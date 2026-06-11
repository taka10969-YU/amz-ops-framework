from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Product(BaseModel):
    asin: str
    title: str = ""
    price: float = 0
    prime_price: float = 0
    coupon_price: float = 0
    coupon_discount: str = ""
    bsr_overall: int = 0
    bsr_category: int = 0
    bsr_category_name: str = ""
    rating: float = 0
    reviews: int = 0


class Keyword(BaseModel):
    text: str
    translation: str = ""
    aba_rank_weekly: int = 0
    aba_rank_monthly: int = 0
    weekly_search_volume: int = 0
    monthly_search_volume: int = 0
    monthly_purchases: int = 0
    purchase_rate: float = 0
    product_count: int = 0
    cpc_exact: float = 0
    cpc_phrase: float = 0
    cpc_broad: float = 0
    cpc_range_low: float = 0
    cpc_range_high: float = 0
    spr: int = 0
    click_share_top1: float = 0
    conversion_share_top1: float = 0
    top1_asin: str = ""
    top1_title: str = ""
    top1_brand: str = ""
    click_share_top3: float = 0
    conversion_share_top3: float = 0


class KeywordTrafficShare(BaseModel):
    asin: str
    keyword: str
    traffic_share: float = 0
    rank_label: str = ""


class CompetitorKeyword(BaseModel):
    keyword: str
    translation: str = ""
    sp_occupancy: float = 0
    listing_traffic_share: float = 0
    campaign_count: int = 0
    ad_group_count: int = 0
    variant_count: int = 0
    weekly_search_volume: int = 0
    product_count: int = 0
    snapshot_date: str = ""


class KeepaDailyRecord(BaseModel):
    date: str
    buybox_price: float = 0
    price: float = 0
    prime_price: float = 0
    coupon_price: float = 0
    coupon_discount: str = ""
    deal_price: float = 0
    deal_info: str = ""
    fba_price: float = 0
    fbm_price: float = 0
    list_price: float = 0
    shipping: str = ""
    bsr_overall: int = 0
    bsr_category: int = 0
    rating: float = 0
    reviews: int = 0
    buybox_sellers: int = 0


class AdCampaignRecord(BaseModel):
    date: str
    sku: str = ""
    currency: str = "USD"
    campaign_name: str = ""
    ad_group_name: str = ""
    targeting: str = ""
    match_type: str = ""
    customer_search_term: str = ""
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0
    cpc: float = 0
    spend: float = 0
    sales_7d: Optional[float] = None
    acos: Optional[float] = None
    roas: Optional[float] = None
    orders_7d: Optional[int] = None
    units_7d: Optional[int] = None


class KeywordClassified(BaseModel):
    keyword_text: str
    translation: str = ""
    aba_rank_weekly: int = 0
    weekly_search_volume: int = 0
    monthly_search_volume: int = 0
    traffic_level: str = ""
    relevance: str = ""
    relevance_score: float = 0
    traffic_monopoly: float = 0
    sales_monopoly: float = 0
    opportunity_score: float = 0
    product_count: int = 0
    cpc: float = 0
    spr: int = 0
    push_cpa: float = 0
    daily_budget_needed: float = 0
    daily_order_target: float = 0
    priority: str = ""
    top1_click_share: float = 0
    top1_conversion_share: float = 0
    top1_asin: str = ""
    top1_brand: str = ""
    effective_competitor_count: int = 0
    traffic_shares: dict[str, float] = Field(default_factory=dict)


class MarketPhase(BaseModel):
    phase: str = ""
    trend_data: list[dict] = Field(default_factory=list)
    confidence: float = 0
    consecutive_weeks: int = 0
    change_pct: float = 0
    recommended_action: str = ""


class WeeklyEvent(BaseModel):
    week_label: str = ""
    date_range: str = ""
    ad_keyword_count: int = 0
    top_keyword: str = ""
    top_keyword_share: float = 0
    top_keyword_strategy: str = ""
    price: float = 0
    price_change: str = ""
    coupon: str = ""
    bsr_category: int = 0
    rating: float = 0
    reviews: int = 0
    review_change: str = ""
    ad_strategy_change: str = ""
    key_decision: str = ""


class CompetitorTimeline(BaseModel):
    asin: str
    product_title: str = ""
    category: str = ""
    weekly_events: list[WeeklyEvent] = Field(default_factory=list)
    total_weeks: int = 0
    phase_summary: str = ""


class AdArchitecture(BaseModel):
    name: str = ""
    stage: str = ""
    campaigns: list[dict] = Field(default_factory=list)
    push_strategy: str = ""
    bidding_strategy: str = ""
    top_position_bid_pct: int = 0
    rest_position_bid_pct: int = 0


class BudgetBreakdown(BaseModel):
    stage: str = ""
    revenue: float = 0
    ad_spend_ratio: float = 0
    ad_spend_amount: float = 0
    allocations: dict[str, float] = Field(default_factory=dict)
    ad_type_allocations: dict[str, float] = Field(default_factory=dict)
    target_acos: float = 0
    net_margin: float = 0
    acceptable_ad_spend: float = 0


class ProfitModel(BaseModel):
    price: float = 0
    product_cost: float = 0
    fba_fee: float = 0
    commission: float = 0
    ad_spend: float = 0
    return_loss: float = 0
    net_profit: float = 0
    net_margin: float = 0
    target_margin: float = 0
    acceptable_ad_spend: float = 0
    target_acos: float = 0


class RiskAlert(BaseModel):
    risk_type: str = ""
    trigger_condition: str = ""
    current_value: str = ""
    threshold: str = ""
    severity: str = ""
    strategy: str = ""
    action: str = ""
    owner: str = ""


class OptimizationAction(BaseModel):
    method: str = ""
    campaign: str = ""
    keyword: str = ""
    current_value: str = ""
    suggested_value: str = ""
    reason: str = ""
    priority: str = ""
    estimated_impact: str = ""


class AttackPlan(BaseModel):
    competitor_asin: str
    weaknesses: list[dict] = Field(default_factory=list)
    copy_actions: list[str] = Field(default_factory=list)
    differentiate_actions: list[str] = Field(default_factory=list)
    phased_plan: list[dict] = Field(default_factory=list)


class KeywordLibrary(BaseModel):
    own_asin: str = ""
    competitor_asins: list[str] = Field(default_factory=list)
    classified_keywords: list[KeywordClassified] = Field(default_factory=list)
    negation_list: list[str] = Field(default_factory=list)
    traffic_structure: str = ""
    total_keywords: int = 0
    category_cvr: float = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class FullPipelineResult(BaseModel):
    keyword_library: Optional[KeywordLibrary] = None
    market_phase: Optional[MarketPhase] = None
    competitor_timelines: list[CompetitorTimeline] = Field(default_factory=list)
    budget_plan: Optional[BudgetBreakdown] = None
    profit_model: Optional[ProfitModel] = None
    risk_alerts: list[RiskAlert] = Field(default_factory=list)
    optimization_actions: list[OptimizationAction] = Field(default_factory=list)
    ad_architecture: Optional[AdArchitecture] = None
    attack_plans: list[AttackPlan] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
