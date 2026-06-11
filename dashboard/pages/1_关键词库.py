"""Keyword Library page - Ch5"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data_layer.file_importer import FileImporter
from src.data_layer.models import KeywordClassified
from dashboard.utils import (
    render_keyword_table,
    render_traffic_pie,
    render_competition_bubble,
    format_pct,
    format_currency,
)

st.title("关键词库 (第5章)")

if "imported" not in st.session_state:
    st.info("请先在首页导入数据")
    st.stop()

imported = st.session_state["imported"]

col_left, col_right = st.columns([1, 3])

with col_left:
    st.subheader("配置")
    own_asin = st.text_input("自身ASIN", value=st.session_state.get("own_asin", ""))
    category_cvr = st.number_input(
        "类目CVR",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.get("category_cvr", 0.10),
        step=0.01,
        format="%.4f",
    )

    if st.button("构建关键词库"):
        if not own_asin:
            st.error("请输入自身ASIN")
        else:
            st.session_state["own_asin"] = own_asin
            st.session_state["category_cvr"] = category_cvr
            with st.spinner("正在构建关键词库..."):
                try:
                    from src.analysis.keyword_builder import KeywordBuilder
                    builder = KeywordBuilder()
                    library = builder.build(own_asin, category_cvr, imported)
                    st.session_state["keyword_library"] = library
                    st.success(f"构建完成: {library.total_keywords} 个关键词")
                except Exception as e:
                    st.error(f"构建失败: {e}")

library = st.session_state.get("keyword_library")

with col_right:
    if library is None:
        st.info("请在左侧配置参数并点击构建")
        st.stop()

    traffic_colors = {"集中型": "🔴", "完美十字型": "🟡", "离散型": "🟢"}
    indicator = traffic_colors.get(library.traffic_structure, "⚪")
    st.metric("流量结构", f"{indicator} {library.traffic_structure}")
    st.metric("关键词总数", library.total_keywords)
    st.metric("竞品ASIN数", len(library.competitor_asins))

    st.subheader("流量分布")
    all_traffic = []
    for source in imported:
        data = source.get("data")
        if isinstance(data, dict):
            shares = data.get("traffic_shares", [])
            if shares:
                all_traffic.extend(shares)
    if all_traffic:
        render_traffic_pie(all_traffic)

    st.subheader("关键词列表")

    all_keywords = library.classified_keywords

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        tier_filter = st.multiselect(
            "流量层级",
            options=["大词", "中词", "长尾"],
            default=["大词", "中词", "长尾"],
        )
    with filter_col2:
        relevance_filter = st.multiselect(
            "相关性",
            options=["强相关", "中相关", "弱相关", "不相关"],
            default=["强相关", "中相关"],
        )
    with filter_col3:
        priority_filter = st.multiselect(
            "优先级",
            options=["first_priority", "second_priority", "skip", "negation"],
            default=["first_priority", "second_priority"],
        )

    filtered = [
        kw for kw in all_keywords
        if kw.traffic_level in tier_filter
        and kw.relevance in relevance_filter
        and kw.priority in priority_filter
    ]

    st.caption(f"筛选后: {len(filtered)} / {len(all_keywords)} 个关键词")

    show_cols = [
        "keyword_text", "translation", "traffic_level", "relevance",
        "relevance_score", "opportunity_score", "traffic_monopoly",
        "sales_monopoly", "product_count", "cpc", "spr",
        "push_cpa", "daily_budget_needed", "daily_order_target", "priority",
    ]
    render_keyword_table(filtered, show_columns=show_cols)

    st.subheader("竞争分析气泡图")
    render_competition_bubble(filtered)

    if library.negation_list:
        st.subheader("否定词列表")
        neg_df = pd.DataFrame({"否定关键词": library.negation_list})
        st.dataframe(neg_df, use_container_width=True, hide_index=True)

        csv = neg_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "下载否定词列表 CSV",
            data=csv,
            file_name="negation_list.csv",
            mime="text/csv",
        )
