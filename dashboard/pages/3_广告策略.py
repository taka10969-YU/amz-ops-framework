"""Ad Strategy page - Ch7"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

st.title("广告策略 (第7章)")

stages = ["新品期 (0-30天)", "成长期 (1-3月)", "成熟期 (3月+)", "衰退期"]
ad_types = ["SP手动精准", "SP手动词组", "SP手动广泛", "SP自动", "SB品牌", "SD再营销"]

if "imported" not in st.session_state:
    st.info("请先在首页导入数据")
    st.stop()

library = st.session_state.get("keyword_library")

col_left, col_right = st.columns([1, 3])

with col_left:
    st.subheader("广告架构配置")

    stage = st.selectbox("产品阶段", stages)

    st.subheader("出价策略")
    bidding_strategies = [
        "动态竞价-仅降低",
        "动态竞价-提高和降低",
        "固定竞价",
    ]
    bidding = st.selectbox("竞价策略", bidding_strategies)

    top_pct = st.slider("首页首位出价调整 (%)", 0, 900, 50, step=10)
    rest_pct = st.slider("其余位置出价调整 (%)", 0, 900, 0, step=10)

    if st.button("生成广告架构"):
        st.session_state["ad_stage"] = stage
        st.session_state["ad_bidding"] = bidding
        st.session_state["ad_top_pct"] = top_pct
        st.session_state["ad_rest_pct"] = rest_pct
        st.success("广告架构已更新")

with col_right:
    if "ad_stage" not in st.session_state:
        st.info("请在左侧配置并生成广告架构")
        st.stop()

    current_stage = st.session_state["ad_stage"]
    current_bidding = st.session_state["ad_bidding"]

    st.subheader("广告架构可视化")

    stage_name = current_stage.split(" ")[0]

    architecture = {
        "新品期": {
            "push_strategy": "精准推词+广泛测词",
            "campaigns": [
                {"name": "精准推词活动", "type": "SP手动精准", "keywords": "first_priority关键词", "budget": "高"},
                {"name": "广泛测词活动", "type": "SP手动广泛", "keywords": "second_priority关键词", "budget": "中"},
                {"name": "自动捡漏活动", "type": "SP自动", "keywords": "自动匹配", "budget": "低"},
            ],
        },
        "成长期": {
            "push_strategy": "扩词+优化ACOS",
            "campaigns": [
                {"name": "精准收割活动", "type": "SP手动精准", "keywords": "已推上首页词", "budget": "中"},
                {"name": "场景词拓展", "type": "SP手动词组", "keywords": "中相关词", "budget": "中"},
                {"name": "长尾覆盖", "type": "SP手动广泛", "keywords": "长尾词", "budget": "低"},
            ],
        },
        "成熟期": {
            "push_strategy": "防守+品牌+再营销",
            "campaigns": [
                {"name": "核心词防守", "type": "SP手动精准", "keywords": "核心流量词", "budget": "高"},
                {"name": "品牌搜索", "type": "SB品牌", "keywords": "品牌词", "budget": "中"},
                {"name": "再营销", "type": "SD再营销", "keywords": "浏览未购买", "budget": "低"},
            ],
        },
        "衰退期": {
            "push_strategy": "收割+清仓",
            "campaigns": [
                {"name": "低价收割", "type": "SP手动精准", "keywords": "转化词", "budget": "极低"},
                {"name": "清仓促销", "type": "SP自动", "keywords": "自动匹配", "budget": "极低"},
            ],
        },
    }

    arch = architecture.get(stage_name, architecture["新品期"])

    st.metric("当前阶段", current_stage)
    st.metric("推词策略", arch["push_strategy"])
    st.metric("竞价策略", current_bidding)
    st.metric("首页首位调整", f"+{st.session_state['ad_top_pct']}%")
    st.metric("其余位置调整", f"+{st.session_state['rest_pct']}%")

    st.subheader("活动结构")
    for camp in arch["campaigns"]:
        with st.expander(f"📋 {camp['name']} ({camp['type']})"):
            st.write(f"**类型**: {camp['type']}")
            st.write(f"**关键词来源**: {camp['keywords']}")
            st.write(f"**预算等级**: {camp['budget']}")

    st.subheader("推荐关键词分配")
    if library and library.classified_keywords:
        first_p = [kw for kw in library.classified_keywords if kw.priority == "first_priority"]
        second_p = [kw for kw in library.classified_keywords if kw.priority == "second_priority"]

        c1, c2, c3 = st.columns(3)
        c1.metric("第一优先级词数", len(first_p))
        c2.metric("第二优先级词数", len(second_p))
        c3.metric("否定词数", len(library.negation_list))

        if first_p:
            st.caption("第一优先级关键词 (精准推词):")
            for kw in first_p[:20]:
                st.write(f"- {kw.keyword_text} | CPC: ${kw.cpc:.2f} | 机会分: {kw.opportunity_score:.2f}")
            if len(first_p) > 20:
                st.caption(f"...还有 {len(first_p) - 20} 个词")
    else:
        st.info("请先构建关键词库以获取推荐关键词")

    st.subheader("否词策略")
    if library and library.negation_list:
        st.caption(f"共 {len(library.negation_list)} 个否定词")
        neg_display = ", ".join(library.negation_list[:50])
        st.text(neg_display)
        if len(library.negation_list) > 50:
            st.caption(f"...还有 {len(library.negation_list) - 50} 个")
    else:
        st.info("构建关键词库后将自动生成否定词列表")
