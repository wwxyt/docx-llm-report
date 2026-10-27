"""模版渲染：把上下文灌进 docx。"""
from __future__ import annotations

from pathlib import Path

from docxtpl import DocxTemplate

from .config import ReportConfig


class RenderError(RuntimeError):
    """模版渲染失败。"""


def build_context(cfg: ReportConfig, rows: list[dict], content: dict, model_note: str) -> dict:
    ctx = cfg.auto_meta(model_note)
    ctx[cfg.data.rows_var] = rows
    ctx.update(content)
    return ctx


def render(cfg: ReportConfig, out: str | Path, context: dict) -> Path:
    template = cfg.resolve(cfg.template)
    if not template.exists():
        raise FileNotFoundError(f"模版不存在：{template}（可先运行 `docxllm init` 生成示例模版）")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc = DocxTemplate(str(template))
        doc.render(context, autoescape=True)
        doc.save(str(out_path))
    except Exception as exc:  # jinja2 语法错误等
        raise RenderError(
            f"模版渲染失败：{type(exc).__name__}: {exc}\n"
            f"提示：检查 {template.name} 中的 Jinja2 标签，或运行 `docxllm check` 定位缺失字段。"
        ) from exc
    return out_path
