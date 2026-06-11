from __future__ import annotations

from src.data_layer.models import (
    AttackPlan,
    CompetitorKeyword,
    KeywordClassified,
    KeepaDailyRecord,
)
from config.settings import DEFAULT_THRESHOLDS


class AttackPlanner:

    def generate_plan(
        self,
        own_asin: str,
        competitor_asin: str,
        classified_keywords: list[KeywordClassified],
        competitor_ad_data: list[CompetitorKeyword] | None = None,
        competitor_keepa: list[KeepaDailyRecord] | None = None,
    ) -> AttackPlan:
        if not classified_keywords:
            return AttackPlan(competitor_asin=competitor_asin)

        own_keywords = {k.keyword_text for k in classified_keywords}
        comp_keywords: list[CompetitorKeyword] = competitor_ad_data or []

        comp_top_kw = sorted(
            comp_keywords,
            key=lambda c: c.listing_traffic_share,
            reverse=True,
        )[:10]

        gaps = [c for c in comp_top_kw if c.keyword not in own_keywords]

        weaknesses = self._analyze_weaknesses(comp_top_kw, competitor_keepa or [])

        copy_actions: list[str] = []
        for ck in comp_top_kw[:5]:
            copy_actions.append(f"复制竞品已验证词: {ck.keyword} (流量占比{ck.listing_traffic_share:.1%})")

        differentiate_actions: list[str] = []
        for g in gaps[:5]:
            differentiate_actions.append(f"竞品有覆盖但我方缺失词: {g.keyword}")

        uncovered = [
            k for k in classified_keywords
            if k.priority in ("高", "中") and k.traffic_monopoly < DEFAULT_THRESHOLDS.get("monopoly_traffic_high", 0.50)
        ]
        if uncovered:
            differentiate_actions.append(f"低垄断高机会词共{len(uncovered)}个，优先覆盖")

        phased_plan = self._build_phases(
            comp_top_kw, gaps, uncovered, competitor_keepa or []
        )

        return AttackPlan(
            competitor_asin=competitor_asin,
            weaknesses=weaknesses,
            copy_actions=copy_actions,
            differentiate_actions=differentiate_actions,
            phased_plan=phased_plan,
        )

    def _analyze_weaknesses(
        self,
        comp_top_kw: list[CompetitorKeyword],
        keepa_data: list[KeepaDailyRecord],
    ) -> list[dict]:
        weaknesses: list[dict] = []

        single_kw_dependent = any(
            ck.listing_traffic_share > 0.30 for ck in comp_top_kw
        )
        if single_kw_dependent:
            top = max(comp_top_kw, key=lambda c: c.listing_traffic_share)
            weaknesses.append({
                "type": "流量集中",
                "detail": f"竞品核心词{top.keyword}流量占比{top.listing_traffic_share:.1%}，依赖度高",
                "exploit": "抢占该核心词，切断其主要流量来源",
            })

        if keepa_data and len(keepa_data) >= 7:
            recent = keepa_data[-7:]
            ratings = [r.rating for r in recent if r.rating > 0]
            if ratings and max(ratings) - min(ratings) >= 0.3:
                weaknesses.append({
                    "type": "评分波动",
                    "detail": f"近7天评分波动{max(ratings)-min(ratings):.1f}，产品质量不稳",
                    "exploit": "强化自身好评、突出品质卖点",
                })

            prices = [r.buybox_price for r in recent if r.buybox_price > 0]
            if prices and len(prices) >= 3:
                price_trend = prices[-1] - prices[0]
                if price_trend < 0:
                    weaknesses.append({
                        "type": "价格下行",
                        "detail": f"竞品7天内降价{abs(price_trend):.2f}，可能利润承压",
                        "exploit": "保持价格稳定，以利润优势长期竞争",
                    })

        low_variant = [ck for ck in comp_top_kw if ck.variant_count <= 1]
        if low_variant:
            weaknesses.append({
                "type": "变体单一",
                "detail": f"竞品在{len(low_variant)}个核心词上变体覆盖少",
                "exploit": "利用多变体抢占广告位",
            })

        return weaknesses

    def _build_phases(
        self,
        comp_top_kw: list[CompetitorKeyword],
        gaps: list[CompetitorKeyword],
        uncovered: list[KeywordClassified],
        keepa_data: list[KeepaDailyRecord],
    ) -> list[dict]:
        short_keywords = [ck.keyword for ck in comp_top_kw[:3]] + [g.keyword for g in gaps[:2]]

        mid_keywords = [g.keyword for g in gaps[2:6]]
        mid_keywords += [k.keyword_text for k in uncovered[:5]]

        long_keywords = [k.keyword_text for k in uncovered[5:15]]

        short_plan = {
            "phase": "短期 (1-3月)",
            "goal": "复制验证策略，攻击竞品最弱环节",
            "actions": [
                f"SP精准投放竞品验证词: {', '.join(short_keywords[:3])}",
                f"SBV品牌视频投放核心词抢占头部",
                "商品投放定向竞品ASIN，抢夺关联流量",
            ],
            "keywords": short_keywords,
            "budget_ratio": 0.50,
        }

        mid_plan = {
            "phase": "中期 (3-6月)",
            "goal": "扩展未覆盖词，差异化广告类型",
            "actions": [
                f"扩展SP词组覆盖新词: {', '.join(mid_keywords[:3])}",
                "SD受众再营销投放，覆盖竞品购买人群",
                "增加SB品牌旗舰店引流",
            ],
            "keywords": mid_keywords,
            "budget_ratio": 0.30,
        }

        long_plan = {
            "phase": "长期 (6-12月)",
            "goal": "构建关键词护城河，降低广告依赖",
            "actions": [
                f"长尾词精准覆盖共{len(long_keywords)}个",
                "优化自然排名，降低核心词CPC依赖",
                "建立品牌搜索量，提升品牌词自然流量",
            ],
            "keywords": long_keywords,
            "budget_ratio": 0.20,
        }

        return [short_plan, mid_plan, long_plan]
