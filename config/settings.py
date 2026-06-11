import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

CREDENTIALS_PATH = os.path.join(BASE_DIR, "config", "credentials.yaml")

DEFAULT_THRESHOLDS = {
    "aba_top_tier": 100,
    "aba_mid_tier": 1000,
    "monopoly_traffic_high": 0.50,
    "monopoly_sales_high": 0.30,
    "relevance_strong": 0.50,
    "relevance_medium": 0.30,
    "relevance_weak": 0.10,
    "seasonality波动_threshold": 0.30,
    "market_down_weeks": 2,
    "market_stable波动_pct": 0.10,
    "push_days_target": 8,
    "cpc_decrease_step_small": 0.05,
    "cpc_decrease_step_medium": 0.20,
    "cpc_decrease_step_large": 1.00,
}

BUDGET_RATIOS = {
    "新品期": {"ad_spend_pct": (0.15, 0.25), "push": 0.70, "test": 0.20, "defense": 0.10},
    "成长期": {"ad_spend_pct": (0.10, 0.15), "push": 0.50, "growth": 0.30, "defense": 0.20},
    "成熟期": {"ad_spend_pct": (0.05, 0.10), "maintain": 0.40, "growth": 0.30, "test_new": 0.30},
    "衰退期": {"ad_spend_pct": (0.03, 0.05), "core": 0.70, "clearance": 0.30},
}

AD_TYPE_BUDGET = {
    "推词": {"SP精准": 0.50, "SP词组广泛": 0.10, "SBV": 0.30, "SP商品投放": 0.00, "SD_SB": 0.00},
    "增量": {"SP精准": 0.30, "SP词组广泛": 0.20, "SBV": 0.20, "SP商品投放": 0.20, "SD_SB": 0.10},
    "稳定": {"SP精准": 0.20, "SP词组广泛": 0.20, "SBV": 0.10, "SP商品投放": 0.30, "SD_SB": 0.20},
}

NEGATION_RULES = {
    "phrase_negation_hours": 48,
    "exact_negation_hours": 48,
    "product_negation_hours": 96,
}

OPTIMIZATION_FREQUENCY = {
    "大红海": "daily_multi",
    "中等竞争": "2-3天",
    "蓝海": "3天",
}
