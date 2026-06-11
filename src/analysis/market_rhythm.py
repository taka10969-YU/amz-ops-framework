from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import BUDGET_RATIOS, DEFAULT_THRESHOLDS, OPTIMIZATION_FREQUENCY
from src.data_layer.models import MarketPhase


class MarketRhythmAnalyzer:

    def find_best_launch_window(self, aba_history: pd.DataFrame) -> dict:
        if aba_history is None or aba_history.empty:
            return {
                "best_window_start": None,
                "best_window_end": None,
                "conditions_met": [],
                "recommendation": "数据不足，无法判断最佳上架窗口",
            }

        df = aba_history.copy()

        date_col = self._resolve_column(df, ["date", "week"])
        if date_col is None:
            return {
                "best_window_start": None,
                "best_window_end": None,
                "conditions_met": [],
                "recommendation": "缺少日期列",
            }

        df = df.sort_values(date_col).reset_index(drop=True)

        volume_col = self._resolve_column(df, ["search_volume", "aba_rank"])
        if volume_col is None:
            return {
                "best_window_start": None,
                "best_window_end": None,
                "conditions_met": [],
                "recommendation": "缺少搜索量或ABA排名列",
            }

        is_rank = "aba_rank" in volume_col

        conditions_met = []
        scores = pd.Series(0.0, index=df.index)

        cpc_col = self._resolve_column(df, ["cpc", "cpc_exact", "cpc_phrase"])
        if cpc_col is not None:
            cpc_min = df[cpc_col].min()
            cpc_range = df[cpc_col].max() - cpc_min
            if cpc_range > 0:
                normalized = (df[cpc_col] - cpc_min) / cpc_range
                if is_rank:
                    scores += (1 - normalized) * 0.33
                else:
                    scores += (1 - normalized) * 0.33
            cpc_low_periods = df[df[cpc_col] <= df[cpc_col].quantile(0.3)]
            if not cpc_low_periods.empty:
                conditions_met.append("CPC低点窗口已识别")

        comp_col = self._resolve_column(df, ["competitor_ad_activity", "spend", "ad_spend"])
        if comp_col is not None:
            comp_min = df[comp_col].min()
            comp_range = df[comp_col].max() - comp_min
            if comp_range > 0:
                normalized = (df[comp_col] - comp_min) / comp_range
                scores += (1 - normalized) * 0.33
            low_comp = df[df[comp_col] <= df[comp_col].quantile(0.3)]
            if not low_comp.empty:
                conditions_met.append("竞争对手广告活跃度低谷已识别")

        if len(df) >= 3:
            window_size = min(3, len(df))
            if is_rank:
                rolling = df[volume_col].rolling(window=window_size).mean()
                growing = rolling.diff() < 0
            else:
                rolling = df[volume_col].rolling(window=window_size).mean()
                growing = rolling.diff() > 0
            scores += growing.astype(float) * 0.34
            if growing.any():
                conditions_met.append("搜索量上升趋势已识别")

        if scores.sum() == 0:
            if is_rank:
                scores = 1.0 - (df[volume_col] - df[volume_col].min()) / max(df[volume_col].max() - df[volume_col].min(), 1)
            else:
                scores = (df[volume_col] - df[volume_col].min()) / max(df[volume_col].max() - df[volume_col].min(), 1)

        best_idx = scores.idxmax()
        window_half = max(1, len(df) // 10)
        start_idx = max(0, best_idx - window_half)
        end_idx = min(len(df) - 1, best_idx + window_half)

        best_start = df.loc[start_idx, date_col]
        best_end = df.loc[end_idx, date_col]

        recommendation = "建议在识别的窗口期内上架，结合CPC和竞争情况调整出价"
        if len(conditions_met) >= 2:
            recommendation = "多条件 favorable，强烈建议在此窗口上架并加大广告投放"
        elif len(conditions_met) == 1:
            recommendation = "部分条件 favorable，建议谨慎上架并监控数据变化"
        else:
            recommendation = "当前数据未检测到明显有利窗口，建议持续观察"

        return {
            "best_window_start": str(best_start),
            "best_window_end": str(best_end),
            "conditions_met": conditions_met,
            "recommendation": recommendation,
        }

    def assess_market_phase(self, aba_weekly: list[dict]) -> MarketPhase:
        if not aba_weekly:
            return MarketPhase(
                phase="unknown",
                trend_data=[],
                confidence=0,
                consecutive_weeks=0,
                change_pct=0,
                recommended_action="无数据，无法判断市场阶段",
            )

        df = pd.DataFrame(aba_weekly)
        volume_col = None
        is_rank = False

        if "search_volume" in df.columns:
            volume_col = "search_volume"
        elif "aba_rank" in df.columns:
            volume_col = "aba_rank"
            is_rank = True

        if volume_col is None:
            return MarketPhase(
                phase="unknown",
                trend_data=aba_weekly,
                confidence=0,
                consecutive_weeks=0,
                change_pct=0,
                recommended_action="缺少搜索量或ABA排名字段",
            )

        df = df.dropna(subset=[volume_col]).reset_index(drop=True)
        if df.empty or len(df) < 2:
            return MarketPhase(
                phase="unknown",
                trend_data=aba_weekly,
                confidence=0,
                consecutive_weeks=0,
                change_pct=0,
                recommended_action="数据不足，至少需要2周数据",
            )

        values = df[volume_col].astype(float)
        diffs = values.diff().dropna()

        min_weeks = DEFAULT_THRESHOLDS.get("market_down_weeks", 2)
        stable_pct = DEFAULT_THRESHOLDS.get("market_stable波动_pct", 0.10)

        down_streak = 0
        up_streak = 0
        max_down = 0
        max_up = 0

        for d in diffs:
            if is_rank:
                if d > 0:
                    down_streak += 1
                    up_streak = 0
                elif d < 0:
                    up_streak += 1
                    down_streak = 0
                else:
                    down_streak = 0
                    up_streak = 0
            else:
                if d < 0:
                    down_streak += 1
                    up_streak = 0
                elif d > 0:
                    up_streak += 1
                    down_streak = 0
                else:
                    down_streak = 0
                    up_streak = 0
            max_down = max(max_down, down_streak)
            max_up = max(max_up, up_streak)

        recent_pct = 0.0
        if len(values) >= 2 and values.iloc[-2] != 0:
            recent_pct = (values.iloc[-1] - values.iloc[-2]) / abs(values.iloc[-2])

        recent_values = values.tail(min(len(values), 8))
        variation = 0.0
        if recent_values.mean() != 0:
            variation = recent_values.std() / abs(recent_values.mean())

        phase = "stable"
        confidence = 0.5
        consecutive = 0
        change_pct = round(recent_pct * 100, 2)
        action = "保排名，精准+泛匹配同时，尽可能拓词"

        if max_down >= min_weeks or (down_streak >= min_weeks):
            phase = "down"
            confidence = min(0.95, 0.5 + max_down * 0.1)
            consecutive = max_down if max_down >= down_streak else down_streak
            action = "降花费，保核心词"
        elif max_up >= min_weeks or (up_streak >= min_weeks):
            phase = "up"
            confidence = min(0.95, 0.5 + max_up * 0.1)
            consecutive = max_up if max_up >= up_streak else up_streak
            action = "涨花费，冲首页，精准投放为主，广告费高度集中"
        else:
            phase = "stable"
            confidence = max(0.3, 1.0 - variation)
            consecutive = 0
            action = "保排名，精准+泛匹配同时，尽可能拓词"

        trend_data = df.to_dict("records")

        return MarketPhase(
            phase=phase,
            trend_data=trend_data,
            confidence=round(confidence, 2),
            consecutive_weeks=consecutive,
            change_pct=change_pct,
            recommended_action=action,
        )

    def detect_seasonality(self, aba_multiyear: pd.DataFrame) -> dict:
        default_result = {
            "is_seasonal": False,
            "peak_periods": [],
            "trough_periods": [],
            "seasonal_months": [],
        }

        if aba_multiyear is None or aba_multiyear.empty:
            return default_result

        df = aba_multiyear.copy()
        required = {"year", "week_of_year", "search_volume"}
        if not required.issubset(df.columns):
            return default_result

        df = df.dropna(subset=["year", "week_of_year", "search_volume"]).reset_index(drop=True)
        if df.empty:
            return default_result

        years = df["year"].unique()
        if len(years) < 2:
            return default_result

        threshold = DEFAULT_THRESHOLDS.get("seasonality波动_threshold", 0.30)

        grouped = df.groupby("week_of_year")["search_volume"].agg(["mean", "std", "min", "max"]).reset_index()
        grouped.columns = ["week_of_year", "mean_vol", "std_vol", "min_vol", "max_vol"]

        overall_mean = df["search_volume"].mean()
        if overall_mean == 0:
            return default_result

        grouped["cv"] = grouped["std_vol"] / grouped["mean_vol"].replace(0, np.nan)
        grouped["range_pct"] = (grouped["max_vol"] - grouped["min_vol"]) / overall_mean

        seasonal_weeks = grouped[grouped["range_pct"] > threshold]
        is_seasonal = len(seasonal_weeks) > 0

        peak_periods = []
        trough_periods = []

        if is_seasonal:
            week_stats = df.groupby("week_of_year")["search_volume"].mean().reset_index()
            week_stats = week_stats.sort_values("search_volume", ascending=False)

            for _, row in week_stats.head(4).iterrows():
                week_num = int(row["week_of_year"])
                peak_periods.append(self._week_to_month_range(week_num))

            for _, row in week_stats.tail(4).iterrows():
                week_num = int(row["week_of_year"])
                trough_periods.append(self._week_to_month_range(week_num))

        seasonal_months = list(set(
            [m for p in peak_periods for m in p.get("months", [])]
            + [m for t in trough_periods for m in t.get("months", [])]
        ))
        seasonal_months.sort(key=lambda x: ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(x)
                              if x in ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] else 99)

        return {
            "is_seasonal": is_seasonal,
            "peak_periods": peak_periods,
            "trough_periods": trough_periods,
            "seasonal_months": seasonal_months,
        }

    def product_lifecycle_strategy(self, product_stage: str, phase: MarketPhase) -> dict:
        stage_configs = BUDGET_RATIOS

        if product_stage not in stage_configs:
            return {
                "ad_focus": "未知阶段",
                "ctr_cvr_priority": "ctr",
                "budget_strategy": "维持当前预算",
                "recommended_actions": ["确认产品生命周期阶段后调整策略"],
            }

        config = stage_configs[product_stage]

        if product_stage == "新品期":
            ad_focus = "精准推词，快速获取流量和转化数据"
            ctr_cvr_priority = "ctr"
            budget_strategy = f"广告花费占营收{config['ad_spend_pct'][0]*100:.0f}%-{config['ad_spend_pct'][1]*100:.0f}%，推词预算占{config['push']*100:.0f}%"
            actions = [
                "开精准匹配广告，集中推核心大词",
                "监控CTR，低于0.3%及时调整主图和标题",
                "前2周以获取曝光和点击为主，不计较ACOS",
                "配合Coupon提升转化率",
            ]
            if phase.phase == "up":
                actions.append("市场上升期，加大推词预算，快速冲首页")
            elif phase.phase == "down":
                actions.append("市场下行期，控制预算，保核心词位置")

        elif product_stage == "成长期":
            ad_focus = "扩词+增量，拓展流量入口"
            ctr_cvr_priority = "cvr"
            budget_strategy = f"广告花费占营收{config['ad_spend_pct'][0]*100:.0f}%-{config['ad_spend_pct'][1]*100:.0f}%，增量预算占{config['growth']*100:.0f}%"
            actions = [
                "增加词组匹配和广泛匹配，拓词为主",
                "关注转化率，淘汰高花费低转化词",
                "开启SBV广告增加品牌曝光",
                "逐步降低对单一核心词的依赖",
            ]
            if phase.phase == "up":
                actions.append("市场上升期，快速扩词抢量")
            elif phase.phase == "down":
                actions.append("市场下行期，收缩至高转化词")

        elif product_stage == "成熟期":
            ad_focus = "稳排名+防御，保住核心流量"
            ctr_cvr_priority = "cvr"
            budget_strategy = f"广告花费占营收{config['ad_spend_pct'][0]*100:.0f}%-{config['ad_spend_pct'][1]*100:.0f}%，维护预算占{config['maintain']*100:.0f}%"
            actions = [
                "精准匹配保核心词排名",
                "增加商品投放防御竞品",
                "开启SD广告做再营销",
                "测试新词，为下一轮增长做准备",
            ]
            if phase.phase == "up":
                actions.append("市场上升期，适当增加预算抢占更多份额")
            elif phase.phase == "down":
                actions.append("市场下行期，聚焦利润词，削减低效花费")

        elif product_stage == "衰退期":
            ad_focus = "保核心+清仓，控制成本"
            ctr_cvr_priority = "acos"
            budget_strategy = f"广告花费占营收{config['ad_spend_pct'][0]*100:.0f}%-{config['ad_spend_pct'][1]*100:.0f}%，核心词预算占{config['core']*100:.0f}%"
            actions = [
                "仅保留高转化核心词精准投放",
                "大幅削减预算，关注ACOS",
                "配合Deal清仓",
                "准备新品替代",
            ]
        else:
            ad_focus = "维持现状"
            ctr_cvr_priority = "ctr"
            budget_strategy = "维持当前预算"
            actions = ["确认产品生命周期阶段后调整策略"]

        return {
            "ad_focus": ad_focus,
            "ctr_cvr_priority": ctr_cvr_priority,
            "budget_strategy": budget_strategy,
            "recommended_actions": actions,
        }

    def get_optimization_frequency(self, competition_level: str) -> str:
        return OPTIMIZATION_FREQUENCY.get(competition_level, "2-3天")

    def _resolve_column(self, df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
        for col in candidates:
            if col in df.columns:
                return col
        return None

    @staticmethod
    def _week_to_month_range(week_num: int) -> dict:
        month_starts = [1, 5, 9, 13, 18, 22, 27, 31, 36, 40, 45, 49]
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        month = 0
        for i, start in enumerate(month_starts):
            if week_num >= start:
                month = i
            else:
                break

        month = min(month, 11)
        return {
            "week": week_num,
            "month": month_names[month],
            "months": [month_names[month]],
        }
