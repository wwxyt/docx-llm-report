"""模版自检：检查 docx 里的 Jinja2 标签与 report.yaml 是否对得上。

针对的是一类最常见的事故——模版里写了 `{{ sumary }}`（拼错），
渲染时默默留空，报告交出去才发现少了一段。
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from .config import ReportConfig

TAG_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
BLOCK_RE = re.compile(r"\{%\s*(?:(?:p|tr|tc|r)\s+)?(for\s+([A-Za-z_]\w*)\s+in\s+([^%]+?)|if\s+[^%]+?)\s*%\}")
PART_RE = re.compile(r"word/(document|header\d*|footer\d*|footnotes|comments)\.xml$")


def _xml_parts(docx_path: Path):
    with zipfile.ZipFile(docx_path) as z:
        for name in z.namelist():
            if PART_RE.match(name):
                yield z.read(name).decode("utf-8", "ignore")


def extract_usage(docx_path: str | Path) -> dict:
    """提取模版里用到的变量、循环变量与循环数据源。"""
    variables: set[str] = set()
    loop_vars: set[str] = set()
    loop_sources: set[str] = set()
    for xml in _xml_parts(Path(docx_path)):
        for m in TAG_RE.finditer(xml):
            root = re.match(r"[A-Za-z_]\w*", m.group(1).strip())
            if root:
                variables.add(root.group())
        for m in BLOCK_RE.finditer(xml):
            if m.group(2):  # for 循环
                loop_vars.add(m.group(2))
                src = re.match(r"[A-Za-z_]\w*", m.group(3).strip())
                if src:
                    loop_sources.add(src.group())
    return {
        "variables": variables,
        "loop_vars": loop_vars,
        "loop_sources": loop_sources,
    }


def check(cfg: ReportConfig) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)。"""
    template = cfg.resolve(cfg.template)
    if not template.exists():
        return [f"模版不存在：{template}"], []

    usage = extract_usage(template)
    errors: list[str] = []

    provided = {s.var for s in cfg.llm.sections}
    provided.add(cfg.data.rows_var)
    provided.update(cfg.auto_meta("x").keys())

    used = usage["variables"] | usage["loop_sources"]
    known = provided | usage["loop_vars"]

    unknown = sorted(v for v in used if v not in known)
    for v in unknown:
        errors.append(f"模版使用了未定义的变量 `{v}`：既不在 llm.sections，也不在 meta 或 {cfg.data.rows_var} 中")

    unused = sorted(v for v in provided if v not in used)
    warnings = [f"配置里的 `{v}` 在模版中没有占位符，生成的内容会被丢弃" for v in unused]

    if cfg.data.rows_var not in usage["loop_sources"]:
        warnings.append(
            f"模版未对 `{cfg.data.rows_var}` 做循环（如 {{%tr for r in {cfg.data.rows_var} %}}），表格数据不会出现在报告里"
        )
    return errors, warnings
