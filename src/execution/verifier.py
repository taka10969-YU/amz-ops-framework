from __future__ import annotations

from src.data_layer.models import AdCampaignRecord
from config.settings import DEFAULT_THRESHOLDS


class Verifier:

    def verify_push(self, keyword_results: list[dict]) -> list[dict]:
        if not keyword_results:
            return []

        target_days = DEFAULT_THRESHOLDS.get("push_days_target", 8)
        results: list[dict] = []

        for item in keyword_results:
            keyword = item.get("keyword", "")
            days_elapsed = item.get("days_elapsed", 0) or 0
            current_page = item.get("current_page", 0) or 0
            target_page = item.get("target_page", 3) or 3
            budget_spent = item.get("budget_spent", 0) or 0
            orders = item.get("orders", 0) or 0

            achieved = 1 <= current_page <= target_page
            within_time = days_elapsed <= target_days

            status = "成功"
            suggestion = ""

            if achieved and within_time:
                status = "成功"
                suggestion = "已达标，保持当前策略"
            elif achieved and not within_time:
                status = "延迟成功"
                suggestion = "虽达目标但超时，检查是否可优化速度"
            elif not achieved and within_time:
                status = "进行中"
                suggestion = "仍在目标时间内，继续当前策略"
            elif not achieved and days_elapsed > target_days * 1.5:
                status = "失败"
                suggestion = "超过目标时间未达标，建议换词或增加预算"
            else:
                status = "待定"
                suggestion = "接近目标时间上限，密切观察"

            results.append(
                {
                    "keyword": keyword,
                    "days_elapsed": days_elapsed,
                    "target_days": target_days,
                    "current_page": current_page,
                    "target_page": target_page,
                    "achieved": achieved,
                    "status": status,
                    "budget_spent": budget_spent,
                    "orders": orders,
                    "suggestion": suggestion,
                }
            )

        results.sort(key=lambda r: (0 if r["achieved"] else 1, r["days_elapsed"]))
        return results

    def generate_review(self, period: str, data: dict) -> dict:
        if not data:
            return {"period": period, "error": "无数据"}

        if period == "daily":
            return self._daily_review(data)
        elif period == "weekly":
            return self._weekly_review(data)
        elif period == "monthly":
            return self._monthly_review(data)
        elif period == "quarterly":
            return self._quarterly_review(data)
        else:
            return {"period": period, "error": f"未知周期: {period}"}

    def when_not_to_act(self, state: dict) -> list[str]:
        if not state:
            return []

        reasons: list[str] = []

        ctr = state.get("ctr", 0) or 0
        cvr = state.get("cvr", 0) or 0
        track_avg_ctr = state.get("track_avg_ctr", 0) or 0
        track_avg_cvr = state.get("track_avg_cvr", 0) or 0
        if ctr < track_avg_ctr and cvr < track_avg_cvr:
            reasons.append("CTR+CVR均低于赛道均值，产品竞争力不足，不宜加大投放")

        aba_decline_weeks = state.get("aba_decline_weeks", 0) or 0
        market_down_threshold = DEFAULT_THRESHOLDS.get("market_down_weeks", 2)
        if aba_decline_weeks >= market_down_threshold:
            reasons.append(f"市场下行(ABA连续{aba_decline_weeks}周下降)，不宜逆势加投")

        monopoly_traffic = state.get("monopoly_traffic_share", 0) or 0
        monopoly_sales = state.get("monopoly_sales_share", 0) or 0
        traffic_high = DEFAULT_THRESHOLDS.get("monopoly_traffic_high", 0.50)
        sales_high = DEFAULT_THRESHOLDS.get("monopoly_sales_high", 0.30)
        if monopoly_traffic > traffic_high and monopoly_sales > sales_high:
            reasons.append(f"品牌垄断(流量>{traffic_high:.0%}+销售额>{sales_high:.0%})，难以突破")

        net_margin = state.get("net_margin", 0) or 0
        ad_ratio = state.get("ad_ratio", 0) or 0
        if net_margin < 0.15 and ad_ratio > 0.15:
            reasons.append(f"利润率{net_margin:.0%}<15%且广告占比{ad_ratio:.0%}>15%，无加投空间")

        push_cost = state.get("push_cost", 0) or 0
        gross_profit = state.get("gross_profit", 0) or 0
        if gross_profit > 0 and push_cost > gross_profit * 3:
            reasons.append(f"推词成本({push_cost:.2f})>毛利*3({gross_profit * 3:.2f})，投入产出不合理")

        rating = state.get("rating", 0) or 0
        if rating < 4.0:
            reasons.append(f"评分{rating:.1f}<4.0，需先提升产品质量和评价")

        return reasons

    def check_negation_effectiveness(
        self,
        before_data: list[AdCampaignRecord],
        after_data: list[AdCampaignRecord],
    ) -> dict:
        if not before_data and not after_data:
            return {"error": "无数据"}

        before_waste = self._calculate_waste_ratio(before_data)
        after_waste = self._calculate_waste_ratio(after_data)

        before_total_spend = sum(r.spend for r in before_data)
        after_total_spend = sum(r.spend for r in after_data)

        before_total_orders = sum(r.orders_7d or 0 for r in before_data)
        after_total_orders = sum(r.orders_7d or 0 for r in after_data)

        before_total_clicks = sum(r.clicks for r in before_data)
        after_total_clicks = sum(r.clicks for r in after_data)

        waste_target = 0.15

        improvement = before_waste - after_waste
        effective = after_waste < waste_target

        return {
            "before_waste_ratio": round(before_waste, 4),
            "after_waste_ratio": round(after_waste, 4),
            "improvement": round(improvement, 4),
            "target_waste_ratio": waste_target,
            "effective": effective,
            "before_total_spend": round(before_total_spend, 2),
            "after_total_spend": round(after_total_spend, 2),
            "before_total_orders": before_total_orders,
            "after_total_orders": after_total_orders,
            "before_total_clicks": before_total_clicks,
            "after_total_clicks": after_total_clicks,
            "before_cpa": round(before_total_spend / before_total_orders, 2) if before_total_orders > 0 else None,
            "after_cpa": round(after_total_spend / after_total_orders, 2) if after_total_orders > 0 else None,
            "savings": round(before_total_spend * before_waste - after_total_spend * after_waste, 2),
        }

    def _daily_review(self, data: dict) -> dict:
        campaigns = data.get("campaigns", [])
        daily_budget = data.get("daily_budget", 0) or 0

        total_spend = sum(c.spend for c in campaigns) if campaigns else 0
        total_sales = sum(c.sales_7d or 0 for c in campaigns) if campaigns else 0
        total_orders = sum(c.orders_7d or 0 for c in campaigns) if campaigns else 0

        acos = total_spend / total_sales if total_sales > 0 else None
        cpa = total_spend / total_orders if total_orders > 0 else None
        budget_burn = total_spend / daily_budget if daily_budget > 0 else None

        return {
            "period": "daily",
            "metrics": {
                "total_spend": round(total_spend, 2),
                "total_sales": round(total_sales, 2),
                "total_orders": total_orders,
                "acos": round(acos, 4) if acos is not None else None,
                "cpa": round(cpa, 2) if cpa is not None else None,
                "budget_burn_rate": round(budget_burn, 4) if budget_burn is not None else None,
                "daily_budget": daily_budget,
            },
            "alerts": self._daily_alerts(acos, cpa, budget_burn, data),
        }

    def _weekly_review(self, data: dict) -> dict:
        keyword_positions = data.get("keyword_positions", [])
        ctr_trend = data.get("ctr_trend", [])

        position_changes: list[dict] = []
        for kp in keyword_positions:
            keyword = kp.get("keyword", "")
            start_pos = kp.get("start_position", 0) or 0
            end_pos = kp.get("end_position", 0) or 0
            change = end_pos - start_pos
            position_changes.append(
                {
                    "keyword": keyword,
                    "start_position": start_pos,
                    "end_position": end_pos,
                    "change": change,
                    "improved": change < 0,
                }
            )

        ctr_change = None
        if ctr_trend and len(ctr_trend) >= 2:
            ctr_change = ctr_trend[-1] - ctr_trend[0]

        return {
            "period": "weekly",
            "metrics": {
                "keyword_position_changes": position_changes,
                "keywords_improved": sum(1 for p in position_changes if p["improved"]),
                "keywords_declined": sum(1 for p in position_changes if not p["improved"]),
                "ctr_trend": ctr_trend,
                "ctr_change": round(ctr_change, 4) if ctr_change is not None else None,
            },
        }

    def _monthly_review(self, data: dict) -> dict:
        bsr_trend = data.get("bsr_trend", [])
        ad_spend_ratio = data.get("ad_spend_ratio", 0) or 0
        revenue = data.get("revenue", 0) or 0
        ad_spend = data.get("ad_spend", 0) or 0
        net_margin = data.get("net_margin", 0) or 0

        bsr_change = None
        if bsr_trend and len(bsr_trend) >= 2:
            bsr_change = bsr_trend[-1] - bsr_trend[0]

        return {
            "period": "monthly",
            "metrics": {
                "bsr_trend": bsr_trend,
                "bsr_change": bsr_change,
                "bsr_improved": bsr_change < 0 if bsr_change is not None else None,
                "ad_spend_ratio": round(ad_spend_ratio, 4),
                "revenue": round(revenue, 2),
                "ad_spend": round(ad_spend, 2),
                "net_margin": round(net_margin, 4),
            },
        }

    def _quarterly_review(self, data: dict) -> dict:
        brand_search_volume = data.get("brand_search_volume", 0) or 0
        brand_search_change = data.get("brand_search_change", 0) or 0
        repeat_purchase_rate = data.get("repeat_purchase_rate", 0) or 0
        market_share = data.get("market_share", 0) or 0
        market_share_change = data.get("market_share_change", 0) or 0

        return {
            "period": "quarterly",
            "metrics": {
                "brand_search_volume": brand_search_volume,
                "brand_search_change": round(brand_search_change, 4),
                "repeat_purchase_rate": round(repeat_purchase_rate, 4),
                "market_share": round(market_share, 4),
                "market_share_change": round(market_share_change, 4),
            },
        }

    @staticmethod
    def _daily_alerts(
        acos: float | None, cpa: float | None, budget_burn: float | None, data: dict
    ) -> list[str]:
        alerts: list[str] = []
        target_acos = data.get("target_acos", 0) or 0
        target_cpa = data.get("target_cpa", 0) or 0

        if acos is not None and target_acos > 0 and acos > target_acos:
            alerts.append(f"ACOS({acos:.2%})超出目标({target_acos:.2%})")
        if cpa is not None and target_cpa > 0 and cpa > target_cpa:
            alerts.append(f"CPA(${cpa:.2f})超出目标(${target_cpa:.2f})")
        if budget_burn is not None and budget_burn > 1.0:
            alerts.append(f"预算消耗率({budget_burn:.0%})超出日预算")
        elif budget_burn is not None and budget_burn < 0.5:
            alerts.append(f"预算消耗率({budget_burn:.0%})过低，预算可能设置过高")

        return alerts

    @staticmethod
    def _calculate_waste_ratio(campaigns: list[AdCampaignRecord]) -> float:
        if not campaigns:
            return 0.0

        total_spend = sum(c.spend for c in campaigns)
        if total_spend == 0:
            return 0.0

        waste_spend = 0.0
        for c in campaigns:
            orders = c.orders_7d or 0
            if orders == 0 and c.spend > 0:
                waste_spend += c.spend

        return waste_spend / total_spend
