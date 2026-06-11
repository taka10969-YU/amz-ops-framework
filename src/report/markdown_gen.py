from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.data_layer.models import (
    AdArchitecture,
    AttackPlan,
    BudgetBreakdown,
    CompetitorTimeline,
    FullPipelineResult,
    KeywordLibrary,
    OptimizationAction,
    RiskAlert,
)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class MarkdownReportGenerator:
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            keep_trailing_newline=True,
        )

    def generate_keyword_report(self, library: KeywordLibrary) -> str:
        lines: list[str] = []
        lines.append("# 关键词库报告")
        lines.append("")
        lines.append("## 概览")
        lines.append("")
        lines.append(f"- 总关键词数: **{library.total_keywords}**")
        lines.append(f"- 流量结构: **{library.traffic_structure}**")
        lines.append(f"- 品类转化率: **{library.category_cvr:.2%}**")
        lines.append(f"- 生成时间: {library.created_at}")
        lines.append("")

        tier_counts: dict[str, int] = {}
        for kw in library.classified_keywords:
            label = kw.priority if kw.priority else "未分级"
            tier_counts[label] = tier_counts.get(label, 0) + 1

        lines.append("## 分级分布")
        lines.append("")
        lines.append("| 分级 | 数量 |")
        lines.append("|------|------|")
        for tier, count in tier_counts.items():
            lines.append(f"| {tier} | {count} |")
        lines.append("")

        lines.append("## Top 20 关键词")
        lines.append("")
        lines.append("| 关键词 | ABA排名 | 搜索量 | CPC | SPR | 推广成本 | 优先级 |")
        lines.append("|--------|---------|--------|-----|-----|----------|--------|")
        sorted_kw = sorted(
            library.classified_keywords, key=lambda k: k.aba_rank_weekly or 999999
        )[:20]
        for kw in sorted_kw:
            lines.append(
                f"| {kw.keyword_text} "
                f"| {kw.aba_rank_weekly} "
                f"| {kw.weekly_search_volume} "
                f"| {kw.cpc:.2f} "
                f"| {kw.spr} "
                f"| {kw.push_cpa:.2f} "
                f"| {kw.priority} |"
            )
        lines.append("")

        lines.append("## 竞争分析")
        lines.append("")
        lines.append("| 关键词 | 垄断度(流量) | 垄断度(转化) | Top1 ASIN | Top1 品牌 | 有效竞品数 |")
        lines.append("|--------|-------------|-------------|-----------|----------|-----------|")
        for kw in sorted_kw:
            lines.append(
                f"| {kw.keyword_text} "
                f"| {kw.traffic_monopoly:.1%} "
                f"| {kw.sales_monopoly:.1%} "
                f"| {kw.top1_asin} "
                f"| {kw.top1_brand} "
                f"| {kw.effective_competitor_count} |"
            )
        lines.append("")

        lines.append("## 否定词列表")
        lines.append("")
        if library.negation_list:
            for neg in library.negation_list:
                lines.append(f"- {neg}")
        else:
            lines.append("（无否定词）")
        lines.append("")

        lines.append("## 推广成本排名")
        lines.append("")
        lines.append("| 关键词 | 推广CPA | 日预算需求 | 日目标订单 |")
        lines.append("|--------|---------|-----------|-----------|")
        by_cost = sorted(
            library.classified_keywords,
            key=lambda k: k.daily_budget_needed,
            reverse=True,
        )
        for kw in by_cost:
            lines.append(
                f"| {kw.keyword_text} "
                f"| {kw.push_cpa:.2f} "
                f"| {kw.daily_budget_needed:.2f} "
                f"| {kw.daily_order_target:.1f} |"
            )
        lines.append("")

        return "\n".join(lines)

    def generate_competitor_report(self, timeline: CompetitorTimeline) -> str:
        lines: list[str] = []
        lines.append("# 竞品拆解报告")
        lines.append("")
        lines.append("## 基本信息")
        lines.append("")
        lines.append(f"- ASIN: **{timeline.asin}**")
        lines.append(f"- 标题: {timeline.product_title}")
        lines.append(f"- 品类: {timeline.category}")
        lines.append(f"- 分析周期: {timeline.total_weeks} 周")
        lines.append(f"- 阶段总结: {timeline.phase_summary}")
        lines.append("")

        lines.append("## 周度时间线")
        lines.append("")
        lines.append(
            "| 周次 | 日期 | 广告词数 | Top关键词 | 占比 | 策略 | "
            "价格 | 变动 | 优惠券 | BSR | 评分 | 评论数 | 变动 | 策略变化 | 关键决策 |"
        )
        lines.append(
            "|------|------|----------|----------|------|------|"
            "------|------|--------|-----|------|--------|------|----------|----------|"
        )
        for ev in timeline.weekly_events:
            lines.append(
                f"| {ev.week_label} "
                f"| {ev.date_range} "
                f"| {ev.ad_keyword_count} "
                f"| {ev.top_keyword} "
                f"| {ev.top_keyword_share:.1%} "
                f"| {ev.top_keyword_strategy} "
                f"| {ev.price:.2f} "
                f"| {ev.price_change} "
                f"| {ev.coupon} "
                f"| {ev.bsr_category} "
                f"| {ev.rating:.1f} "
                f"| {ev.reviews} "
                f"| {ev.review_change} "
                f"| {ev.ad_strategy_change} "
                f"| {ev.key_decision} |"
            )
        lines.append("")

        lines.append("## 广告词演化")
        lines.append("")
        for ev in timeline.weekly_events:
            lines.append(
                f"- **{ev.week_label}** ({ev.date_range}): "
                f"{ev.ad_keyword_count} 个关键词, 策略: {ev.ad_strategy_change or '无变化'}"
            )
        lines.append("")

        lines.append("## 价格策略")
        lines.append("")
        price_events = [
            ev for ev in timeline.weekly_events if ev.price_change
        ]
        if price_events:
            for ev in price_events:
                lines.append(
                    f"- **{ev.week_label}**: {ev.price_change} → ${ev.price:.2f}"
                )
        else:
            lines.append("（未检测到价格调整）")
        lines.append("")

        lines.append("## 评论分析")
        lines.append("")
        review_events = [
            ev for ev in timeline.weekly_events if ev.review_change
        ]
        if review_events:
            for ev in review_events:
                lines.append(
                    f"- **{ev.week_label}**: {ev.review_change} → {ev.reviews} 条, 评分 {ev.rating:.1f}"
                )
        else:
            lines.append("（评论数据平稳）")
        lines.append("")

        lines.append("## 关键发现")
        lines.append("")
        findings = []
        kw_trend = [
            (ev.week_label, ev.ad_keyword_count)
            for ev in timeline.weekly_events
        ]
        if kw_trend:
            first_kw = kw_trend[0][1]
            last_kw = kw_trend[-1][1]
            diff = last_kw - first_kw
            findings.append(
                f"1. 广告关键词数从 {first_kw} 变化到 {last_kw}（{'增加' if diff > 0 else '减少'}{abs(diff)} 个）"
            )

        price_vals = [ev.price for ev in timeline.weekly_events if ev.price > 0]
        if price_vals:
            findings.append(
                f"2. 价格区间: ${min(price_vals):.2f} ~ ${max(price_vals):.2f}"
            )

        review_vals = [
            ev.reviews for ev in timeline.weekly_events if ev.reviews > 0
        ]
        if review_vals:
            findings.append(
                f"3. 评论增长: {min(review_vals)} → {max(review_vals)}"
            )

        bsr_vals = [
            ev.bsr_category for ev in timeline.weekly_events if ev.bsr_category > 0
        ]
        if bsr_vals:
            findings.append(
                f"4. BSR变化: {max(bsr_vals)} → {min(bsr_vals)}（越小越好）"
            )

        top_kws = [
            ev.top_keyword
            for ev in timeline.weekly_events
            if ev.top_keyword
        ]
        if top_kws:
            from collections import Counter

            most_common = Counter(top_kws).most_common(1)[0]
            findings.append(
                f"5. 最常出现的热门关键词: {most_common[0]}（{most_common[1]} 周）"
            )

        for f in findings[:5]:
            lines.append(f)
        lines.append("")

        return "\n".join(lines)

    def generate_strategy_report(
        self,
        architecture: AdArchitecture,
        budget: BudgetBreakdown,
        risk_alerts: list[RiskAlert],
        attack_plans: list[AttackPlan],
    ) -> str:
        lines: list[str] = []
        lines.append("# 广告策略报告")
        lines.append("")

        lines.append("## 广告架构")
        lines.append("")
        lines.append(f"- 架构名称: **{architecture.name}**")
        lines.append(f"- 当前阶段: **{architecture.stage}**")
        lines.append(f"- 推广策略: {architecture.push_strategy}")
        lines.append(f"- 竞价策略: {architecture.bidding_strategy}")
        lines.append(
            f"- 首位竞价比例: {architecture.top_position_bid_pct}%"
        )
        lines.append(
            f"- 其余位置比例: {architecture.rest_position_bid_pct}%"
        )
        lines.append("")

        if architecture.campaigns:
            lines.append("### 广告活动结构")
            lines.append("")
            lines.append("| 活动名称 | 类型 | 预算 | 匹配方式 | 关键词数 |")
            lines.append("|----------|------|------|----------|----------|")
            for camp in architecture.campaigns:
                lines.append(
                    f"| {camp.get('name', '')} "
                    f"| {camp.get('type', '')} "
                    f"| {camp.get('budget', '')} "
                    f"| {camp.get('match_type', '')} "
                    f"| {camp.get('keyword_count', '')} |"
                )
            lines.append("")

        lines.append("## 预算分配")
        lines.append("")
        lines.append(f"- 运营阶段: **{budget.stage}**")
        lines.append(f"- 预计营收: ${budget.revenue:,.2f}")
        lines.append(f"- 广告占比: {budget.ad_spend_ratio:.1%}")
        lines.append(f"- 广告预算: ${budget.ad_spend_amount:,.2f}")
        lines.append(f"- 目标ACoS: {budget.target_acos:.1%}")
        lines.append(f"- 净利率: {budget.net_margin:.1%}")
        lines.append(f"- 可接受广告支出: ${budget.acceptable_ad_spend:,.2f}")
        lines.append("")

        if budget.allocations:
            lines.append("### 按阶段分配")
            lines.append("")
            lines.append("| 阶段 | 占比 |")
            lines.append("|------|------|")
            for stage_name, pct in budget.allocations.items():
                lines.append(f"| {stage_name} | {pct:.1%} |")
            lines.append("")

        if budget.ad_type_allocations:
            lines.append("### 按广告类型分配")
            lines.append("")
            lines.append("| 广告类型 | 占比 |")
            lines.append("|----------|------|")
            for ad_type, pct in budget.ad_type_allocations.items():
                lines.append(f"| {ad_type} | {pct:.1%} |")
            lines.append("")

        lines.append("## 风险评估")
        lines.append("")
        if risk_alerts:
            lines.append(
                "| 风险类型 | 触发条件 | 当前值 | 阈值 | 严重程度 | 应对策略 | 执行动作 | 负责人 |"
            )
            lines.append(
                "|----------|----------|--------|------|----------|----------|----------|--------|"
            )
            for risk in risk_alerts:
                lines.append(
                    f"| {risk.risk_type} "
                    f"| {risk.trigger_condition} "
                    f"| {risk.current_value} "
                    f"| {risk.threshold} "
                    f"| {risk.severity} "
                    f"| {risk.strategy} "
                    f"| {risk.action} "
                    f"| {risk.owner} |"
                )
        else:
            lines.append("（当前无活跃风险）")
        lines.append("")

        lines.append("## 竞品攻击计划")
        lines.append("")
        if attack_plans:
            for plan in attack_plans:
                lines.append(f"### 目标: {plan.competitor_asin}")
                lines.append("")

                if plan.weaknesses:
                    lines.append("#### 弱点分析")
                    lines.append("")
                    for w in plan.weaknesses:
                        lines.append(
                            f"- **{w.get('area', '')}**: {w.get('detail', '')}"
                        )
                    lines.append("")

                if plan.copy_actions:
                    lines.append("#### 跟进动作")
                    lines.append("")
                    for a in plan.copy_actions:
                        lines.append(f"- {a}")
                    lines.append("")

                if plan.differentiate_actions:
                    lines.append("#### 差异化动作")
                    lines.append("")
                    for a in plan.differentiate_actions:
                        lines.append(f"- {a}")
                    lines.append("")

                if plan.phased_plan:
                    lines.append("#### 分阶段执行")
                    lines.append("")
                    lines.append("| 阶段 | 动作 | 时间 | 目标 |")
                    lines.append("|------|------|------|------|")
                    for phase in plan.phased_plan:
                        lines.append(
                            f"| {phase.get('phase', '')} "
                            f"| {phase.get('action', '')} "
                            f"| {phase.get('timeline', '')} "
                            f"| {phase.get('goal', '')} |"
                        )
                    lines.append("")
        else:
            lines.append("（暂无攻击计划）")
            lines.append("")

        return "\n".join(lines)

    def generate_optimization_daily(
        self,
        actions: list[OptimizationAction],
        date: str = "",
    ) -> str:
        report_date = date or datetime.now().strftime("%Y-%m-%d")
        lines: list[str] = []
        lines.append(f"# 每日优化清单 - {report_date}")
        lines.append("")

        priority_order = ["高", "中", "低"]
        grouped: dict[str, list[OptimizationAction]] = {p: [] for p in priority_order}
        for action in actions:
            label = action.priority if action.priority in grouped else "低"
            grouped[label].append(action)

        header = "| 操作 | 广告活动 | 关键词 | 当前值 | 建议值 | 原因 | 预计影响 |"
        separator = "|------|----------|--------|--------|--------|------|----------|"

        for priority_level in priority_order:
            items = grouped[priority_level]
            tag = (
                "高优先级"
                if priority_level == "高"
                else "中优先级" if priority_level == "中" else "低优先级"
            )
            lines.append(f"## {tag} ({len(items)} 项)")
            lines.append("")
            if items:
                lines.append(header)
                lines.append(separator)
                for a in items:
                    lines.append(
                        f"| {a.method} "
                        f"| {a.campaign} "
                        f"| {a.keyword} "
                        f"| {a.current_value} "
                        f"| {a.suggested_value} "
                        f"| {a.reason} "
                        f"| {a.estimated_impact} |"
                    )
            else:
                lines.append("（无）")
            lines.append("")

        return "\n".join(lines)

    def generate_full_pipeline(self, result: FullPipelineResult) -> str:
        lines: list[str] = []
        lines.append("# 完整运营报告")
        lines.append("")
        lines.append(f"生成时间: {result.generated_at}")
        lines.append("")

        if result.keyword_library:
            lines.append("---")
            lines.append("")
            lines.append(self.generate_keyword_report(result.keyword_library))

        if result.competitor_timelines:
            lines.append("---")
            lines.append("")
            for ct in result.competitor_timelines:
                lines.append(self.generate_competitor_report(ct))

        if result.market_phase:
            lines.append("---")
            lines.append("")
            lines.append("## 市场阶段")
            lines.append("")
            lines.append(f"- 当前阶段: **{result.market_phase.phase}**")
            lines.append(f"- 置信度: {result.market_phase.confidence:.1%}")
            lines.append(f"- 连续周数: {result.market_phase.consecutive_weeks}")
            lines.append(f"- 变化幅度: {result.market_phase.change_pct:.1%}")
            lines.append(f"- 建议动作: {result.market_phase.recommended_action}")
            lines.append("")

        if result.profit_model:
            lines.append("---")
            lines.append("")
            lines.append("## 利润模型")
            lines.append("")
            lines.append(f"| 指标 | 值 |")
            lines.append("|------|-----|")
            lines.append(f"| 售价 | ${result.profit_model.price:.2f} |")
            lines.append(f"| 产品成本 | ${result.profit_model.product_cost:.2f} |")
            lines.append(f"| FBA费用 | ${result.profit_model.fba_fee:.2f} |")
            lines.append(f"| 佣金 | ${result.profit_model.commission:.2f} |")
            lines.append(f"| 广告费 | ${result.profit_model.ad_spend:.2f} |")
            lines.append(f"| 退货损失 | ${result.profit_model.return_loss:.2f} |")
            lines.append(f"| 净利润 | ${result.profit_model.net_profit:.2f} |")
            lines.append(f"| 净利率 | {result.profit_model.net_margin:.1%} |")
            lines.append(f"| 目标利润率 | {result.profit_model.target_margin:.1%} |")
            lines.append(
                f"| 可接受广告支出 | ${result.profit_model.acceptable_ad_spend:.2f} |"
            )
            lines.append(f"| 目标ACoS | {result.profit_model.target_acos:.1%} |")
            lines.append("")

        if result.ad_architecture and result.budget_plan:
            lines.append("---")
            lines.append("")
            lines.append(
                self.generate_strategy_report(
                    result.ad_architecture,
                    result.budget_plan,
                    result.risk_alerts,
                    result.attack_plans,
                )
            )

        if result.optimization_actions:
            lines.append("---")
            lines.append("")
            lines.append(
                self.generate_optimization_daily(result.optimization_actions)
            )

        return "\n".join(lines)

    def save(self, content: str, filename: str, reports_dir: str = None) -> str:
        target_dir = reports_dir or os.path.join("data", "reports")
        os.makedirs(target_dir, exist_ok=True)
        filepath = os.path.join(target_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath
