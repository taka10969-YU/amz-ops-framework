from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from src.data_layer.models import AdCampaignRecord, OptimizationAction
from config.settings import DEFAULT_THRESHOLDS


class Optimizer:

    def budget_lean(
        self,
        campaigns: list[AdCampaignRecord],
        daily_budget: float = 0,
        target_cpa: float = 0,
    ) -> list[OptimizationAction]:
        if not campaigns:
            return []

        grouped: dict[str, list[AdCampaignRecord]] = defaultdict(list)
        for c in campaigns:
            grouped[c.campaign_name].append(c)

        campaign_metrics: list[tuple[str, float, float, float]] = []
        for name, records in grouped.items():
            total_spend = sum(r.spend for r in records)
            total_orders = sum(r.orders_7d or 0 for r in records)
            cpa = total_spend / total_orders if total_orders > 0 else float("inf")
            campaign_metrics.append((name, total_spend, total_orders, cpa))

        campaign_metrics.sort(key=lambda x: x[3])
        actions: list[OptimizationAction] = []

        for rank, (name, spend, orders, cpa) in enumerate(campaign_metrics):
            if spend == 0:
                continue

            if target_cpa <= 0:
                continue

            if cpa <= target_cpa:
                increase_frac = max(0.10, (len(campaign_metrics) - rank) / len(campaign_metrics) * 0.50)
                new_budget = round(spend * (1 + increase_frac), 2)
                needs_approval = (
                    daily_budget > 0
                    and (new_budget - spend) > 0.30 * daily_budget
                )
                suffix = " [需审批:单次调整>30%日预算]" if needs_approval else ""
                actions.append(
                    OptimizationAction(
                        method="预算倾斜法",
                        campaign=name,
                        keyword="",
                        current_value=f"${spend:.2f}",
                        suggested_value=f"${new_budget:.2f}",
                        reason=f"CPA ${cpa:.2f} < 目标 ${target_cpa:.2f}, 提升{increase_frac:.0%}预算{suffix}",
                        priority="高" if not needs_approval else "中",
                        estimated_impact=f"预计增加{increase_frac:.0%}有效流量",
                    )
                )
            else:
                decrease_frac = min(0.30, (cpa - target_cpa) / target_cpa * 0.10)
                new_budget = round(spend * (1 - decrease_frac), 2)
                actions.append(
                    OptimizationAction(
                        method="预算倾斜法",
                        campaign=name,
                        keyword="",
                        current_value=f"${spend:.2f}",
                        suggested_value=f"${new_budget:.2f}",
                        reason=f"CPA ${cpa:.2f} > 目标 ${target_cpa:.2f}, 减少{decrease_frac:.0%}预算",
                        priority="高",
                        estimated_impact=f"预计节省{decrease_frac:.0%}无效花费",
                    )
                )

        priority_order = {"高": 0, "中": 1, "低": 2}
        actions.sort(key=lambda a: priority_order.get(a.priority, 99))
        return actions

    def time_lean(self, campaigns: list[AdCampaignRecord]) -> list[OptimizationAction]:
        if not campaigns:
            return []

        hourly: dict[int, dict[str, float]] = defaultdict(lambda: {"spend": 0.0, "orders": 0.0, "records": []})
        for c in campaigns:
            try:
                dt = datetime.fromisoformat(c.date)
                hour = dt.hour
            except (ValueError, TypeError):
                continue
            hourly[hour]["spend"] += c.spend
            hourly[hour]["orders"] += c.orders_7d or 0
            hourly[hour]["records"].append(c)

        if not hourly:
            return []

        sorted_hours = sorted(hourly.keys())
        order_rates = {h: hourly[h]["orders"] for h in sorted_hours}
        max_orders = max(order_rates.values()) if order_rates else 0
        if max_orders == 0:
            return []

        growth_start = None
        decline_start = None
        for i in range(1, len(sorted_hours)):
            prev_h = sorted_hours[i - 1]
            curr_h = sorted_hours[i]
            if order_rates[curr_h] > order_rates[prev_h] and growth_start is None:
                growth_start = curr_h
            if order_rates[curr_h] < order_rates[prev_h] and growth_start is not None and decline_start is None:
                decline_start = curr_h

        actions: list[OptimizationAction] = []

        for h in sorted_hours:
            data = hourly[h]
            total_spend = data["spend"]
            total_orders = data["orders"]
            if total_spend <= 0:
                continue

            if growth_start is not None and h < growth_start:
                target_budget = round(total_spend * 1.20, 2)
                actions.append(
                    OptimizationAction(
                        method="时间倾斜法",
                        campaign=",".join(set(r.campaign_name for r in data["records"] if r.campaign_name)),
                        keyword=f"时段{h:02d}:00",
                        current_value=f"${total_spend:.2f}",
                        suggested_value=f"${target_budget:.2f}",
                        reason=f"订单增长前时段(h{h:02d}), 设定目标预算",
                        priority="中",
                        estimated_impact="提前布局订单高峰期",
                    )
                )
            elif decline_start is not None and h >= decline_start:
                actions.append(
                    OptimizationAction(
                        method="时间倾斜法",
                        campaign=",".join(set(r.campaign_name for r in data["records"] if r.campaign_name)),
                        keyword=f"时段{h:02d}:00",
                        current_value=f"${total_spend:.2f}",
                        suggested_value="$1.00",
                        reason=f"订单下降后时段(h{h:02d}), 降至$1",
                        priority="中",
                        estimated_impact="减少无效时段花费",
                    )
                )

        priority_order = {"高": 0, "中": 1, "低": 2}
        actions.sort(key=lambda a: priority_order.get(a.priority, 99))
        return actions

    def position_lean(self, campaigns: list[AdCampaignRecord]) -> list[OptimizationAction]:
        if not campaigns:
            return []

        position_data: dict[str, dict[str, float]] = defaultdict(lambda: {"spend": 0.0, "sales": 0.0})
        for c in campaigns:
            pos = self._classify_position(c.targeting)
            position_data[pos]["spend"] += c.spend
            position_data[pos]["sales"] += c.sales_7d or 0

        position_acos: dict[str, float] = {}
        for pos, data in position_data.items():
            if data["sales"] > 0:
                position_acos[pos] = data["spend"] / data["sales"]
            elif data["spend"] > 0:
                position_acos[pos] = float("inf")

        if not position_acos:
            return []

        best_position = min(position_acos, key=position_acos.get)
        best_acos = position_acos[best_position]

        actions: list[OptimizationAction] = []
        for pos, acos in position_acos.items():
            if pos == best_position:
                multiplier = 1.20
                actions.append(
                    OptimizationAction(
                        method="位置倾斜法",
                        campaign="",
                        keyword="",
                        current_value=f"{pos} ACOS={acos:.2%}" if acos != float("inf") else f"{pos} ACOS=N/A",
                        suggested_value=f"竞价倍数+{int((multiplier - 1) * 100)}%",
                        reason=f"最优位置{pos}(ACOS={acos:.2%}), 提升竞价倍数",
                        priority="低",
                        estimated_impact="增加最优位置展现",
                    )
                )
            else:
                ratio = acos / best_acos if best_acos > 0 else float("inf")
                if ratio > 2.0:
                    multiplier = 0.80
                    actions.append(
                        OptimizationAction(
                            method="位置倾斜法",
                            campaign="",
                            keyword="",
                            current_value=f"{pos} ACOS={acos:.2%}" if acos != float("inf") else f"{pos} ACOS=N/A",
                            suggested_value=f"竞价倍数{int((multiplier - 1) * 100)}%",
                            reason=f"位置{pos}ACOS({acos:.2%})远高于最优({best_acos:.2%}), 降低竞价",
                            priority="低",
                            estimated_impact="减少低效位置花费",
                        )
                    )

        return actions

    def reduce_waste(
        self,
        campaigns: list[AdCampaignRecord],
        category_cvr: float = 0,
    ) -> list[OptimizationAction]:
        if not campaigns:
            return []

        term_data: dict[str, dict[str, float]] = defaultdict(
            lambda: {"clicks": 0, "orders": 0, "spend": 0.0, "match_type": ""}
        )
        for c in campaigns:
            if not c.customer_search_term:
                continue
            key = (c.customer_search_term, c.campaign_name)
            term_data[key]["clicks"] += c.clicks
            term_data[key]["orders"] += c.orders_7d or 0
            term_data[key]["spend"] += c.spend
            if c.match_type:
                term_data[key]["match_type"] = c.match_type

        actions: list[OptimizationAction] = []

        for (term, campaign), data in term_data.items():
            if data["clicks"] == 0:
                continue

            if data["orders"] == 0 and data["spend"] > 0:
                is_exact_big = data["match_type"].lower() == "exact" and data["clicks"] >= 50

                if data["clicks"] < 10:
                    actions.append(
                        OptimizationAction(
                            method="无效花费降低法",
                            campaign=campaign,
                            keyword=term,
                            current_value=f"{data['clicks']}点击 0订单",
                            suggested_value="精准否定",
                            reason=f"不相关搜索词, {data['clicks']}点击无转化",
                            priority="高",
                            estimated_impact=f"节省${data['spend']:.2f}/周期",
                        )
                    )
                elif data["clicks"] >= 10 and category_cvr > 0:
                    cvr_threshold_clicks = category_cvr * 2
                    if data["clicks"] >= cvr_threshold_clicks and not is_exact_big:
                        actions.append(
                            OptimizationAction(
                                method="无效花费降低法",
                                campaign=campaign,
                                keyword=term,
                                current_value=f"{data['clicks']}点击 0订单",
                                suggested_value="精准否定",
                                reason=f"点击{data['clicks']}>类目CVR*2({cvr_threshold_clicks:.0f})无转化",
                                priority="高",
                                estimated_impact=f"节省${data['spend']:.2f}/周期",
                            )
                        )

        actions.sort(key=lambda a: float(a.estimated_impact.replace("节省$", "").replace("/周期", "") or 0), reverse=True)
        return actions

    def optimize_cpc(
        self,
        campaigns: list[AdCampaignRecord],
        self_ctr: float = 0,
        market_ctr: float = 0,
    ) -> list[OptimizationAction]:
        if not campaigns:
            return []

        if self_ctr <= market_ctr:
            return []

        step_small = DEFAULT_THRESHOLDS["cpc_decrease_step_small"]
        step_medium = DEFAULT_THRESHOLDS["cpc_decrease_step_medium"]
        step_large = DEFAULT_THRESHOLDS["cpc_decrease_step_large"]

        grouped: dict[str, list[AdCampaignRecord]] = defaultdict(list)
        for c in campaigns:
            if c.cpc > 0:
                grouped[c.campaign_name].append(c)

        actions: list[OptimizationAction] = []
        for name, records in grouped.items():
            avg_cpc = sum(r.cpc for r in records) / len(records)

            if avg_cpc <= 0.9:
                decrease = step_small
            elif avg_cpc <= 4.0:
                decrease = step_medium
            else:
                decrease = step_large

            new_cpc = round(avg_cpc - decrease, 2)
            if new_cpc <= 0:
                continue

            actions.append(
                OptimizationAction(
                    method="CPC优化法",
                    campaign=name,
                    keyword="",
                    current_value=f"${avg_cpc:.2f}",
                    suggested_value=f"${new_cpc:.2f}",
                    reason=f"自身CTR({self_ctr:.2%})>市场({market_ctr:.2%}), 可降CPC",
                    priority="中",
                    estimated_impact=f"降低单次点击成本${decrease:.2f}, 需监控广告位不下降",
                )
            )

        return actions

    def ad_type_lean(self, campaigns: list[AdCampaignRecord]) -> list[OptimizationAction]:
        if not campaigns:
            return []

        keyword_type_data: dict[str, dict[str, list[AdCampaignRecord]]] = defaultdict(lambda: defaultdict(list))
        for c in campaigns:
            ad_type = self._classify_ad_type(c.campaign_name)
            keyword_type_data[c.customer_search_term][ad_type].append(c)

        actions: list[OptimizationAction] = []
        for keyword, type_records in keyword_type_data.items():
            if not keyword:
                continue

            type_acos: dict[str, float] = {}
            for ad_type, records in type_records.items():
                total_spend = sum(r.spend for r in records)
                total_sales = sum(r.sales_7d or 0 for r in records)
                if total_sales > 0:
                    type_acos[ad_type] = total_spend / total_sales
                elif total_spend > 0:
                    type_acos[ad_type] = float("inf")

            if len(type_acos) < 2:
                continue

            sp_acos = type_acos.get("SP")
            sbv_acos = type_acos.get("SBV")

            if sp_acos is not None and sbv_acos is not None:
                if sp_acos > sbv_acos * 1.5 and sbv_acos < float("inf"):
                    actions.append(
                        OptimizationAction(
                            method="广告类型倾斜法",
                            campaign=",".join(
                                r.campaign_name for r in type_records.get("SP", [])
                            ),
                            keyword=keyword,
                            current_value=f"SP ACOS={sp_acos:.2%}",
                            suggested_value="转SBV投放",
                            reason=f"SP ACOS({sp_acos:.2%})远高于SBV({sbv_acos:.2%}), 切换至SBV",
                            priority="中",
                            estimated_impact="提升同关键词投放效率",
                        )
                    )

        return actions

    def optimize_target(self, search_query_data: list[dict]) -> list[OptimizationAction]:
        if not search_query_data:
            return []

        scored: list[tuple[dict, float]] = []
        for item in search_query_data:
            ctr = item.get("ctr", 0) or 0
            cvr = item.get("cvr", 0) or 0
            clicks = item.get("clicks", 0) or 0
            adds = item.get("adds_to_cart", 0) or 0
            score = ctr * 0.4 + cvr * 0.6
            scored.append((item, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        actions: list[OptimizationAction] = []
        if not scored:
            return actions

        best_item, best_score = scored[0]
        best_asin = best_item.get("asin", "")
        best_keyword = best_item.get("search_term", "")

        if best_score > 0:
            actions.append(
                OptimizationAction(
                    method="投流对象优化法",
                    campaign="",
                    keyword=best_keyword,
                    current_value=f"当前投放ASIN: {best_asin}",
                    suggested_value=f"最优CTR+CVR ASIN: {best_asin}",
                    reason=f"综合CTR+CVR得分最高({best_score:.4f}), 优先投流",
                    priority="高",
                    estimated_impact="聚焦最优产品提升整体转化",
                )
            )

        for item, _ in scored:
            keyword = item.get("search_term", "")
            clicks = item.get("clicks", 0) or 0
            adds = item.get("adds_to_cart", 0) or 0
            targeted = item.get("is_targeted", False)

            if targeted:
                continue
            if clicks >= 100 or adds >= 10:
                actions.append(
                    OptimizationAction(
                        method="投流对象优化法",
                        campaign="",
                        keyword=keyword,
                        current_value="未投放",
                        suggested_value="添加关键词投放",
                        reason=f"未投放但周点击{clicks}次/周加购{adds}次, 需添加定向",
                        priority="高",
                        estimated_impact="捕获高潜力搜索词流量",
                    )
                )

        return actions

    def optimize_targeted(self, keyword_rank_data: list[dict]) -> list[OptimizationAction]:
        if not keyword_rank_data:
            return []

        actions: list[OptimizationAction] = []
        for item in keyword_rank_data:
            keyword = item.get("keyword", "")
            natural_page = item.get("natural_page", 0) or 0
            ad_page = item.get("ad_page", 0) or 0
            orders = item.get("orders", 0) or 0
            ctr = item.get("ctr", 0) or 0

            if 1 <= natural_page <= 3 and ad_page == 0 and orders > 0 and ctr > 0:
                actions.append(
                    OptimizationAction(
                        method="被投流对象优化法",
                        campaign="",
                        keyword=keyword,
                        current_value=f"自然页{natural_page}页, 无广告位",
                        suggested_value=f"添加关键词精准投放",
                        reason=f"自然排名{natural_page}页有订单且CTR好, 无广告位需补投",
                        priority="中",
                        estimated_impact="利用已有自然排名优势增加广告展现",
                    )
                )

        return actions

    def competitor_strike(self, competitor_weaknesses: list[dict]) -> list[OptimizationAction]:
        if not competitor_weaknesses:
            return []

        actions: list[OptimizationAction] = []
        for weakness in competitor_weaknesses:
            competitor_asin = weakness.get("competitor_asin", "")
            w_type = weakness.get("type", "")
            detail = weakness.get("detail", "")

            if w_type == "poor_visuals":
                actions.append(
                    OptimizationAction(
                        method="竞品劣势打击法",
                        campaign=competitor_asin,
                        keyword="",
                        current_value="竞品主图/A+劣势",
                        suggested_value="优化我方主图/A+内容",
                        reason=f"竞品{competitor_asin}视觉差({detail}), 强化我方视觉优势",
                        priority="高",
                        estimated_impact="提升点击率和转化率",
                    )
                )
            elif w_type == "low_ad_spend":
                actions.append(
                    OptimizationAction(
                        method="竞品劣势打击法",
                        campaign=competitor_asin,
                        keyword="",
                        current_value="竞品广告投入低",
                        suggested_value="增加我方广告抢占位",
                        reason=f"竞品{competitor_asin}广告投入少({detail}), 抢占广告位",
                        priority="高",
                        estimated_impact="获取竞品放弃的广告流量",
                    )
                )
            elif w_type == "low_rating":
                their_rating = weakness.get("their_rating", 0)
                our_rating = weakness.get("our_rating", 0)
                actions.append(
                    OptimizationAction(
                        method="竞品劣势打击法",
                        campaign=competitor_asin,
                        keyword="",
                        current_value=f"竞品评分{their_rating}",
                        suggested_value=f"突出我方评分{our_rating}优势",
                        reason=f"竞品评分低({their_rating}), 我方({our_rating})有优势",
                        priority="中",
                        estimated_impact="强化品质信任感",
                    )
                )
            elif w_type == "refurbished":
                actions.append(
                    OptimizationAction(
                        method="竞品劣势打击法",
                        campaign=competitor_asin,
                        keyword="",
                        current_value="竞品为翻新/二手",
                        suggested_value="通过RAV举报违规",
                        reason=f"竞品{competitor_asin}疑似翻新({detail}), RAV举报",
                        priority="高",
                        estimated_impact="可能移除竞品listing",
                    )
                )
            elif w_type == "single_keyword_dependency":
                core_keyword = weakness.get("core_keyword", "")
                actions.append(
                    OptimizationAction(
                        method="竞品劣势打击法",
                        campaign=competitor_asin,
                        keyword=core_keyword,
                        current_value=f"竞品依赖核心词{core_keyword}",
                        suggested_value=f"抢夺{core_keyword}自然位",
                        reason=f"竞品单词依赖({core_keyword}), 攻占其核心词自然位",
                        priority="高",
                        estimated_impact="削弱竞品核心流量来源",
                    )
                )

        return actions

    def daily_sop(
        self,
        campaigns: list[AdCampaignRecord],
        category_cvr: float = 0,
        self_ctr: float = 0,
        market_ctr: float = 0,
        daily_budget: float = 0,
        target_cpa: float = 0,
    ) -> list[OptimizationAction]:
        all_actions: list[OptimizationAction] = []

        budget_actions = self.budget_lean(campaigns, daily_budget, target_cpa)
        for a in budget_actions:
            a.priority = "高"
        all_actions.extend(budget_actions)

        waste_actions = self.reduce_waste(campaigns, category_cvr)
        for a in waste_actions:
            a.priority = "高"
        all_actions.extend(waste_actions)

        time_actions = self.time_lean(campaigns)
        for a in time_actions:
            a.priority = "中"
        all_actions.extend(time_actions)

        position_actions = self.position_lean(campaigns)
        for a in position_actions:
            a.priority = "低"
        all_actions.extend(position_actions)

        priority_order = {"高": 0, "中": 1, "低": 2}
        all_actions.sort(key=lambda a: priority_order.get(a.priority, 99))
        return all_actions

    @staticmethod
    def _classify_position(targeting: str) -> str:
        if not targeting:
            return "unknown"
        t = targeting.lower()
        if "top" in t:
            return "top"
        if "rest" in t:
            return "rest"
        if "product" in t or "page" in t:
            return "product_page"
        return "unknown"

    @staticmethod
    def _classify_ad_type(campaign_name: str) -> str:
        if not campaign_name:
            return "SP"
        cn = campaign_name.upper()
        if "SBV" in cn or "SPONSORED BRAND" in cn:
            return "SBV"
        if "SB" in cn:
            return "SB"
        if "SD" in cn:
            return "SD"
        return "SP"
