from __future__ import annotations

from config.settings import DEFAULT_THRESHOLDS
from src.data_layer.models import (
    Keyword,
    KeywordClassified,
    KeywordLibrary,
    KeywordTrafficShare,
)


class KeywordBuilder:
    def __init__(self):
        self._thresholds = DEFAULT_THRESHOLDS

    def _get_traffic_level(self, aba_rank: int) -> str:
        if 0 < aba_rank <= self._thresholds["aba_top_tier"]:
            return "一级"
        elif self._thresholds["aba_top_tier"] < aba_rank <= self._thresholds["aba_mid_tier"]:
            return "二级"
        else:
            return "三级"

    def step1_collect_competitors(self, own_asin: str, imported_data: list[dict]) -> list[str]:
        asin_keywords: dict[str, set[str]] = {}
        for source in imported_data:
            data = source.get("data")
            if not data or not isinstance(data, dict):
                continue
            traffic_shares = data.get("traffic_shares", [])
            for ts in traffic_shares:
                asin = ts.asin
                keyword = ts.keyword
                if asin not in asin_keywords:
                    asin_keywords[asin] = set()
                asin_keywords[asin].add(keyword)
        own_keywords = asin_keywords.pop(own_asin, set())
        overlap_counts: dict[str, int] = {}
        for asin, kw_set in asin_keywords.items():
            overlap = len(kw_set & own_keywords)
            if overlap > 0:
                overlap_counts[asin] = overlap
        sorted_asins = sorted(overlap_counts, key=lambda a: overlap_counts[a], reverse=True)
        return sorted_asins[:15]

    def step2_get_market_keywords(self, competitor_asins: list[str], imported_data: list[dict]) -> list[Keyword]:
        keywords: dict[str, Keyword] = {}
        competitor_set = set(competitor_asins)
        for source in imported_data:
            data = source.get("data")
            if not data or not isinstance(data, dict):
                continue
            source_asins = set(data.get("asins", []))
            if competitor_set and source_asins and not (source_asins & competitor_set):
                continue
            kw_list = data.get("keywords", [])
            for kw in kw_list:
                if kw.text and kw.text not in keywords:
                    keywords[kw.text] = kw
        return list(keywords.values())

    def step3_classify_by_traffic(self, keywords: list[Keyword]) -> tuple[dict[str, list], str]:
        tier1, tier2, tier3 = [], [], []
        aba_top = self._thresholds["aba_top_tier"]
        aba_mid = self._thresholds["aba_mid_tier"]
        for kw in keywords:
            rank = kw.aba_rank_weekly or kw.aba_rank_monthly
            if 0 < rank <= aba_top:
                tier1.append(kw)
            elif aba_top < rank <= aba_mid:
                tier2.append(kw)
            else:
                tier3.append(kw)
        tiered = {"一级": tier1, "二级": tier2, "三级": tier3}
        all_sorted = sorted(keywords, key=lambda k: k.weekly_search_volume or k.monthly_search_volume or 0, reverse=True)
        total_traffic = sum((k.weekly_search_volume or k.monthly_search_volume or 0) for k in all_sorted)
        structure = "离散型"
        if total_traffic > 0 and all_sorted:
            top3_traffic = sum((k.weekly_search_volume or k.monthly_search_volume or 0) for k in all_sorted[:3])
            if top3_traffic / total_traffic > 0.30:
                structure = "集中型"
            elif len(all_sorted) >= 10:
                max_single = max((k.weekly_search_volume or k.monthly_search_volume or 0) / total_traffic for k in all_sorted[:10])
                if max_single >= 0.15:
                    structure = "完美十字型"
        return tiered, structure

    def step4_assess_competition(self, keywords: list[Keyword], aba_data: list[Keyword] = None) -> list[KeywordClassified]:
        aba_lookup: dict[str, Keyword] = {}
        if aba_data:
            for akw in aba_data:
                aba_lookup[akw.text.lower()] = akw
        traffic_high = self._thresholds["monopoly_traffic_high"]
        sales_high = self._thresholds["monopoly_sales_high"]
        results = []
        for kw in keywords:
            source = aba_lookup.get(kw.text.lower(), kw)
            click_top3 = source.click_share_top3 or 0
            conv_top3 = source.conversion_share_top3 or 0
            opportunity_score = conv_top3 / click_top3 if click_top3 > 0 else 0.0
            kc = KeywordClassified(
                keyword_text=kw.text,
                translation=kw.translation,
                aba_rank_weekly=kw.aba_rank_weekly or kw.aba_rank_monthly,
                weekly_search_volume=kw.weekly_search_volume,
                monthly_search_volume=kw.monthly_search_volume,
                traffic_level=self._get_traffic_level(kw.aba_rank_weekly or kw.aba_rank_monthly),
                traffic_monopoly=round(click_top3, 4),
                sales_monopoly=round(conv_top3, 4),
                opportunity_score=round(opportunity_score, 4),
                product_count=kw.product_count,
                cpc=kw.cpc_exact,
                spr=kw.spr,
                top1_click_share=source.click_share_top1 or 0,
                top1_conversion_share=source.conversion_share_top1 or 0,
                top1_asin=source.top1_asin,
                top1_brand=source.top1_brand,
            )
            results.append(kc)
        return results

    def step5_judge_relevance(self, keywords: list[KeywordClassified], competitor_asins: list[str],
                               imported_data: list[dict]) -> tuple[list[KeywordClassified], list[str]]:
        kw_asin_map: dict[str, set[str]] = {}
        competitor_set = set(a.upper() for a in competitor_asins)
        for source in imported_data:
            data = source.get("data")
            if not data or not isinstance(data, dict):
                continue
            source_asins = set(a.upper() for a in data.get("asins", []))
            traffic_shares = data.get("traffic_shares", [])
            for ts in traffic_shares:
                key = ts.keyword.lower()
                if key not in kw_asin_map:
                    kw_asin_map[key] = set()
                kw_asin_map[key].add(ts.asin.upper())
        source_count = len(competitor_asins)
        strong_t = self._thresholds["relevance_strong"]
        medium_t = self._thresholds["relevance_medium"]
        weak_t = self._thresholds["relevance_weak"]
        negation_list: list[str] = []
        for kw in keywords:
            asins_for_kw = kw_asin_map.get(kw.keyword_text.lower(), set())
            effective = len(asins_for_kw & competitor_set)
            kw.effective_competitor_count = effective
            score = effective / source_count if source_count > 0 else 0.0
            kw.relevance_score = round(score, 4)
            if score >= strong_t:
                kw.relevance = "强相关"
            elif score >= medium_t:
                kw.relevance = "中相关"
            elif score >= weak_t:
                kw.relevance = "弱相关"
            else:
                kw.relevance = "不相关"
                negation_list.append(kw.keyword_text)
        return keywords, negation_list

    def step6_calculate_push_cost(self, keywords: list[KeywordClassified],
                                   category_cvr: float) -> list[KeywordClassified]:
        push_days = self._thresholds["push_days_target"]
        traffic_high = self._thresholds["monopoly_traffic_high"]
        sales_high = self._thresholds["monopoly_sales_high"]
        for kw in keywords:
            ad_cvr = category_cvr * 2
            cpc = kw.cpc or 0.0
            kw.push_cpa = round(cpc / ad_cvr, 2) if ad_cvr > 0 else 0.0
            kw.daily_order_target = round((kw.spr or 0) / push_days, 2) if push_days > 0 else 0.0
            kw.daily_budget_needed = round(kw.push_cpa * kw.daily_order_target, 2)
            if kw.relevance == "不相关":
                kw.priority = "否词"
            elif kw.traffic_monopoly >= traffic_high and kw.sales_monopoly >= sales_high:
                kw.priority = "跳过(品牌垄断)"
            elif (kw.traffic_monopoly < traffic_high
                  and kw.sales_monopoly < sales_high
                  and kw.relevance in ("强相关", "中相关")):
                kw.priority = "第一优先"
            elif kw.relevance in ("强相关", "中相关"):
                kw.priority = "第二优先"
            else:
                kw.priority = "暂不投入"
        return keywords

    @staticmethod
    def estimate_cvr(imported_data: list[dict]) -> float:
        for source in imported_data:
            data = source.get("data")
            if not data or not isinstance(data, dict):
                continue
            kw_list = data.get("keywords", [])
            rates = [k.purchase_rate for k in kw_list if k.purchase_rate and k.purchase_rate > 0]
            if rates:
                return sum(rates) / len(rates) / 2
        return 0.05

    def build(self, own_asin: str, imported_data: list[dict],
              category_cvr: float = None) -> KeywordLibrary:
        if category_cvr is None:
            category_cvr = self.estimate_cvr(imported_data)
        competitor_asins = self.step1_collect_competitors(own_asin, imported_data)
        if not competitor_asins:
            competitor_asins = self._fallback_competitors(imported_data, own_asin)
        market_keywords = self.step2_get_market_keywords(competitor_asins, imported_data)
        tiered, traffic_structure = self.step3_classify_by_traffic(market_keywords)
        aba_keywords = None
        for source in imported_data:
            if source.get("format") == "amazon_search_terms":
                aba_keywords = source.get("data", {}).get("keywords", [])
                break
        classified = self.step4_assess_competition(market_keywords, aba_keywords)
        classified, negation_list = self.step5_judge_relevance(classified, competitor_asins, imported_data)
        classified = self.step6_calculate_push_cost(classified, category_cvr)
        return KeywordLibrary(
            own_asin=own_asin,
            competitor_asins=competitor_asins,
            classified_keywords=classified,
            negation_list=negation_list,
            traffic_structure=traffic_structure,
            total_keywords=len(classified),
            category_cvr=category_cvr,
        )

    def _fallback_competitors(self, imported_data: list[dict], own_asin: str) -> list[str]:
        for source in imported_data:
            data = source.get("data")
            if not data or not isinstance(data, dict):
                continue
            asins = data.get("asins", [])
            others = [a for a in asins if a.upper() != own_asin.upper()]
            if others:
                return others
        return []
