"""数据分析层测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from docxllm.analysis import analyze, infer_kind
from docxllm.config import DataSpec, LLMSpec, ReportConfig, Section
from docxllm.prompt import build_messages

HEADERS = ["地区", "销售额（万元）", "同比"]
ROWS = [
    {"地区": "华东", "销售额（万元）": 3280.5, "同比": "+12.4%"},
    {"地区": "华南", "销售额（万元）": 2140.0, "同比": "+8.1%"},
    {"地区": "华北", "销售额（万元）": 1875.3, "同比": "-2.6%"},
    {"地区": "西南", "销售额（万元）": 960.8, "同比": "+21.7%"},
    {"地区": "东北", "销售额（万元）": 612.4, "同比": "-5.3%"},
]


def test_infer_kind():
    assert infer_kind("地区", ["华东", "华南", "华北", "西南", "东北"]) == "category"
    assert infer_kind("销售额（万元）", [1, 2, 3.5]) == "number"
    assert infer_kind("同比", ["+12.4%", "-2.6%"]) == "percent"
    # 列名带"率"且多数为数字 → 仍按比率处理
    assert infer_kind("毛利率", [31.2, 28.9, 30.1]) == "percent"


def test_percent_column_not_summed():
    insight = analyze(HEADERS, ROWS)
    assert "不做求和" in insight.text
    # 12.4+8.1-2.6+21.7-5.3 = 34.3，这个无意义的求和值绝不能出现
    assert "34.3" not in insight.text
    assert any("同比" in w for w in insight.warnings)


def test_number_metrics():
    m = analyze(HEADERS, ROWS).findings["metrics"]["销售额（万元）"]
    assert abs(m["total"] - 8869.0) < 0.01
    assert m["best"] == {"group": "华东", "value": 3280.5}
    assert m["worst"]["group"] == "东北"
    assert abs(sum(s["share"] for s in m["shares"]) - 100) < 0.5
    assert m["shares"][0]["group"] == "华东"


def test_percent_metrics():
    m = analyze(HEADERS, ROWS).findings["metrics"]["同比"]
    assert m["positives"] == 3 and m["negatives"] == 2
    assert m["best"]["group"] == "西南"
    assert m["worst"]["group"] == "东北"


def test_outlier_detected():
    rows = [{"地区": f"R{i}", "值": 10 + i} for i in range(6)] + [{"地区": "异常点", "值": 999}]
    insight = analyze(["地区", "值"], rows)
    outliers = insight.findings["metrics"]["值"]["outliers"]
    assert len(outliers) == 1
    assert outliers[0]["group"] == "异常点"
    assert "偏离均值" in insight.text


def test_no_outlier_when_uniform():
    insight = analyze(HEADERS, ROWS)
    assert insight.findings["metrics"]["销售额（万元）"]["outliers"] == []
    assert "未发现显著离群值" in insight.text


def test_group_by_override():
    insight = analyze(HEADERS, ROWS, group_by="地区")
    assert insight.findings["group_col"] == "地区"


def test_group_by_invalid_raises():
    with pytest.raises(ValueError, match="不在表头"):
        analyze(HEADERS, ROWS, group_by="不存在")


def test_empty_rows_raises():
    with pytest.raises(ValueError, match="没有可分析的数据行"):
        analyze(HEADERS, [])


def test_insight_goes_into_prompt():
    cfg = ReportConfig(
        template=Path("t.docx"),
        data=DataSpec(file="x.xlsx"),
        llm=LLMSpec(sections=[Section(var="summary", desc="总体情况")]),
    )
    insight = analyze(HEADERS, ROWS)
    messages = build_messages(cfg, "| 地区 |", insight.text)
    assert insight.text in messages[1]["content"]
    assert "【结构】" in messages[1]["content"]
