"""report.yaml 的加载与数据结构。"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Section:
    """一段由大模型产出的内容。"""

    var: str
    desc: str
    type: str = "str"          # str | list
    count: int = 3             # type=list 时的条数
    item_desc: str = ""


@dataclass
class DataSpec:
    file: str
    sheet: str | None = None
    rows_var: str = "rows"
    # 分组维度（不必填，默认自动取第一个文本列，如"地区""品类"）
    group_by: str | None = None
    # 键为 Excel 表头，值为模版里使用的字段名；为空则原样使用表头
    columns: dict[str, str] = field(default_factory=dict)


@dataclass
class LLMSpec:
    model: str | None = None
    temperature: float = 0.3
    brief: str = ""
    language: str = "中文"
    tone: str = "正式书面语"
    sections: list[Section] = field(default_factory=list)


@dataclass
class ReportConfig:
    template: Path
    data: DataSpec
    llm: LLMSpec
    meta: dict = field(default_factory=dict)
    base_dir: Path = field(default_factory=Path.cwd)

    def resolve(self, p: str | Path) -> Path:
        """把配置里的相对路径解析为相对配置文件的路径。"""
        path = Path(p)
        return path if path.is_absolute() else (self.base_dir / path)

    def auto_meta(self, model_note: str) -> dict:
        """生成落款类变量：报告期间 / 生成时间 / 模型说明。"""
        meta = dict(self.meta or {})
        meta.setdefault("period", dt.date.today().strftime("%Y 年 %m 月"))
        meta.setdefault("generated_at", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
        meta.setdefault("model_note", model_note)
        for k in ("period", "generated_at", "model_note"):
            if str(meta.get(k, "")).strip().lower() == "auto":
                meta[k] = {
                    "period": dt.date.today().strftime("%Y 年 %m 月"),
                    "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "model_note": model_note,
                }[k]
        return meta


def load_config(path: str | Path) -> ReportConfig:
    cfg_path = Path(path).resolve()
    if not cfg_path.exists():
        raise FileNotFoundError(f"配置文件不存在：{cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    base = cfg_path.parent

    data_raw = raw.get("data") or {}
    if not data_raw.get("file"):
        raise ValueError("report.yaml 缺少 data.file")

    llm_raw = raw.get("llm") or {}
    sections = [Section(**s) for s in (llm_raw.get("sections") or [])]
    if not sections:
        raise ValueError("report.yaml 缺少 llm.sections，至少要定义一个变量")

    for s in sections:
        if s.type not in ("str", "list"):
            raise ValueError(f"section `{s.var}` 的 type 只能是 str 或 list")
        if not s.var.isidentifier():
            raise ValueError(f"section 变量名 `{s.var}` 不合法，必须是合法标识符")

    return ReportConfig(
        template=Path(raw.get("template", "templates/report.docx")),
        data=DataSpec(
            file=data_raw["file"],
            sheet=data_raw.get("sheet"),
            rows_var=data_raw.get("rows_var", "rows"),
            group_by=data_raw.get("group_by"),
            columns=dict(data_raw.get("columns") or {}),
        ),
        llm=LLMSpec(
            model=llm_raw.get("model"),
            temperature=float(llm_raw.get("temperature", 0.3)),
            brief=llm_raw.get("brief", ""),
            language=llm_raw.get("language", "中文"),
            tone=llm_raw.get("tone", "正式书面语"),
            sections=sections,
        ),
        meta=dict(raw.get("meta") or {}),
        base_dir=base,
    )
