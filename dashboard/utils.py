"""Shared visualization utilities"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st


def render_keyword_table(keywords, show_columns=None):
    if not keywords:
        st.info("暂无关键词数据")
        return

    rows = []
    for kw in keywords:
        if hasattr(kw, "model_dump"):
            rows.append(kw.model_dump())
        elif isinstance(kw, dict):
            rows.append(kw)
        else:
            rows.append(vars(kw))

    df = pd.DataFrame(rows)
    if show_columns:
        available = [c for c in show_columns if c in df.columns]
        if available:
            df = df[available]

    rename_map = {
        "keyword_text": "关键词",
        "translation": "翻译",
        "aba_rank_weekly": "ABA周排名",
        "weekly_search_volume": "周搜索量",
        "monthly_search_volume": "月搜索量",
        "traffic_level": "流量层级",
        "relevance": "相关性",
        "relevance_score": "相关性得分",
        "traffic_monopoly": "流量垄断度",
        "sales_monopoly": "销量垄断度",
        "opportunity_score": "机会得分",
        "product_count": "商品数",
        "cpc": "CPC",
        "spr": "SPR",
        "push_cpa": "推词CPA",
        "daily_budget_needed": "日预算需求",
        "daily_order_target": "日订单目标",
        "priority": "优先级",
        "top1_click_share": "TOP1点击份额",
        "top1_conversion_share": "TOP1转化份额",
        "top1_asin": "TOP1 ASIN",
        "top1_brand": "TOP1品牌",
        "effective_competitor_count": "有效竞品数",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_traffic_pie(traffic_shares):
    if not traffic_shares:
        st.info("暂无流量分布数据")
        return

    rows = []
    for ts in traffic_shares:
        if hasattr(ts, "model_dump"):
            d = ts.model_dump()
        elif isinstance(ts, dict):
            d = ts
        else:
            d = vars(ts)
        rows.append(d)

    df = pd.DataFrame(rows)
    asin_col = "asin" if "asin" in df.columns else df.columns[0]
    share_col = "traffic_share" if "traffic_share" in df.columns else None
    if share_col is None:
        for c in df.columns:
            if "share" in c.lower() or "占比" in c:
                share_col = c
                break

    if share_col is None:
        st.warning("无法识别流量份额列")
        return

    agg = df.groupby(asin_col)[share_col].sum().reset_index()
    agg = agg.sort_values(share_col, ascending=False)

    fig = px.pie(
        agg,
        names=asin_col,
        values=share_col,
        title="关键词流量分布",
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)


def render_competition_bubble(keywords):
    if not keywords:
        st.info("暂无竞争分析数据")
        return

    rows = []
    for kw in keywords:
        if hasattr(kw, "model_dump"):
            rows.append(kw.model_dump())
        elif isinstance(kw, dict):
            rows.append(kw)
        else:
            rows.append(vars(kw))

    df = pd.DataFrame(rows)

    x_col = "aba_rank_weekly" if "aba_rank_weekly" in df.columns else None
    y_col = "cpc" if "cpc" in df.columns else None
    size_col = "weekly_search_volume" if "weekly_search_volume" in df.columns else None
    color_col = "opportunity_score" if "opportunity_score" in df.columns else None

    if not all([x_col, y_col, size_col, color_col]):
        st.warning("缺少必要字段，无法绘制竞争气泡图")
        return

    df = df[df[x_col] > 0].copy()

    fig = px.scatter(
        df,
        x=x_col,
        y=y_col,
        size=size_col,
        color=color_col,
        hover_name="keyword_text" if "keyword_text" in df.columns else None,
        title="竞争分析气泡图 (X=ABA排名, Y=CPC, 大小=搜索量, 颜色=机会分)",
        color_continuous_scale="RdYlGn",
    )
    fig.update_layout(xaxis_title="ABA周排名", yaxis_title="CPC ($)")
    fig.update_xaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)


def render_timeline_chart(timeline):
    if not timeline or not hasattr(timeline, "weekly_events") or not timeline.weekly_events:
        st.info("暂无时间线数据")
        return

    events = timeline.weekly_events
    labels = [e.week_label for e in events]
    kw_counts = [e.ad_keyword_count for e in events]
    prices = [e.price for e in events]
    bsrs = [e.bsr_category for e in events]
    reviews = [e.reviews for e in events]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=labels, y=kw_counts, name="广告关键词数",
        yaxis="y1", mode="lines+markers",
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=prices, name="价格 ($)",
        yaxis="y2", mode="lines+markers",
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=bsrs, name="BSR类目排名",
        yaxis="y3", mode="lines+markers",
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=reviews, name="评论数",
        yaxis="y4", mode="lines+markers",
    ))

    fig.update_layout(
        title=f"竞品时间线 - {timeline.asin}",
        xaxis_title="周期",
        yaxis=dict(title="广告关键词数", side="left"),
        yaxis2=dict(title="价格 ($)", overlaying="y", side="right", anchor="x"),
        yaxis3=dict(title="BSR排名", overlaying="y", side="right", anchor="free", position=0.85),
        yaxis4=dict(title="评论数", overlaying="y", side="right", anchor="free", position=0.95),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_budget_pie(allocations):
    if not allocations:
        st.info("暂无预算分配数据")
        return

    labels = list(allocations.keys())
    values = list(allocations.values())

    fig = px.pie(
        names=labels,
        values=values,
        title="预算分配",
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label+value")
    st.plotly_chart(fig, use_container_width=True)


def render_risk_gauge(risks):
    if not risks:
        st.info("暂无风险数据")
        return

    severity_colors = {"高": "red", "中": "orange", "低": "green"}

    high_count = sum(1 for r in risks if _get_field(r, "severity") == "高")
    med_count = sum(1 for r in risks if _get_field(r, "severity") == "中")
    low_count = sum(1 for r in risks if _get_field(r, "severity") == "低")

    col1, col2, col3 = st.columns(3)
    col1.metric("高风险", high_count, delta=None)
    col1.metric("中风险", med_count, delta=None)
    col1.metric("低风险", low_count, delta=None)

    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=high_count * 3 + med_count * 2 + low_count,
        gauge={
            "axis": {"range": [None, len(risks) * 3]},
            "bar": {"color": "darkred"},
            "steps": [
                {"range": [0, len(risks)], "color": "lightgreen"},
                {"range": [len(risks), len(risks) * 2], "color": "lightyellow"},
                {"range": [len(risks) * 2, len(risks) * 3], "color": "lightcoral"},
            ],
        },
        title={"text": "风险指数"},
    ))
    st.plotly_chart(fig, use_container_width=True)


def _get_field(obj, field):
    if hasattr(obj, field):
        return getattr(obj, field)
    if isinstance(obj, dict):
        return obj.get(field, "")
    return ""


def format_pct(val):
    return f"{val:.1%}" if val else "N/A"


def format_currency(val):
    return f"${val:.2f}" if val else "N/A"
