"""Budget & Risk page - Ch14-15"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dashboard.utils import render_budget_pie, format_currency

st.title("预算与风险 (第14-15章)")

tab_budget, tab_profit, tab_risk = st.tabs(["预算分配", "利润模型", "风险看板"])

with tab_budget:
    st.subheader("预算分配计算器")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        monthly_revenue = st.number_input("月销售额 ($)", min_value=0.0, value=10000.0, step=500.0)
        stage_options = {
            "新品期": {"ratio": 0.25, "alloc": {"SP手动精准": 0.50, "SP手动广泛": 0.25, "SP自动": 0.15, "SB品牌": 0.05, "SD再营销": 0.05}},
            "成长期": {"ratio": 0.15, "alloc": {"SP手动精准": 0.35, "SP手动词组": 0.25, "SP手动广泛": 0.15, "SP自动": 0.10, "SB品牌": 0.10, "SD再营销": 0.05}},
            "成熟期": {"ratio": 0.08, "alloc": {"SP手动精准": 0.30, "SP手动词组": 0.15, "SP自动": 0.10, "SB品牌": 0.25, "SD再营销": 0.20}},
            "衰退期": {"ratio": 0.05, "alloc": {"SP手动精准": 0.40, "SP自动": 0.40, "SD再营销": 0.20}},
        }
        budget_stage = st.selectbox("产品阶段", list(stage_options.keys()), key="budget_stage")

    with col_b2:
        stage_info = stage_options[budget_stage]
        ad_ratio = stage_info["ratio"]
        ad_spend = monthly_revenue * ad_ratio
        target_acos = st.number_input("目标ACOS (%)", min_value=0.0, max_value=100.0, value=25.0, step=1.0) / 100

        st.metric("广告费率", f"{ad_ratio:.0%}")
        st.metric("月广告预算", format_currency(ad_spend))
        st.metric("目标ACOS", f"{target_acos:.1%}")
        st.metric("可接受广告费", format_currency(monthly_revenue * target_acos))

    if st.button("计算预算分配", key="calc_budget"):
        alloc = stage_info["alloc"]
        alloc_amounts = {k: v * ad_spend for k, v in alloc.items()}

        st.subheader("按广告类型分配")
        render_budget_pie(alloc_amounts)

        st.subheader("分配明细")
        for ad_type, ratio in alloc.items():
            amount = ratio * ad_spend
            st.write(f"**{ad_type}**: {ratio:.0%} = {format_currency(amount)}")

with tab_profit:
    st.subheader("利润模型计算器")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        price = st.number_input("售价 ($)", min_value=0.0, value=29.99, step=0.5)
        product_cost = st.number_input("产品成本 ($)", min_value=0.0, value=5.0, step=0.5)
        fba_fee = st.number_input("FBA费用 ($)", min_value=0.0, value=6.0, step=0.5)
        shipping_cost = st.number_input("头程运费 ($)", min_value=0.0, value=2.0, step=0.5)

    with col_p2:
        commission_rate = st.number_input("佣金率 (%)", min_value=0.0, max_value=50.0, value=15.0, step=1.0) / 100
        return_rate = st.number_input("退货率 (%)", min_value=0.0, max_value=50.0, value=5.0, step=1.0) / 100
        ad_cost_per_unit = st.number_input("单件广告费 ($)", min_value=0.0, value=4.0, step=0.5)
        other_cost = st.number_input("其他费用 ($)", min_value=0.0, value=0.5, step=0.1)

    if st.button("计算利润", key="calc_profit"):
        commission = price * commission_rate
        return_loss = price * return_rate
        total_cost = product_cost + fba_fee + shipping_cost + commission + ad_cost_per_unit + return_loss + other_cost
        net_profit = price - total_cost
        net_margin = net_profit / price if price > 0 else 0
        actual_acos = ad_cost_per_unit / price if price > 0 else 0
        acceptable_ad = net_profit * 0.7 if net_profit > 0 else 0

        st.subheader("利润分析")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("净利润", format_currency(net_profit))
        mc2.metric("净利率", f"{net_margin:.1%}")
        mc3.metric("实际ACOS", f"{actual_acos:.1%}")
        mc4.metric("可接受广告费/件", format_currency(acceptable_ad))

        st.subheader("成本结构")
        cost_breakdown = {
            "产品成本": product_cost,
            "FBA费用": fba_fee,
            "头程运费": shipping_cost,
            "佣金": commission,
            "广告费": ad_cost_per_unit,
            "退货损失": return_loss,
            "其他费用": other_cost,
            "净利润": net_profit if net_profit > 0 else 0,
        }
        render_budget_pie(cost_breakdown)

        if net_margin < 0:
            st.error(f"亏损! 净利率 {net_margin:.1%}")
        elif net_margin < 0.15:
            st.warning(f"利润偏低, 净利率 {net_margin:.1%}")
        else:
            st.success(f"利润健康, 净利率 {net_margin:.1%}")

with tab_risk:
    st.subheader("风险看板")

    if st.button("生成风险评估", key="gen_risk"):
        risks = []
        library = st.session_state.get("keyword_library")

        if library and library.classified_keywords:
            high_monopoly = [
                kw for kw in library.classified_keywords
                if kw.priority == "first_priority" and kw.traffic_monopoly > 0.5
            ]
            if high_monopoly:
                risks.append({
                    "risk_type": "流量垄断",
                    "trigger_condition": "TOP3流量份额>50%",
                    "current_value": f"{len(high_monopoly)} 个词受垄断",
                    "threshold": "TOP3份额<50%",
                    "severity": "高",
                    "strategy": "寻找长尾替代词",
                    "action": "降低推词优先级,增加长尾词预算",
                    "owner": "运营",
                })

            high_cpc = [
                kw for kw in library.classified_keywords
                if kw.priority == "first_priority" and kw.cpc > 2.0
            ]
            if high_cpc:
                risks.append({
                    "risk_type": "CPC过高",
                    "trigger_condition": "首推词CPC>$2.0",
                    "current_value": f"{len(high_cpc)} 个词CPC过高",
                    "threshold": "CPC<$2.0",
                    "severity": "中",
                    "strategy": "使用词组匹配降低CPC",
                    "action": "调整匹配方式,使用长尾词精准匹配",
                    "owner": "广告",
                })

            negation_count = len(library.negation_list)
            if negation_count > 0:
                risks.append({
                    "risk_type": "无关流量浪费",
                    "trigger_condition": "存在不相关搜索词",
                    "current_value": f"{negation_count} 个否定词",
                    "threshold": "否定词数<总词数30%",
                    "severity": "低",
                    "strategy": "及时添加否定词",
                    "action": "将否定词添加到广告组否定列表",
                    "owner": "广告",
                })

        risks.append({
            "risk_type": "断货风险",
            "trigger_condition": "库存<14天销量",
            "current_value": "未检测",
            "threshold": "库存>30天销量",
            "severity": "高",
            "strategy": "及时补货,降低广告预算",
            "action": "监控库存,提前备货",
            "owner": "供应链",
        })

        risks.append({
            "risk_type": "差评攻击",
            "trigger_condition": "单日新增差评>3",
            "current_value": "未检测",
            "threshold": "差评率<10%",
            "severity": "高",
            "strategy": "增加好评稀释,申诉异常差评",
            "action": "监控评论变化,及时申诉",
            "owner": "运营",
        })

        st.session_state["risks"] = risks

    risks = st.session_state.get("risks")
    if not risks:
        st.info("点击生成风险评估按钮")
        st.stop()

    from dashboard.utils import render_risk_gauge
    render_risk_gauge(risks)

    st.subheader("风险详情")
    for risk in risks:
        severity = risk.get("severity", "低")
        color_map = {"高": "🔴", "中": "🟡", "低": "🟢"}
        icon = color_map.get(severity, "⚪")

        with st.expander(f"{icon} [{severity}] {risk['risk_type']}"):
            c1, c2 = st.columns(2)
            c1.write(f"**触发条件**: {risk['trigger_condition']}")
            c1.write(f"**当前值**: {risk['current_value']}")
            c1.write(f"**阈值**: {risk['threshold']}")
            c2.write(f"**应对策略**: {risk['strategy']}")
            c2.write(f"**执行动作**: {risk['action']}")
            c2.write(f"**责任人**: {risk['owner']}")

    st.subheader("应急预案")
    contingency_plans = {
        "ACOS飙升": "暂停高ACOS关键词,降低竞价20%,检查搜索词报告",
        "转化率骤降": "检查Listing状态(图片/价格/评论),检查竞品动态",
        "BSR大幅下滑": "增加广告预算,启用优惠券,检查库存状态",
        "关键词排名丢失": "加大精准匹配预算,检查Listing相关性",
        "竞品发起价格战": "评估是否跟进,差异化策略,加强品牌广告",
    }
    for scenario, plan in contingency_plans.items():
        st.write(f"**{scenario}**: {plan}")
