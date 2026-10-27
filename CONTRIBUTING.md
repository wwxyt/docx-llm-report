# 贡献指南

感谢你愿意花时间。这个项目的目标很窄：**把 Excel 的数据和 Word 的模版接起来，中间那段叙述交给大模型，但数字绝不让模型碰。** 提交之前，先确认你的改动和这个目标是一致的。

## 开发环境

```bash
git clone https://github.com/wwxyt/docx-llm-report
cd docx-llm-report
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```

要求 Python ≥ 3.9。CI 会跑 3.9 / 3.11 / 3.13 三个版本，本地用哪个都行。

## 跑通一次完整链路

不需要任何 API Key：

```bash
docxllm init --dir demo
cd demo
docxllm check          # 校验模版标签与配置是否对得上
docxllm run --mock     # 出 output/report.docx
```

要接真实模型，把 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`LLM_MODEL` 三个环境变量设好即可，任何 OpenAI 兼容端点都能用。

## 三条设计红线

改动如果触碰这三条，请先在 Issue 里讨论，不要直接提 PR。

1. **数字只从数据源来。** 报告里出现的任何数值，必须能追溯到 Excel 或 `analysis.py` 的计算结果。不要让模型自己算，也不要在提示词里暗示它去算。
2. **依赖保持极薄。** 目前只依赖 docxtpl、openpyxl、PyYAML，HTTP 请求用标准库 urllib 直接写。引入新依赖需要有充分理由。
3. **渲染层与模版层解耦。** `render.py` 是唯一接触 docxtpl 的地方。将来换模版引擎时，理想情况下只改这一个文件。

## 常见改动怎么做

**新增一个分析指标** —— 改 `analysis.py` 的 `analyze()`，把结果拼进返回的 `Insight.text`，同时在 `tests/test_analysis.py` 加断言。注意指标要保持「程序可算、可验证」，比如占比要能被独立复算。

**新增一种 section 类型** —— `config.Section` 加字段，`prompt.py` 的 schema 生成与 `pipeline.mock_content()` 的占位逻辑同步跟上，`validate.py` 若涉及模版标签也要看一眼。

**支持新的数据源（CSV、数据库）** —— 在 `excel.py` 里加读取函数，保持返回 `(headers, rows)` 的契约，其余模块不需要知道数据从哪来。

**修模版标签相关的问题** —— 先看 README 的「三个必踩的坑」，多半是同类原因：标签被 Word 拆进多个 `w:r`、`{%tr for %}` 没占满整行、段落循环误用了 `{% for %}`。

## 提交规范

提交信息用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：

```
feat(analysis): 支持按季度分组的环比计算
fix(render): 表格行循环标签跨行时被剥离
docs: 补充中文字体继承的说明
test: 覆盖 model 返回多余字段的情况
```

范围名用模块名（`analysis` / `excel` / `llm` / `prompt` / `render` / `validate` / `template` / `pipeline` / `cli` / `config`）。

## PR 要求

- `pytest -q` 全绿，且新行为要有对应测试（本项目全离线运行，不允许测试里真的调模型）
- 改了模版标签或配置项时，README 与 `cli.py` 里的 `SAMPLE_CONFIG` 要同步，否则 `docxllm init` 生成出来的示例会跟文档不一致
- 一个 PR 只做一件事，重构和行为变更不要混在一起

## 报告问题

用 Issue 模板，务必附上**最小可复现输入**：模版里相关的那几行标签、Excel 的表头、`report.yaml` 的相关片段。只贴一句「表格渲染不出来」基本没法定位。

## 许可证

贡献的代码按 MIT 授权，与项目一致。
