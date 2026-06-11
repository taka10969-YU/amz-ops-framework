from __future__ import annotations

from src.data_layer.models import AdArchitecture, KeywordClassified
from config.settings import AD_TYPE_BUDGET


class AdArchitect:

    def design_push_ads(
        self,
        keywords: list[KeywordClassified],
        stage: str = "推词",
        strategy: str = "auto",
    ) -> AdArchitecture:
        if not keywords:
            return AdArchitecture(stage=stage, push_strategy=strategy)

        if strategy == "auto":
            total_budget = sum(k.daily_budget_needed for k in keywords if k.daily_budget_needed)
            strategy = self.select_push_strategy(total_budget, keywords)

        bidding = self.select_bidding_strategy(stage)

        campaigns: list[dict] = []

        big_keywords = [k for k in keywords if k.aba_rank_weekly > 0 and k.aba_rank_weekly <= 1000]
        small_keywords = [k for k in keywords if k.aba_rank_weekly > 1000]

        if strategy in ("小带大", "大带小"):
            ordered = small_keywords + big_keywords if strategy == "小带大" else big_keywords + small_keywords
        elif strategy == "一对一":
            ordered = [k for k in keywords if k.priority in ("高", "中")][:5]
        elif strategy == "面对点":
            ordered = keywords
        else:
            ordered = keywords

        ad_type_ratios = AD_TYPE_BUDGET.get(stage if stage in AD_TYPE_BUDGET else "推词", AD_TYPE_BUDGET["推词"])

        if ad_type_ratios.get("SP精准", 0) > 0 and ordered:
            sp_exact_kw = [k.keyword_text for k in ordered[:10]]
            campaigns.append({
                "type": "SP",
                "targeting": "精准",
                "keywords": sp_exact_kw,
                "budget_ratio": ad_type_ratios["SP精准"],
            })

        if ad_type_ratios.get("SP词组广泛", 0) > 0 and big_keywords:
            sp_phrase_kw = [k.keyword_text for k in big_keywords[:5]]
            campaigns.append({
                "type": "SP",
                "targeting": "词组",
                "keywords": sp_phrase_kw,
                "budget_ratio": ad_type_ratios["SP词组广泛"],
            })

        if ad_type_ratios.get("SBV", 0) > 0 and big_keywords:
            sbv_kw = [k.keyword_text for k in big_keywords[:5]]
            campaigns.append({
                "type": "SBV",
                "targeting": "精准",
                "keywords": sbv_kw,
                "budget_ratio": ad_type_ratios["SBV"],
            })

        if ad_type_ratios.get("SP商品投放", 0) > 0 and stage in ("增量", "稳定"):
            campaigns.append({
                "type": "SP",
                "targeting": "商品投放",
                "keywords": [],
                "budget_ratio": ad_type_ratios["SP商品投放"],
            })

        if ad_type_ratios.get("SD_SB", 0) > 0 and stage in ("增量", "稳定"):
            campaigns.append({
                "type": "SD/SB",
                "targeting": "受众",
                "keywords": [],
                "budget_ratio": ad_type_ratios["SD_SB"],
            })

        top_kw = [k for k in ordered if k.cpc > 0][:5]
        top_pct = 60 if top_kw else 50
        rest_pct = 100 - top_pct

        return AdArchitecture(
            name=f"{stage}_{strategy}",
            stage=stage,
            campaigns=campaigns,
            push_strategy=strategy,
            bidding_strategy=bidding,
            top_position_bid_pct=top_pct,
            rest_position_bid_pct=rest_pct,
        )

    def select_push_strategy(self, total_budget: float, keywords: list[KeywordClassified]) -> str:
        if not keywords:
            return "大带小"

        if len(keywords) == 1:
            return "一对一"

        big_count = sum(1 for k in keywords if k.aba_rank_weekly > 0 and k.aba_rank_weekly <= 1000)
        small_count = len(keywords) - big_count

        if total_budget < 50 and small_count > big_count:
            return "小带大"

        if total_budget >= 50:
            return "大带小"

        if len(keywords) > 10 and big_count > 0:
            return "面对点"

        return "大带小"

    def select_bidding_strategy(self, product_stage: str) -> str:
        stage_map = {
            "新品期": "固定",
            "成长期": "固定",
            "成熟期": "仅降低",
            "衰退期": "仅降低",
        }
        return stage_map.get(product_stage, "提高或降低")
