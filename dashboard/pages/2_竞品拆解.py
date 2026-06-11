"""Competitor Teardown page - Ch11"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data_layer.file_importer import FileImporter
from src.data_layer.models import CompetitorKeyword, KeepaDailyRecord
from dashboard.utils import render_timeline_chart

st.title("竞品拆解 (第11章)")

if "imported" not in st.session_state:
    st.info("请先在首页导入数据")
    st.stop()

imported = st.session_state["imported"]

all_asins = set()
ad_snapshots_by_date = {}
keepa_records = []

for source in imported:
    data = source.get("data")
    if not isinstance(data, dict):
        continue

    asins = data.get("asins", [])
    if asins:
        all_asins.update(asins)

    comp_kws = data.get("competitor_keywords", [])
    if comp_kws:
        snap_date = data.get("snapshot_date", "unknown")
        if snap_date not in ad_snapshots_by_date:
            ad_snapshots_by_date[snap_date] = []
        ad_snapshots_by_date[snap_date].extend(comp_kws)

    records = data.get("records", [])
    if records:
        keepa_records.extend(records)

all_asins = sorted(all_asins)

col_left, col_right = st.columns([1, 3])

with col_left:
    st.subheader("竞品选择")
    asin_input = st.text_input("竞品ASIN", value=st.session_state.get("comp_asin", ""))

    if all_asins:
        st.caption("检测到的ASIN:")
        selected_from_list = st.selectbox("或从列表选择", [""] + all_asins)
        if selected_from_list:
            asin_input = selected_from_list

    if st.button("开始拆解"):
        if not asin_input:
            st.error("请输入竞品ASIN")
        else:
            st.session_state["comp_asin"] = asin_input
            with st.spinner("正在分析竞品..."):
                try:
                    from src.analysis.competitor import CompetitorTeardown
                    teardown = CompetitorTeardown()

                    filtered_snapshots = []
                    for date_key in sorted(ad_snapshots_by_date.keys()):
                        kws = ad_snapshots_by_date[date_key]
                        matching = [k for k in kws if hasattr(k, "keyword")]
                        if matching:
                            filtered_snapshots.append(matching)

                    filtered_keepa = [
                        r for r in keepa_records
                        if isinstance(r, KeepaDailyRecord)
                    ]

                    timeline = teardown.step6_full_timeline(
                        asin=asin_input,
                        ad_snapshots=filtered_snapshots,
                        keepa_records=filtered_keepa,
                    )
                    st.session_state["competitor_timeline"] = timeline
                    st.success(f"分析完成: {timeline.total_weeks} 周数据")
                except Exception as e:
                    st.error(f"分析失败: {e}")

timeline = st.session_state.get("competitor_timeline")

with col_right:
    if timeline is None:
        st.info("请在左侧选择竞品ASIN并点击开始拆解")
        st.stop()

    if timeline.phase_summary:
        st.metric("阶段总结", timeline.phase_summary)
    st.metric("总周数", timeline.total_weeks)

    st.subheader("多维度时间线")
    render_timeline_chart(timeline)

    st.subheader("每周事件详情")
    if timeline.weekly_events:
        event_rows = []
        for e in timeline.weekly_events:
            event_rows.append({
                "周期": e.week_label,
                "广告词数": e.ad_keyword_count,
                "TOP关键词": e.top_keyword,
                "TOP份额": format_pct_val(e.top_keyword_share),
                "策略": e.top_keyword_strategy,
                "价格($)": e.price,
                "价格变动": e.price_change,
                "优惠券": e.coupon,
                "BSR类目": e.bsr_category,
                "评分": e.rating,
                "评论数": e.reviews,
                "评论变动": e.review_change,
                "广告策略变化": e.ad_strategy_change,
                "关键决策": e.key_decision,
            })
        events_df = pd.DataFrame(event_rows)
        st.dataframe(events_df, use_container_width=True, hide_index=True)
    else:
        st.info("无周事件数据")


def format_pct_val(val):
    return f"{val:.1%}" if val else "N/A"
