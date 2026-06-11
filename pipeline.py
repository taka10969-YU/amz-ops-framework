from __future__ import annotations

import os
from datetime import datetime

from src.data_layer.data_store import DataStore
from src.data_layer.file_importer import FileImporter
from src.data_layer.models import (
    AdCampaignRecord,
    CompetitorKeyword,
    CompetitorTimeline,
    FullPipelineResult,
    KeepaDailyRecord,
    KeywordClassified,
    KeywordLibrary,
    MarketPhase,
    OptimizationAction,
)
from src.analysis.competitor import CompetitorTeardown
from src.analysis.competition import CompetitionAssessor
from src.analysis.keyword_builder import KeywordBuilder
from src.analysis.market_rhythm import MarketRhythmAnalyzer
from src.execution.optimizer import Optimizer
from src.execution.troubleshooter import Troubleshooter
from src.execution.verifier import Verifier
from src.report import MarkdownReportGenerator
from src.strategy.ad_architecture import AdArchitect
from src.strategy.attack import AttackPlanner
from src.strategy.budget import BudgetAllocator
from src.strategy.risk import RiskManager


class Pipeline:

    def __init__(self):
        self.importer = FileImporter()
        self.store = DataStore()
        self.keyword_builder = KeywordBuilder()
        self.rhythm_analyzer = MarketRhythmAnalyzer()
        self.competitor_teardown = CompetitorTeardown()
        self.competition_assessor = CompetitionAssessor()
        self.ad_architect = AdArchitect()
        self.budget_allocator = BudgetAllocator()
        self.risk_manager = RiskManager()
        self.optimizer = Optimizer()
        self.verifier = Verifier()
        self.report_gen = MarkdownReportGenerator()
        self.attack_planner = AttackPlanner()
        self.troubleshooter = Troubleshooter()

    def import_data(self, path: str) -> list[dict]:
        if os.path.isfile(path):
            result = self.importer.auto_import(path)
            return [result]
        if os.path.isdir(path):
            return self.importer.import_directory(path)
        return []

    def _adapt_for_builder(self, imported_data: list[dict]) -> list[dict]:
        adapted: list[dict] = []
        for source in imported_data:
            fmt = source.get("format", "")
            data = source.get("data")
            if not data or not isinstance(data, dict):
                adapted.append(source)
                continue

            if fmt in ("sif_compare", "ss_compare"):
                traffic_shares = data.get("traffic_shares", [])
                if traffic_shares:
                    adapted.append({
                        "format": "traffic_share_compare",
                        "path": source.get("path", ""),
                        "data": [
                            ts.model_dump() if hasattr(ts, "model_dump") else ts
                            for ts in traffic_shares
                        ],
                    })
                keywords = data.get("keywords", [])
                if keywords:
                    adapted.append({
                        "format": "keyword_source",
                        "path": source.get("path", ""),
                        "data": [
                            kw.model_dump() if hasattr(kw, "model_dump") else kw
                            for kw in keywords
                        ],
                    })
            elif fmt in ("ss_keyword_analyze", "ss_cpc_category", "amazon_search_terms"):
                keywords = data.get("keywords", [])
                adapted.append({
                    "format": fmt,
                    "path": source.get("path", ""),
                    "data": [
                        kw.model_dump() if hasattr(kw, "model_dump") else kw
                        for kw in keywords
                    ],
                })
            elif fmt == "gpt_categorization":
                classified = data.get("classified_keywords", [])
                adapted.append({
                    "format": fmt,
                    "path": source.get("path", ""),
                    "data": [
                        kc.model_dump() if hasattr(kc, "model_dump") else kc
                        for kc in classified
                    ],
                })
            else:
                adapted.append(source)
        return adapted

    def build_keyword_library(
        self, own_asin: str, category_cvr: float = None, imported_data: list[dict] = None
    ) -> KeywordLibrary:
        adapted = self._adapt_for_builder(imported_data)
        return self.keyword_builder.build(own_asin, adapted, category_cvr)

    def analyze_market(self, imported_data: list[dict]) -> MarketPhase:
        aba_weekly: list[dict] = []
        for source in imported_data:
            fmt = source.get("format", "")
            data = source.get("data")
            if not data or not isinstance(data, dict):
                continue
            if fmt in ("amazon_search_terms", "ss_keyword_analyze", "ss_cpc_category"):
                for kw in data.get("keywords", []):
                    kw_data = kw.model_dump() if hasattr(kw, "model_dump") else kw
                    aba_weekly.append({
                        "keyword": kw_data.get("text", ""),
                        "aba_rank": kw_data.get("aba_rank_weekly", 0),
                        "weekly_search_volume": kw_data.get("weekly_search_volume", 0),
                    })
        return self.rhythm_analyzer.assess_market_phase(aba_weekly)

    def teardown_competitor(
        self, asin: str, imported_data: list[dict]
    ) -> CompetitorTimeline:
        ad_snapshots: list[list[CompetitorKeyword]] = []
        keepa_records: list[KeepaDailyRecord] = []

        for source in imported_data:
            fmt = source.get("format", "")
            data = source.get("data")
            if not data or not isinstance(data, dict):
                continue
            source_path = (source.get("filename", "") + source.get("path", "")).lower()

            if fmt == "sif_ad_view":
                if asin.lower() in source_path:
                    cks = data.get("competitor_keywords", [])
                    if cks:
                        ad_snapshots.append(cks)
            elif fmt == "keepa_history":
                if asin.lower() in source_path:
                    keepa_records.extend(data.get("records", []))

        if not ad_snapshots and not keepa_records:
            for source in imported_data:
                fmt = source.get("format", "")
                data = source.get("data")
                if not data or not isinstance(data, dict):
                    continue
                if fmt == "sif_ad_view":
                    cks = data.get("competitor_keywords", [])
                    if cks:
                        ad_snapshots.append(cks)
                elif fmt == "keepa_history":
                    keepa_records.extend(data.get("records", []))

        return self.competitor_teardown.step6_full_timeline(
            asin=asin,
            ad_snapshots=ad_snapshots,
            keepa_records=keepa_records,
        )

    def generate_strategy(
        self,
        keyword_library: KeywordLibrary,
        market_phase: MarketPhase,
        product_stage: str = "新品期",
        revenue: float = 0,
    ) -> dict:
        keywords = keyword_library.classified_keywords if keyword_library else []
        stage_map = {"新品期": "推词", "成长期": "增量", "成熟期": "稳定", "衰退期": "稳定"}
        ad_stage = stage_map.get(product_stage, "推词")

        ad_arch = self.ad_architect.design_push_ads(keywords, ad_stage)
        budget = self.budget_allocator.calculate_by_stage(product_stage, revenue)

        lifecycle = self.rhythm_analyzer.product_lifecycle_strategy(
            product_stage, market_phase
        )

        return {
            "ad_architecture": ad_arch,
            "budget": budget,
            "lifecycle_strategy": lifecycle,
        }

    def daily_optimization(
        self, imported_data: list[dict], category_cvr: float = 0
    ) -> list[OptimizationAction]:
        campaigns: list[AdCampaignRecord] = []
        for source in imported_data:
            if source.get("format") == "amazon_sp_report":
                data = source.get("data")
                if data and isinstance(data, dict):
                    campaigns.extend(data.get("records", []))
        return self.optimizer.daily_sop(campaigns, category_cvr=category_cvr)

    def full_pipeline(
        self,
        data_dir: str,
        own_asin: str,
        category_cvr: float = None,
        product_stage: str = "新品期",
        revenue: float = 0,
    ) -> FullPipelineResult:
        imported_data = self.import_data(data_dir)

        keyword_library = self.build_keyword_library(
            own_asin, category_cvr, imported_data
        )
        self.store.save_json(keyword_library.model_dump(), "keyword_library.json")

        market_phase = self.analyze_market(imported_data)
        self.store.save_json(market_phase.model_dump(), "market_phase.json")

        competitor_asins = keyword_library.competitor_asins if keyword_library else []
        competitor_timelines: list[CompetitorTimeline] = []
        for comp_asin in competitor_asins[:5]:
            timeline = self.teardown_competitor(comp_asin, imported_data)
            competitor_timelines.append(timeline)

        strategy = self.generate_strategy(
            keyword_library, market_phase, product_stage, revenue
        )
        ad_arch = strategy["ad_architecture"]
        budget = strategy["budget"]

        self.store.save_json(
            ad_arch.model_dump() if ad_arch else {}, "ad_architecture.json"
        )
        self.store.save_json(
            budget.model_dump() if budget else {}, "budget.json"
        )

        risk_alerts = self.risk_manager.identify_risks({})

        opt_actions = self.daily_optimization(imported_data, category_cvr)

        attack_plans = []
        for comp_asin in competitor_asins[:5]:
            plan = self.attack_planner.generate_plan(
                own_asin=own_asin,
                competitor_asin=comp_asin,
                classified_keywords=(
                    keyword_library.classified_keywords if keyword_library else []
                ),
            )
            attack_plans.append(plan)

        result = FullPipelineResult(
            keyword_library=keyword_library,
            market_phase=market_phase,
            competitor_timelines=competitor_timelines,
            budget_plan=budget,
            ad_architecture=ad_arch,
            risk_alerts=risk_alerts,
            optimization_actions=opt_actions,
            attack_plans=attack_plans,
        )

        self.store.save_json(result.model_dump(), "full_pipeline_result.json")

        report = self.report_gen.generate(result)
        self.store.save_report(report, f"pipeline_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")

        return result
