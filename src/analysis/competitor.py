from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from src.data_layer.models import (
    CompetitorKeyword,
    CompetitorTimeline,
    KeepaDailyRecord,
    WeeklyEvent,
)


def _parse_date(date_str: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def _week_start(dt: datetime) -> datetime:
    return dt - timedelta(days=dt.weekday())


def _week_label(dt: datetime) -> str:
    start = _week_start(dt)
    end = start + timedelta(days=6)
    return f"{start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}"


def _classify_strategy(keywords: list[CompetitorKeyword]) -> str:
    if not keywords:
        return "empty"
    top = max(keywords, key=lambda k: k.listing_traffic_share)
    if top.sp_occupancy > 0.5 and top.listing_traffic_share > 0.3:
        return "core_word_focused"
    avg_share = sum(k.listing_traffic_share for k in keywords) / len(keywords)
    if avg_share < 0.05 and len(keywords) > 10:
        return "long_tail"
    brand_count = sum(
        1 for k in keywords
        if any(w[0].isupper() and len(w) > 2 for w in k.keyword.split() if w)
    )
    if brand_count > len(keywords) * 0.3:
        return "brand_word"
    return "mixed"


class CompetitorTeardown:
    def __init__(self):
        pass

    def step1_push_rhythm(self, ad_snapshots: list[list[CompetitorKeyword]]) -> dict:
        timeline = []
        strategy_pattern = []

        for i, snapshot in enumerate(ad_snapshots):
            current_set = {k.keyword for k in snapshot}
            top_kw = max(snapshot, key=lambda k: k.listing_traffic_share) if snapshot else None
            strategy = _classify_strategy(snapshot)
            strategy_pattern.append(strategy)

            if i == 0:
                timeline.append({
                    "period": i,
                    "snapshot_date": snapshot[0].snapshot_date if snapshot else "",
                    "added": sorted(current_set),
                    "removed": [],
                    "top_keyword": top_kw.keyword if top_kw else "",
                    "top_keyword_share": top_kw.listing_traffic_share if top_kw else 0,
                    "share_change": 0,
                    "strategy": strategy,
                })
                continue

            prev_snapshot = ad_snapshots[i - 1]
            prev_set = {k.keyword for k in prev_snapshot}
            prev_top = max(prev_snapshot, key=lambda k: k.listing_traffic_share) if prev_snapshot else None

            timeline.append({
                "period": i,
                "snapshot_date": snapshot[0].snapshot_date if snapshot else "",
                "added": sorted(current_set - prev_set),
                "removed": sorted(prev_set - current_set),
                "top_keyword": top_kw.keyword if top_kw else "",
                "top_keyword_share": top_kw.listing_traffic_share if top_kw else 0,
                "share_change": (top_kw.listing_traffic_share if top_kw else 0) - (prev_top.listing_traffic_share if prev_top else 0),
                "strategy": strategy,
            })

        return {"timeline": timeline, "strategy_pattern": strategy_pattern}

    def step2_ad_evolution(self, ad_snapshots: list[list[CompetitorKeyword]]) -> dict:
        evolution_data = []
        phase_detections = []

        for i, snapshot in enumerate(ad_snapshots):
            evolution_data.append({
                "period": i,
                "snapshot_date": snapshot[0].snapshot_date if snapshot else "",
                "keyword_count": len(snapshot),
                "campaign_count": sum(k.campaign_count for k in snapshot),
                "ad_group_count": sum(k.ad_group_count for k in snapshot),
            })

        for i in range(2, len(evolution_data)):
            curr = evolution_data[i]
            prev = evolution_data[i - 1]
            prev2 = evolution_data[i - 2]
            kw_delta = curr["keyword_count"] - prev["keyword_count"]
            kw_delta_prev = prev["keyword_count"] - prev2["keyword_count"]
            kw_count = curr["keyword_count"]

            if kw_count <= 5 and kw_delta >= 0:
                phase = "testing"
            elif kw_delta > 3 and kw_delta_prev > 0:
                phase = "expanding"
            elif kw_delta >= 0 and kw_count > 10:
                phase = "scaling"
            elif kw_delta < -3:
                phase = "contracting"
            elif kw_delta < 0 and kw_delta_prev < 0:
                phase = "harvesting"
            else:
                phase = "stable"

            phase_detections.append({
                "period": i,
                "snapshot_date": curr["snapshot_date"],
                "phase": phase,
                "keyword_delta": kw_delta,
            })

        return {"evolution_data": evolution_data, "phase_detections": phase_detections}

    def step3_price_promo_rhythm(self, keepa_records: list[KeepaDailyRecord]) -> dict:
        records = list(reversed(keepa_records))
        price_events = []
        promo_events = []
        price_bsr_correlations = []

        for i in range(1, len(records)):
            curr = records[i]
            prev = records[i - 1]
            price_diff = curr.buybox_price - prev.buybox_price

            if abs(price_diff) >= 0.50:
                direction = "up" if price_diff > 0 else "down"
                price_events.append({
                    "date": curr.date,
                    "amount": round(abs(price_diff), 2),
                    "direction": direction,
                    "new_price": curr.buybox_price,
                    "old_price": prev.buybox_price,
                })

                lag_analysis = []
                for lag in range(3, 8):
                    lag_idx = i + lag
                    if lag_idx < len(records):
                        bsr_diff = records[lag_idx].bsr_category - records[i].bsr_category
                        lag_analysis.append({"lag_days": lag, "bsr_change": bsr_diff})
                price_bsr_correlations.append({
                    "price_event_date": curr.date,
                    "direction": direction,
                    "lag_analysis": lag_analysis,
                })

            if curr.coupon_discount != prev.coupon_discount:
                promo_events.append({
                    "date": curr.date,
                    "type": "coupon_change",
                    "old_coupon": prev.coupon_discount,
                    "new_coupon": curr.coupon_discount,
                    "discount_pct": curr.coupon_discount,
                })

            if curr.prime_price and prev.prime_price and curr.prime_price != prev.prime_price:
                promo_events.append({
                    "date": curr.date,
                    "type": "prime_exclusive_change",
                    "old_prime_price": prev.prime_price,
                    "new_prime_price": curr.prime_price,
                })

        return {
            "price_events": price_events,
            "promo_events": promo_events,
            "price_bsr_correlations": price_bsr_correlations,
        }

    def step4_review_rhythm(self, keepa_records: list[KeepaDailyRecord]) -> dict:
        records = list(reversed(keepa_records))
        weekly_buckets: dict[str, list[KeepaDailyRecord]] = defaultdict(list)

        for r in records:
            dt = _parse_date(r.date)
            week_key = _week_start(dt).strftime("%Y-%m-%d")
            weekly_buckets[week_key].append(r)

        sorted_weeks = sorted(weekly_buckets.keys())
        growth_rates = []
        inflection_points = []
        rating_drops = []
        review_events = []
        prev_rate = 0.0

        for wi, week in enumerate(sorted_weeks):
            wk_recs = weekly_buckets[week]
            first = wk_recs[0]
            last = wk_recs[-1]
            delta = last.reviews - first.reviews

            growth_rates.append({
                "week": week,
                "start_reviews": first.reviews,
                "end_reviews": last.reviews,
                "delta": delta,
                "rate_per_week": delta,
            })

            if wi > 0 and prev_rate > 0 and delta > prev_rate * 2 and delta >= 5:
                cause = "possible_merge_or_refurbish" if delta > prev_rate * 3 else "push_campaign_effect"
                inflection_points.append({
                    "week": week,
                    "previous_rate": prev_rate,
                    "current_rate": delta,
                    "acceleration": delta - prev_rate,
                    "possible_cause": cause,
                })

            if wi > 0:
                prev_recs = weekly_buckets[sorted_weeks[wi - 1]]
                prev_avg = sum(r.rating for r in prev_recs) / len(prev_recs)
                curr_avg = sum(r.rating for r in wk_recs) / len(wk_recs)
                drop = prev_avg - curr_avg
                if drop >= 0.3:
                    rating_drops.append({
                        "week": week,
                        "previous_rating": round(prev_avg, 2),
                        "current_rating": round(curr_avg, 2),
                        "drop": round(drop, 2),
                        "possible_cause": "quality_issue_or_attack",
                    })

            review_events.append({
                "week": week,
                "reviews": last.reviews,
                "rating": last.rating,
                "weekly_growth": delta,
            })

            prev_rate = float(delta)

        return {
            "growth_rates": growth_rates,
            "inflection_points": inflection_points,
            "rating_drops": rating_drops,
            "review_events": review_events,
        }

    def step5_market_alignment(self, competitor_timeline: dict, aba_weekly: list[dict]) -> dict:
        if not aba_weekly:
            return {"alignment_score": 0.0, "key_observations": ["No ABA weekly data available"]}

        aba_lookup = {}
        for entry in aba_weekly:
            key = entry.get("week", entry.get("date", ""))
            aba_lookup[key] = entry

        observations = []
        aligned = 0
        total = 0

        for entry in competitor_timeline.get("timeline", []):
            snap_date = entry.get("snapshot_date", "")
            if not snap_date:
                continue
            dt = _parse_date(snap_date)
            week_key = _week_start(dt).strftime("%Y-%m-%d")

            if week_key not in aba_lookup:
                continue

            aba = aba_lookup[week_key]
            sv = aba.get("search_volume", aba.get("weekly_search_volume", 0))
            prev_sv = aba.get("prev_search_volume", aba.get("prev_weekly_search_volume", 0))

            added = len(entry.get("added", []))
            removed = len(entry.get("removed", []))
            total += 1

            if prev_sv > 0:
                sv_change_pct = (sv - prev_sv) / prev_sv * 100
            else:
                sv_change_pct = 0

            if sv > prev_sv and added > removed:
                aligned += 1
                observations.append(
                    f"Week {week_key}: expanded ads during market upswing (search {sv_change_pct:+.0f}%)"
                )
            elif sv < prev_sv and removed > added:
                aligned += 1
                observations.append(
                    f"Week {week_key}: reduced ads during market downswing - defensive"
                )
            elif sv > prev_sv and removed > added:
                observations.append(
                    f"Week {week_key}: reduced ads despite market growth - missed opportunity"
                )
            elif sv < prev_sv and added > removed:
                observations.append(
                    f"Week {week_key}: expanded ads during market decline - aggressive"
                )

        score = round(aligned / total, 2) if total > 0 else 0.0
        return {
            "alignment_score": score,
            "key_observations": observations if observations else ["Insufficient data for alignment analysis"],
        }

    def step6_full_timeline(
        self,
        asin: str,
        ad_snapshots: list[list[CompetitorKeyword]],
        keepa_records: list[KeepaDailyRecord],
        aba_weekly: list[dict] | None = None,
    ) -> CompetitorTimeline:
        push_rhythm = self.step1_push_rhythm(ad_snapshots)
        evolution = self.step2_ad_evolution(ad_snapshots)
        price_promo = self.step3_price_promo_rhythm(keepa_records)
        review_rhythm = self.step4_review_rhythm(keepa_records)

        if aba_weekly:
            self.step5_market_alignment(push_rhythm, aba_weekly)

        records = list(reversed(keepa_records))
        keepa_weekly: dict[str, list[KeepaDailyRecord]] = defaultdict(list)
        for r in records:
            dt = _parse_date(r.date)
            wk = _week_start(dt).strftime("%Y-%m-%d")
            keepa_weekly[wk].append(r)

        snap_by_week: dict[str, list[CompetitorKeyword]] = {}
        for snap in ad_snapshots:
            if not snap or not snap[0].snapshot_date:
                continue
            dt = _parse_date(snap[0].snapshot_date)
            wk = _week_start(dt).strftime("%Y-%m-%d")
            snap_by_week[wk] = snap

        phase_lookup: dict[str, str] = {}
        for pd in evolution.get("phase_detections", []):
            sd = pd.get("snapshot_date", "")
            if sd:
                dt = _parse_date(sd)
                wk = _week_start(dt).strftime("%Y-%m-%d")
                phase_lookup[wk] = pd["phase"]

        rhythm_lookup: dict[str, dict] = {}
        for entry in push_rhythm.get("timeline", []):
            sd = entry.get("snapshot_date", "")
            if sd:
                try:
                    dt = _parse_date(sd)
                    wk = _week_start(dt).strftime("%Y-%m-%d")
                    rhythm_lookup[wk] = entry
                except ValueError:
                    pass

        all_weeks = sorted(set(list(keepa_weekly.keys()) + list(snap_by_week.keys())))
        events: list[WeeklyEvent] = []
        prev_reviews = 0
        prev_price = 0.0
        prev_top_kw = ""

        for week in all_weeks:
            snap = snap_by_week.get(week, [])
            wk_recs = keepa_weekly.get(week, [])

            top_kw_obj = max(snap, key=lambda k: k.listing_traffic_share) if snap else None
            top_keyword = top_kw_obj.keyword if top_kw_obj else ""
            top_keyword_share = top_kw_obj.listing_traffic_share if top_kw_obj else 0
            top_keyword_strategy = _classify_strategy(snap) if snap else ""

            last_r = wk_recs[-1] if wk_recs else None
            price = last_r.buybox_price if last_r else 0
            coupon = last_r.coupon_discount if last_r else ""
            bsr_cat = last_r.bsr_category if last_r else 0
            rating = last_r.rating if last_r else 0
            reviews = last_r.reviews if last_r else 0

            price_change = ""
            if prev_price > 0 and price != prev_price:
                diff = price - prev_price
                arrow = "↑" if diff > 0 else "↓"
                price_change = f"{arrow}{abs(diff):.2f}"

            review_change = ""
            if prev_reviews > 0:
                rd = reviews - prev_reviews
                review_change = f"+{rd}" if rd >= 0 else str(rd)

            phase = phase_lookup.get(week, "")
            strategy_change = phase

            key_decision = self._build_decision(
                week, snap, price, prev_price, coupon,
                reviews, prev_reviews, phase,
                top_keyword, prev_top_kw, rhythm_lookup, aba_weekly,
            )

            label = _week_label(_parse_date(week))
            events.append(WeeklyEvent(
                week_label=label,
                date_range=label,
                ad_keyword_count=len(snap),
                top_keyword=top_keyword,
                top_keyword_share=round(top_keyword_share, 4),
                top_keyword_strategy=top_keyword_strategy,
                price=price,
                price_change=price_change,
                coupon=coupon,
                bsr_category=bsr_cat,
                rating=rating,
                reviews=reviews,
                review_change=review_change,
                ad_strategy_change=strategy_change,
                key_decision=key_decision,
            ))

            prev_reviews = reviews
            prev_price = price
            if top_keyword:
                prev_top_kw = top_keyword

        phase_summary = self._summarize_phases(evolution.get("phase_detections", []))
        return CompetitorTimeline(
            asin=asin,
            weekly_events=events,
            total_weeks=len(events),
            phase_summary=phase_summary,
        )

    def _build_decision(
        self,
        week: str,
        snap: list[CompetitorKeyword],
        price: float,
        prev_price: float,
        coupon: str,
        reviews: int,
        prev_reviews: int,
        phase: str,
        top_keyword: str,
        prev_top_kw: str,
        rhythm_lookup: dict[str, dict],
        aba_weekly: list[dict] | None,
    ) -> str:
        parts = []

        if prev_price > 0 and price < prev_price:
            market_up = False
            if aba_weekly:
                for entry in aba_weekly:
                    ek = entry.get("week", entry.get("date", ""))
                    if ek == week:
                        sv = entry.get("search_volume", entry.get("weekly_search_volume", 0))
                        psv = entry.get("prev_search_volume", entry.get("prev_weekly_search_volume", 0))
                        if sv > psv:
                            market_up = True
                        break
            if market_up:
                parts.append("降价+开广告，踩准上升期")
            else:
                parts.append("降价促销")

        if coupon and coupon not in ("", "0%", "0"):
            parts.append("开启优惠券")

        phase_map = {
            "testing": "测试期探词",
            "expanding": "扩词测试",
            "scaling": "规模化投放",
            "contracting": "收缩优化ACOS",
            "harvesting": "收割期优化",
        }
        if phase in phase_map:
            parts.append(phase_map[phase])

        if top_keyword and prev_top_kw and top_keyword != prev_top_kw:
            parts.append(f"场景词替代核心词: {top_keyword}")

        if prev_reviews > 0 and reviews > prev_reviews * 1.5 and (reviews - prev_reviews) >= 10:
            parts.append("疑似刷评或合并变体")

        return "；".join(parts) if parts else "维持现状"

    def _summarize_phases(self, phase_detections: list[dict]) -> str:
        if not phase_detections:
            return "数据不足"
        counts: dict[str, int] = defaultdict(int)
        for pd in phase_detections:
            counts[pd.get("phase", "unknown")] += 1
        dominant = max(counts, key=counts.get)
        parts = [f"{p}: {c}周" for p, c in sorted(counts.items(), key=lambda x: -x[1])]
        return f"主导阶段: {dominant}（{'，'.join(parts)}）"
