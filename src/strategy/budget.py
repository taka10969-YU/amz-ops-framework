from __future__ import annotations

from src.data_layer.models import BudgetBreakdown, ProfitModel
from config.settings import BUDGET_RATIOS, AD_TYPE_BUDGET


class BudgetAllocator:

    def calculate_by_stage(self, stage: str, revenue: float) -> BudgetBreakdown:
        if revenue <= 0:
            return BudgetBreakdown(stage=stage, revenue=revenue)

        ratio_cfg = BUDGET_RATIOS.get(stage)
        if not ratio_cfg:
            return BudgetBreakdown(stage=stage, revenue=revenue)

        low, high = ratio_cfg["ad_spend_pct"]
        ad_spend_ratio = (low + high) / 2
        ad_spend_amount = revenue * ad_spend_ratio

        allocations: dict[str, float] = {}
        for key in ("push", "test", "defense", "growth", "maintain", "test_new", "core", "clearance"):
            if key in ratio_cfg:
                allocations[key] = ad_spend_amount * ratio_cfg[key]

        ad_type_allocs = self.calculate_by_ad_type(stage)
        target_acos = 1 - ad_spend_ratio if ad_spend_ratio < 1 else 0

        return BudgetBreakdown(
            stage=stage,
            revenue=revenue,
            ad_spend_ratio=ad_spend_ratio,
            ad_spend_amount=ad_spend_amount,
            allocations=allocations,
            ad_type_allocations=ad_type_allocs,
            target_acos=target_acos,
            net_margin=0,
            acceptable_ad_spend=0,
        )

    def calculate_by_ad_type(self, stage: str) -> dict[str, float]:
        stage_map = {
            "新品期": "推词",
            "成长期": "增量",
            "成熟期": "稳定",
            "衰退期": "稳定",
        }
        ad_stage = stage_map.get(stage, "推词")
        return dict(AD_TYPE_BUDGET.get(ad_stage, AD_TYPE_BUDGET["推词"]))

    def build_profit_model(
        self,
        price: float,
        product_cost: float,
        fba_fee: float,
        commission_rate: float,
        ad_spend: float,
        return_rate: float,
        target_margin: float = 0.15,
    ) -> ProfitModel:
        if price <= 0:
            return ProfitModel(target_margin=target_margin)

        commission = price * commission_rate
        return_loss = price * return_rate
        net_profit = price - product_cost - fba_fee - commission - ad_spend - return_loss
        net_margin = net_profit / price if price > 0 else 0
        acceptable_ad_spend = price - product_cost - fba_fee - commission - (price * target_margin) - return_loss

        if ad_spend > 0 and acceptable_ad_spend > 0:
            implied_revenue_from_ad = price
            target_acos = acceptable_ad_spend / implied_revenue_from_ad
        elif ad_spend > 0:
            target_acos = net_profit / (price * ad_spend / price) if price > 0 else 0
        else:
            target_acos = 0

        return ProfitModel(
            price=price,
            product_cost=product_cost,
            fba_fee=fba_fee,
            commission=commission,
            ad_spend=ad_spend,
            return_loss=return_loss,
            net_profit=net_profit,
            net_margin=net_margin,
            target_margin=target_margin,
            acceptable_ad_spend=acceptable_ad_spend,
            target_acos=target_acos,
        )
