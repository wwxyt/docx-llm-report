"""主流程：Excel -> (LLM) -> Word。"""
from __future__ import annotations

import os
from pathlib import Path

from .config import ReportConfig
from .excel import load_data, summarize, to_markdown
from .llm import chat_json
from .prompt import build_messages, normalize
from .render import build_context, render


def mock_content(cfg: ReportConfig, row_count: int) -> dict:
    """离线占位文案：不花钱、不需要 key，用来验证链路。"""
    out: dict = {}
    for s in cfg.llm.sections:
        if s.type == "list":
            out[s.var] = [
                f"（mock 第 {i + 1} 条）此处为占位分析文字，用于验证段落循环是否正常，"
                f"接入真实模型后由大模型依据 {row_count} 行数据撰写。"
                for i in range(s.count)
            ]
        elif s.var == "title":
            out[s.var] = "示例分析报告"
        else:
            out[s.var] = (
                f"（mock）本段为占位文字。本次共读取 {row_count} 行数据，"
                "表格中的数字来自数据源本身，模型只负责撰写叙述部分。"
            )
    return out


def generate(
    cfg: ReportConfig,
    out: str | Path | None = None,
    mock: bool = False,
    model: str | None = None,
) -> tuple[Path, dict]:
    """执行一次报告生成，返回 (输出路径, 模型产出的字段)。"""
    headers, raw_rows, mapped_rows = load_data(cfg.data, cfg.resolve(cfg.data.file))

    if mock:
        content = mock_content(cfg, len(raw_rows))
        note = "由大模型生成（mock 模式，占位文案）"
    else:
        messages = build_messages(cfg, to_markdown(headers, raw_rows), summarize(headers, raw_rows))
        content = normalize(chat_json(messages, model=cfg.llm.model or model, temperature=cfg.llm.temperature), cfg)
        note = f"由大模型生成 · {cfg.llm.model or model or os.getenv('LLM_MODEL', 'gpt-4o-mini')}"

    ctx = build_context(cfg, mapped_rows, content, note)
    out_path = Path(out) if out else cfg.resolve("output/report.docx")
    return render(cfg, out_path, ctx), content
