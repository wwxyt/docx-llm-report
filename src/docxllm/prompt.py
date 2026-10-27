"""提示词构造：把配置里的 section 描述翻译成 JSON Schema 约束。"""
from __future__ import annotations

from .config import ReportConfig


def build_schema_hint(cfg: ReportConfig) -> str:
    lines = []
    for s in cfg.llm.sections:
        if s.type == "list":
            lines.append(f"- {s.var}: 字符串数组，恰好 {s.count} 条。{s.desc} {s.item_desc}".strip())
        else:
            lines.append(f"- {s.var}: 字符串。{s.desc}")
    return "\n".join(lines)


def build_system_prompt(cfg: ReportConfig) -> str:
    return f"""你是资深{cfg.llm.brief or '报告'}撰写专家，负责产出可直接交付的{cfg.llm.language}报告正文。

硬性规则：
1. 只依据给定的数据撰写，不得编造数据中不存在的数字、单位、机构或时间；
2. 需要引用数字时，必须直接使用「数据摘要」中已算好的值，不要自行计算或换算；
3. 语言为{cfg.llm.tone}，不使用口语、感叹号和第一人称；
4. 不使用 Markdown 标记，不使用「首先/其次/最后」这类模板化连接词，直接陈述结论；
5. 严格输出 JSON 对象，不要输出代码块或任何解释性文字。

JSON 字段要求：
{build_schema_hint(cfg)}"""


def build_messages(cfg: ReportConfig, table_md: str, data_summary: str, extra: str = "") -> list[dict]:
    user = f"""请根据以下数据撰写报告。

## 撰写要求
{cfg.llm.brief or '根据数据撰写一份结构化分析报告。'}

## 数据摘要（已统计，可直接引用）
{data_summary}

## 明细数据（共 {table_md.count(chr(10)) - 1} 行）
{table_md}
{extra}
只返回 JSON 对象，字段为：{', '.join(s.var for s in cfg.llm.sections)}。"""
    return [
        {"role": "system", "content": build_system_prompt(cfg)},
        {"role": "user", "content": user},
    ]


def normalize(content: dict, cfg: ReportConfig) -> dict:
    """补齐缺失字段、裁剪多余条目，保证渲染不会因模型跑偏而失败。"""
    out: dict = {}
    for s in cfg.llm.sections:
        value = content.get(s.var)
        if s.type == "list":
            if isinstance(value, str):
                value = [v.strip() for v in value.split("\n") if v.strip()]
            if not isinstance(value, list):
                value = []
            out[s.var] = [str(v).strip() for v in value if str(v).strip()][: max(s.count * 2, s.count)]
        else:
            out[s.var] = str(value).strip() if value is not None else ""
    return out
