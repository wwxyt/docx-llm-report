# docx-llm-report

> 用大模型撰写并填充 Word 报告：**Excel 数据 + Word 模版 → LLM 写叙述 → 输出 .docx**

很多「AI 生成报告」的项目最后交给你一个 Markdown 或 PDF，但真实业务里要的是一份**能改、能盖章、格式合规的 Word**。
这个项目解决的就是最后一公里：模版你定，数字从数据来，文字让模型写，排版永远不乱。

```
Excel / 数据表 ──①读取映射──> 结构化数据 ──②LLM(强制JSON)──> 文案字段 ──③docxtpl──> 报告.docx
```

## 它不做什么

- 不是「一句话生成整篇报告」的黑盒。内容边界由你的 `report.yaml` 定义，模型只填你声明的字段。
- 不替换 Word 排版。字体、页眉、编号、表格样式全部来自你的模版。
- 不让模型算数。**所有数字由程序从数据源取，模型只负责叙述**——这是报告类场景唯一可信的做法。

## 特性

| 能力 | 说明 |
|------|------|
| 配置驱动 | 一份 `report.yaml` 声明模版、数据列映射、要模型写哪些字段，不改代码即可换业务 |
| **表格分析** | 列类型推断、规模/占比/集中度/离群值全部由程序算好；"同比"类比率列自动识别，**不参与求和** |
| 数字不可篡改 | 表格数值直接来自 Excel，模型只拿到「已算好的数据洞察」，从源头杜绝编数 |
| 强制 JSON | `response_format=json_object` + 解析兜底（剥代码块、截取花括号），模型跑偏不会崩 |
| 模版自检 | `docxllm check` 比对模版标签与配置，提前发现 `{{ sumary }}` 这类拼写事故 |
| 离线可跑 | `--mock` 模式不联网、不花钱，用于 CI 和链路验证 |
| 零 SDK 依赖 | 只用标准库 urllib 调 OpenAI 兼容接口，DeepSeek / Qwen / 本地 vLLM 都能接 |

## 快速开始

```bash
git clone <this-repo> && cd docx-llm-report
pip install -e .

docxllm init              # 生成 report.yaml + 模版 + 示例数据
docxllm run --mock        # 离线跑通，产出 output/report.docx
```

接真实模型：

```bash
# .env.example 里有模板；也可以直接用系统环境变量
set OPENAI_API_KEY=sk-xxx
set OPENAI_BASE_URL=https://api.deepseek.com/v1
set LLM_MODEL=deepseek-chat

docxllm run -o output/经营分析报告.docx
```

支持任何 OpenAI 兼容端点：

| 服务 | OPENAI_BASE_URL | LLM_MODEL |
|------|-----------------|-----------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 本地 vLLM / Ollama | `http://localhost:8000/v1` | 你的模型名 |

## 工作原理

```
report.yaml ─┬─> template.docx （Jinja2 标签）
             ├─> data.file      （Excel 工作表）
             └─> llm.sections   （要模型写的字段与要求）
                     │
                     ▼
        读取 Excel → 列名映射 → 生成数据摘要（合计/极值）
                     │
                     ▼
        Prompt(含摘要 + 明细表 + JSON Schema) → 模型 → JSON
                     │
                     ▼
        docxtpl 渲染 → output/*.docx
```

### 三个必踩的坑（本项目已处理）

1. **`{%tr for %}` 与 `{%tr endfor %}` 必须各占一整行。** 放在同一行会导致整行被 docxtpl 剥掉，报 `unknown tag 'endfor'`。
2. **模版字段名与 Excel 表头是两套命名。** 中文表头需要 `columns` 映射，否则表格渲染成空白行。
3. **段落级循环要用 `{%p for %}`。** 直接 `{% for %}` 会把标签当普通文字渲染出来。

## 表格分析能力

模型不是数据分析师，让它自己算合计、占比、增幅，报告就不可信了。所以**能算的全部在进模型前算好**，
模型拿到的是一段「数据洞察」，只负责组织语言。

以示例数据为例，模型实际收到的内容：

```
数据规模：5 行 × 3 列；分组维度：地区。
列类型判定：地区=category，销售额（万元）=number，同比=percent。
【规模】销售额（万元）：合计 8,869.00，均值 1,773.80，中位数 1,875.30；最高为 华东（3,280.50，占 37.0%），最低为 东北（612.40）。
【结构】销售额（万元）的 Top3 合计占 82.3%，HHI 0.26，属于较为集中；华东 37.0%、华南 24.1%、华北 21.1%、西南 10.8%、东北 6.9%。
【异常】销售额（万元）未发现显著离群值（|z| ≥ 2.0 判定）。
【变化】同比：正值 3 项、负值 2 项；平均 +6.86%（比率类指标只统计分布，不做求和）；最高 西南 +21.70%，最低 东北 -5.30%。
```

| 分析项 | 是否自动计算 | 说明 |
|--------|--------------|------|
| 列类型推断 | ✅ | `number` / `percent` / `category` / `text`，比率列靠列名与 `%` 后缀双重判定 |
| 规模指标 | ✅ | 合计、均值、中位数、最高/最低及对应分组、各自占比 |
| 结构集中度 | ✅ | 各分组占比、Top3 占比、HHI 及「集中/分散」判定 |
| 离群值 | ✅ | `\|z\| ≥ 2` 的记录及 z 值，报告中可点名解释 |
| 比率列保护 | ✅ | 同比/环比/占比等只统计分布（正负计数、均值、极值），**绝不求和** |
| 分组维度 | ✅ | `data.group_by` 指定，省略则自动取第一个文本列 |
| 时间趋势 | ❌ | 未实现（按月/季的序列变化需要额外实现） |
| 多维交叉（透视） | ❌ | 未实现，当前只按单一维度分组 |
| 图表 | ❌ | Roadmap 中 |
| 因果解释、业务判断 | 交给模型 | 只能基于上述指标展开，不得引入数据外的事实 |

> 一句话：**事实（数字、占比、离群）由程序产出，观点（归因、建议）由模型产出。**

## 配置详解

```yaml
template: templates/report.docx   # 相对 report.yaml 所在目录

data:
  file: examples/sample.xlsx
  sheet: 销售数据                # 省略则读第一个工作表
  rows_var: rows                 # 模版里循环用的变量名
  group_by: 地区                 # 分析分组维度，省略则自动取第一个文本列
  columns:                       # Excel 表头 → 模版字段名
    地区: region
    销售额（万元）: sales
    同比: yoy

llm:
  model: deepseek-chat
  temperature: 0.3
  brief: 本期区域销售经营分析，面向管理层汇报。   # 决定写作视角
  language: 中文
  tone: 正式书面语
  sections:                      # 每个 section 对应模版里的一个变量
    - var: title
      desc: 报告标题，不超过 20 字。
    - var: summary
      desc: 总体情况，200-300 字，一段话。
    - var: analysis
      type: list                 # list = 多段/多行
      count: 3
      desc: 趋势分析，从数据中提炼规律与异常。
      item_desc: 每条 100-150 字，一条一个结论。
    - var: conclusion
      desc: 结论与建议，150-200 字，可执行。

meta:
  period: auto                   # auto 或写死字符串
  generated_at: auto
  model_note: auto               # 落款注明由哪个模型生成
```

## 换成你自己的 Word 模版

1. 用 Word 正常排版，在需要填内容的位置写标签：

| 需求 | 写法 |
|------|------|
| 单值 | `{{ summary }}` |
| 表格逐行 | 一整行写 `{%tr for r in rows %}`，下一行写 `{{ r.region }}`，再下一行写 `{%tr endfor %}` |
| 多段落（列表） | 一整段写 `{%p for p in analysis %}`，下一段写 `{{ p }}`，再下一段写 `{%p endfor %}` |
| 落款 | `{{ generated_at }}`、`{{ model_note }}` |

2. 在 `report.yaml` 里把 `llm.sections` 改成你的字段，`data.columns` 改成你的表头映射。
3. 跑 `docxllm check` 自检，再 `docxllm run`。

> 注意：标签要写在一个 run 里（别在中间改字体），否则 Word 会把 `{{` 和 `summary` 拆到两个 XML 节点，渲染时匹配不上。

## CLI

| 命令 | 作用 |
|------|------|
| `docxllm init [--dir D] [--force]` | 生成示例工程（配置、模版、数据） |
| `docxllm run [-c report.yaml] [-o out.docx] [--mock] [--model M]` | 生成报告 |
| `docxllm check [-c report.yaml]` | 校验模版标签与配置一致性，有错误返回 1 |

## 项目结构

```
src/docxllm/
├── config.py      # report.yaml → dataclass
├── excel.py       # 读表、列映射、转 Markdown 明细
├── analysis.py    # 列类型推断、规模/占比/HHI/离群值、比率列保护
├── llm.py         # OpenAI 兼容客户端 + JSON 解析兜底 + 重试
├── prompt.py      # 从 sections 生成 JSON Schema 约束与提示词
├── render.py      # docxtpl 渲染
├── validate.py    # 模版标签自检
├── template.py    # 程序化生成示例模版
├── pipeline.py    # 主流程
└── cli.py         # init / run / check
tests/test_pipeline.py   # 10 个端到端用例
tests/test_analysis.py   # 10 个数据分析用例
```

## 测试

```bash
pip install -e ".[dev]"
pytest -q          # 20 passed，不联网
```

覆盖：mock 全链路出 docx、表格行数与内容、段落循环展开、列映射、缺列报错、JSON 三种脏格式解析、模版自检的正反例、CLI 端到端；
以及列类型推断、比率列不求和、占比与 HHI、离群值检测、分组维度校验、洞察文本注入 prompt。

## FAQ

**Q：为什么不直接用 Word 的邮件合并？**
邮件合并只能做「一行数据一份文档」，无法写分析叙述，也不能做多段落推理。本项目补的正是「叙述部分」。

**Q：模型写出来的数字不放心怎么办？**
本项目把数字全部剥离给程序：`analysis.analyze()` 先算好合计、均值、占比、集中度、离群值给模型引用，模型只做文字组织。上生产时建议再加一条：渲染前正则扫描正文数字，与数据源比对。

**Q：能一次生成几十页吗？**
不建议单次请求写长文，质量会崩。做法是按章节拆多个 section（或多次调用），每节带上「上一节摘要」滚动生成。

**Q：需要联网吗？**
`--mock` 完全离线。真实模式只需能访问你的模型端点，内网 vLLM / Ollama 也行。

## Roadmap

- [ ] 每节单独调用（长文档模式）
- [ ] 时间趋势分析（按月/季序列、环比）
- [ ] 多维交叉透视（两个维度以上）
- [ ] 数字校验器：正文数字与数据源比对
- [ ] 图表插入（Excel 图表 → 图片 → 模版占位）
- [ ] 批量模式：一行数据一份报告，打包 zip
- [ ] 模版标签可视化编辑

## 相关项目

- [docxtpl](https://github.com/elapouya/python-docx-template)：本项目的渲染底座，Jinja2 语法进 docx
- [STORM](https://github.com/stanford-oval/storm) / [GPT-Researcher](https://github.com/assafelovic/gpt-researcher)：内容生成更强，但输出不套模版，可作为「正文供应商」接进来

## License

MIT
