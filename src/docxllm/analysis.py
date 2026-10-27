"""表格数据分析：把「一堆行」变成可直接引用的结论性指标。

设计原则：能算的全部算好，模型只负责组织语言。
—— 一旦让模型自己算合计、占比、增幅，报告就不可信了。
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .excel import to_number

PCT_HINTS = ("同比", "环比", "增长", "增幅", "增速", "占比", "比例", "率", "%")
DATE_HINTS = ("日期", "时间", "月份", "年月", "季度", "周次", "date", "month", "time", "period")
OUTLIER_Z = 2.0


def _is_pct_text(v) -> bool:
    return isinstance(v, str) and v.strip().endswith("%")


def infer_kind(name: str, values: list) -> str:
    """推断列类型：number / percent / category / text / empty。"""
    sample = [v for v in values if v is not None and str(v).strip() != ""]
    if not sample:
        return "empty"
    pct_ratio = sum(1 for v in sample if _is_pct_text(v)) / len(sample)
    num_ratio = sum(1 for v in sample if to_number(v) is not None) / len(sample)
    if pct_ratio >= 0.6:
        return "percent"
    if any(h in name for h in PCT_HINTS) and num_ratio >= 0.8:
        return "percent"
    if num_ratio >= 0.8:
        return "number"
    # 非数值列：长文本视为自由文本，其余都当作分组维度（地区、品类、姓名等）
    avg_len = sum(len(str(v)) for v in sample) / len(sample)
    return "text" if avg_len > 40 else "category"


def _fmt(v: float) -> str:
    return f"{v:,.2f}"


@dataclass
class Insight:
    """分析结果：text 直接进 prompt，findings 供程序二次使用。"""

    text: str
    findings: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _analyse_numbers(rows, group_col, col, values) -> tuple[list[str], dict]:
    pairs = [(r.get(group_col), v) for r, v in zip(rows, values) if v is not None]
    if not pairs:
        return [], {}
    vals = [v for _, v in pairs]
    total, mean, median = sum(vals), statistics.fmean(vals), statistics.median(vals)
    ranked = sorted(pairs, key=lambda x: x[1], reverse=True)
    best, worst = ranked[0], ranked[-1]
    shares = [(g, v, (v / total * 100) if total else 0.0) for g, v in ranked]
    top3_share = sum(s for _, _, s in shares[:3])
    hhi = sum((v / total) ** 2 for _, v in ranked) if total else 0.0
    level = "高度集中" if hhi >= 0.4 else ("较为集中" if hhi >= 0.2 else "相对分散")

    lines = [
        f"【规模】{col}：合计 {_fmt(total)}，均值 {_fmt(mean)}，中位数 {_fmt(median)}；"
        f"最高为 {best[0]}（{_fmt(best[1])}，占 {shares[0][2]:.1f}%），最低为 {worst[0]}（{_fmt(worst[1])}）。",
        f"【结构】{col}的 Top3 合计占 {top3_share:.1f}%，HHI {hhi:.2f}，属于{level}；"
        + "、".join(f"{g} {s:.1f}%" for g, _, s in shares[:5]) + "。",
    ]

    outliers = []
    if len(vals) >= 4:
        sd = statistics.pstdev(vals)
        if sd > 0:
            for g, v in pairs:
                z = (v - mean) / sd
                if abs(z) >= OUTLIER_Z:
                    outliers.append({"group": g, "value": v, "z": round(z, 2)})
    if outliers:
        lines.append(
            "【异常】以下记录偏离均值超过 2 个标准差，需在报告中单独说明："
            + "、".join(f"{o['group']} {_fmt(o['value'])}（z={o['z']}）" for o in outliers) + "。"
        )
    else:
        lines.append(f"【异常】{col}未发现显著离群值（|z| ≥ {OUTLIER_Z} 判定）。")

    return lines, {
        "total": total, "mean": mean, "median": median,
        "best": {"group": best[0], "value": best[1]},
        "worst": {"group": worst[0], "value": worst[1]},
        "shares": [{"group": g, "value": v, "share": round(s, 2)} for g, v, s in shares],
        "top3_share": round(top3_share, 2), "hhi": round(hhi, 4),
        "outliers": outliers,
    }


def _analyse_percent(rows, group_col, col, values) -> tuple[list[str], dict]:
    pairs = [(r.get(group_col), v) for r, v in zip(rows, values) if v is not None]
    if not pairs:
        return [], {}
    vals = [v for _, v in pairs]
    pos = [p for p in pairs if p[1] > 0]
    neg = [p for p in pairs if p[1] < 0]
    best = max(pairs, key=lambda x: x[1])
    worst = min(pairs, key=lambda x: x[1])
    lines = [
        f"【变化】{col}：正值 {len(pos)} 项、负值 {len(neg)} 项；平均 {statistics.fmean(vals):+.2f}%"
        f"（比率类指标只统计分布，不做求和）；最高 {best[0]} {best[1]:+.2f}%，最低 {worst[0]} {worst[1]:+.2f}%。"
    ]
    return lines, {
        "positives": len(pos), "negatives": len(neg),
        "mean": round(statistics.fmean(vals), 2),
        "best": {"group": best[0], "value": best[1]},
        "worst": {"group": worst[0], "value": worst[1]},
    }


def analyze(headers: list[str], rows: list[dict], group_by: str | None = None) -> Insight:
    """产出「可直接引用」的数据洞察文本。"""
    if not rows:
        raise ValueError("没有可分析的数据行")
    if group_by and group_by not in headers:
        raise ValueError(f"group_by 指定的列 `{group_by}` 不在表头中：{headers}")

    kinds = {h: infer_kind(h, [r.get(h) for r in rows]) for h in headers}
    group_col = group_by or next((h for h in headers if kinds[h] == "category"), headers[0])
    number_cols = [h for h in headers if kinds[h] == "number"]
    percent_cols = [h for h in headers if kinds[h] == "percent"]

    findings: dict = {"row_count": len(rows), "columns": kinds, "group_col": group_col, "metrics": {}}
    lines = [
        f"数据规模：{len(rows)} 行 × {len(headers)} 列；分组维度：{group_col}。",
        "列类型判定：" + "，".join(f"{h}={k}" for h, k in kinds.items()) + "。",
    ]
    warnings: list[str] = []

    if not number_cols:
        warnings.append("未识别到数值列，报告将只能做定性描述")

    for col in number_cols:
        text, metrics = _analyse_numbers(rows, group_col, col, [to_number(r.get(col)) for r in rows])
        lines.extend(text)
        findings["metrics"][col] = metrics

    for col in percent_cols:
        text, metrics = _analyse_percent(rows, group_col, col, [to_number(r.get(col)) for r in rows])
        lines.extend(text)
        findings["metrics"][col] = metrics
        warnings.append(f"`{col}` 被判定为比率类指标，已按分布统计处理，未参与求和")

    if len(percent_cols) >= 2:
        warnings.append("存在多个比率列，请确认报告中未将它们直接相加")

    lines.append("以上数值均由程序计算，可直接引用；不得自行重新计算、换算或补充数据中不存在的数字。")
    return Insight(text="\n".join(lines), findings=findings, warnings=warnings)
