from __future__ import annotations

from datetime import datetime

from src.data_layer.models import FullPipelineResult


class MarkdownReportGenerator:

    def generate(self, result: FullPipelineResult) -> str:
        parts: list[str] = []
        parts.append("# AMZ Pipeline Report")
        parts.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        if result.keyword_library:
            kl = result.keyword_library
            parts.append("## Keyword Library")
            parts.append(f"- Own ASIN: {kl.own_asin}")
            parts.append(f"- Total Keywords: {kl.total_keywords}")
            parts.append(f"- Traffic Structure: {kl.traffic_structure}")
            parts.append(f"- Category CVR: {kl.category_cvr}")
            parts.append(f"- Competitor ASINs: {', '.join(kl.competitor_asins)}")
            parts.append(f"- Negation List: {len(kl.negation_list)} keywords")

            priority_counts: dict[str, int] = {}
            for kw in kl.classified_keywords:
                priority_counts[kw.priority] = priority_counts.get(kw.priority, 0) + 1
            if priority_counts:
                parts.append("\n### Priority Distribution")
                for p, c in sorted(priority_counts.items(), key=lambda x: -x[1]):
                    parts.append(f"- {p}: {c}")
            parts.append("")

        if result.market_phase:
            mp = result.market_phase
            parts.append("## Market Phase")
            phase_label = {"up": "上升期", "down": "下行期", "stable": "稳定期"}.get(mp.phase, mp.phase)
            parts.append(f"- Phase: **{phase_label}**")
            parts.append(f"- Confidence: {mp.confidence:.0%}")
            parts.append(f"- Consecutive Weeks: {mp.consecutive_weeks}")
            parts.append(f"- Change: {mp.change_pct:+.1f}%")
            parts.append(f"- Recommended Action: {mp.recommended_action}")
            parts.append("")

        if result.competitor_timelines:
            parts.append("## Competitor Timelines")
            for tl in result.competitor_timelines:
                parts.append(f"\n### ASIN: {tl.asin}")
                parts.append(f"- Total Weeks: {tl.total_weeks}")
                parts.append(f"- Phase Summary: {tl.phase_summary}")
                if tl.weekly_events:
                    parts.append("\n| Week | Keywords | Price | BSR | Reviews | Decision |")
                    parts.append("|------|----------|-------|-----|---------|----------|")
                    for ev in tl.weekly_events[:10]:
                        parts.append(
                            f"| {ev.week_label} | {ev.ad_keyword_count} | "
                            f"${ev.price:.2f} | {ev.bsr_category} | "
                            f"{ev.reviews} ({ev.review_change}) | {ev.key_decision} |"
                        )
            parts.append("")

        if result.ad_architecture:
            arch = result.ad_architecture
            parts.append("## Ad Architecture")
            parts.append(f"- Name: {arch.name}")
            parts.append(f"- Stage: {arch.stage}")
            parts.append(f"- Push Strategy: {arch.push_strategy}")
            parts.append(f"- Bidding: {arch.bidding_strategy}")
            parts.append(f"- Top Position Bid: {arch.top_position_bid_pct}%")
            parts.append(f"- Rest Position Bid: {arch.rest_position_bid_pct}%")
            if arch.campaigns:
                parts.append("\n### Campaigns")
                for i, camp in enumerate(arch.campaigns, 1):
                    parts.append(f"{i}. **{camp.get('type', '')} {camp.get('targeting', '')}** - Budget ratio: {camp.get('budget_ratio', 0):.0%}")
            parts.append("")

        if result.budget_plan:
            bp = result.budget_plan
            parts.append("## Budget Plan")
            parts.append(f"- Stage: {bp.stage}")
            parts.append(f"- Revenue: ${bp.revenue:,.2f}")
            parts.append(f"- Ad Spend Ratio: {bp.ad_spend_ratio:.1%}")
            parts.append(f"- Ad Spend Amount: ${bp.ad_spend_amount:,.2f}")
            parts.append(f"- Target ACOS: {bp.target_acos:.1%}")
            if bp.allocations:
                parts.append("\n### Allocations")
                for key, val in bp.allocations.items():
                    parts.append(f"- {key}: ${val:,.2f}")
            parts.append("")

        if result.risk_alerts:
            parts.append("## Risk Alerts")
            for alert in result.risk_alerts:
                parts.append(f"- **[{alert.severity}]** {alert.risk_type}: {alert.action}")
            parts.append("")

        if result.optimization_actions:
            parts.append("## Optimization Actions")
            priority_order = {"高": 0, "中": 1, "低": 2}
            sorted_actions = sorted(result.optimization_actions, key=lambda a: priority_order.get(a.priority, 99))
            parts.append("\n| Priority | Method | Campaign | Keyword | Current | Suggested | Reason |")
            parts.append("|----------|--------|----------|---------|---------|-----------|--------|")
            for act in sorted_actions[:20]:
                kw_display = act.keyword[:20] if act.keyword else "-"
                parts.append(
                    f"| {act.priority} | {act.method} | {act.campaign[:20]} | "
                    f"{kw_display} | {act.current_value} | {act.suggested_value} | {act.reason[:40]} |"
                )
            if len(sorted_actions) > 20:
                parts.append(f"\n... and {len(sorted_actions) - 20} more actions")
            parts.append("")

        if result.attack_plans:
            parts.append("## Attack Plans")
            for plan in result.attack_plans:
                parts.append(f"\n### vs {plan.competitor_asin}")
                if plan.weaknesses:
                    parts.append("**Weaknesses:**")
                    for w in plan.weaknesses:
                        parts.append(f"- {w.get('type', '')}: {w.get('detail', '')}")
                if plan.copy_actions:
                    parts.append("\n**Copy Actions:**")
                    for a in plan.copy_actions[:5]:
                        parts.append(f"- {a}")
                if plan.differentiate_actions:
                    parts.append("\n**Differentiate Actions:**")
                    for a in plan.differentiate_actions[:5]:
                        parts.append(f"- {a}")
                if plan.phased_plan:
                    parts.append("\n**Phased Plan:**")
                    for phase in plan.phased_plan:
                        parts.append(f"- {phase.get('phase', '')}: {phase.get('goal', '')}")
            parts.append("")

        return "\n".join(parts)
