"""命令行入口。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import load_config
from .excel import write_sample
from .pipeline import generate
from .template import build_template
from .validate import check

SAMPLE_CONFIG = """\
# docx-llm-report 配置文件
# 全部路径均相对本文件所在目录

template: templates/report.docx

data:
  file: examples/sample.xlsx
  sheet: 销售数据
  rows_var: rows            # 模版里循环用的变量名
  columns:                  # Excel 表头 -> 模版字段名
    地区: region
    销售额（万元）: sales
    同比: yoy

llm:
  model: deepseek-chat      # 留空则读取环境变量 LLM_MODEL
  temperature: 0.3
  brief: 本期区域销售经营分析，面向管理层汇报。
  language: 中文
  tone: 正式书面语
  sections:                 # 每个 section 都是一个模版变量
    - var: title
      desc: 报告标题，不超过 20 字。
    - var: summary
      desc: 总体情况，200-300 字，一段话，概括整体规模与结构。
    - var: analysis
      type: list            # list 会渲染成多段/多行
      count: 3
      desc: 趋势分析，从数据中提炼规律与异常。
      item_desc: 每条 100-150 字，一条一个结论。
    - var: conclusion
      desc: 结论与建议，150-200 字，给出可执行的行动建议。

meta:
  period: auto              # auto = 当前年月，也可写死字符串
  generated_at: auto
  model_note: auto
"""


def cmd_init(args) -> int:
    target = Path(args.dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    cfg_path = target / "report.yaml"
    if cfg_path.exists() and not args.force:
        print(f"已存在 {cfg_path}，如需覆盖请加 --force")
        return 1
    build_template(target / "templates" / "report.docx")
    write_sample(target / "examples" / "sample.xlsx")
    cfg_path.write_text(SAMPLE_CONFIG, encoding="utf-8")
    print("已生成示例工程：")
    for p in ("report.yaml", "templates/report.docx", "examples/sample.xlsx"):
        print(f"  {p}")
    print("下一步：docxllm run --mock")
    return 0


def cmd_run(args) -> int:
    cfg = load_config(args.config)
    print(f"配置：{Path(args.config).resolve()}")
    print(f"数据：{cfg.resolve(cfg.data.file)}")
    print(f"模版：{cfg.resolve(cfg.template)}")
    out = args.out or cfg.resolve("output/report.docx")
    path, content = generate(cfg, out=out, mock=args.mock, model=args.model)
    mode = "mock（未调用模型）" if args.mock else "真实模型调用"
    print(f"模式：{mode}")
    print(f"产出字段：{', '.join(content)}")
    print(f"已生成：{path}")
    return 0


def cmd_check(args) -> int:
    cfg = load_config(args.config)
    errors, warnings = check(cfg)
    for w in warnings:
        print(f"[warn] {w}")
    for e in errors:
        print(f"[error] {e}")
    if errors:
        print(f"\n检查未通过：{len(errors)} 个错误、{len(warnings)} 个警告")
        return 1
    print(f"\n检查通过（{len(warnings)} 个警告）")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="docxllm",
        description="用大模型撰写并填充 Word 报告：Excel + Word 模版 -> LLM -> .docx",
    )
    p.add_argument("--version", action="version", version=f"docx-llm-report {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    i = sub.add_parser("init", help="生成示例工程（配置 + 模版 + 示例数据）")
    i.add_argument("--dir", default=".", help="目标目录，默认当前目录")
    i.add_argument("--force", action="store_true", help="覆盖已存在的 report.yaml")
    i.set_defaults(func=cmd_init)

    r = sub.add_parser("run", help="生成报告")
    r.add_argument("-c", "--config", default="report.yaml", help="配置文件路径")
    r.add_argument("-o", "--out", default=None, help="输出 docx 路径")
    r.add_argument("--mock", action="store_true", help="不调用模型，用占位文案验证链路")
    r.add_argument("--model", default=None, help="临时指定模型名（覆盖配置与环境变量）")
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("check", help="检查模版标签与配置是否一致")
    c.add_argument("-c", "--config", default="report.yaml", help="配置文件路径")
    c.set_defaults(func=cmd_check)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
