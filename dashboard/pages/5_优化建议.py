"""Optimization Recommendations page - Ch8-9, 16"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

st.title("优化建议 (第8-9章)")

tab_sop, tab_troubleshoot, tab_verify, tab_warnings = st.tabs(
    ["每日SOP", "问题诊断", "推词验证", "何时不动"]
)

with tab_sop:
    st.subheader("每日运营检查清单")

    if "sop_checks" not in st.session_state:
        st.session_state["sop_checks"] = {}

    sop_items = [
        ("ad_review", "检查广告活动状态 (预算/竞价/状态)"),
        ("search_term", "下载并分析搜索词报告"),
        ("acos_monitor", "监控ACOS变化 (日/周/月)"),
        ("keyword_rank", "检查核心关键词排名变化"),
        ("competitor_check", "监控竞品动态 (价格/评论/广告)"),
        ("inventory", "检查库存水平"),
        ("review_check", "查看新评论和评分变化"),
        ("budget_adjust", "根据表现调整预算分配"),
        ("negation_update", "更新否定词列表"),
        ("listing_check", "检查Listing状态 (图片/A+内容)"),
    ]

    all_checked = True
    for key, label in sop_items:
        checked = st.checkbox(
            label,
            value=st.session_state["sop_checks"].get(key, False),
            key=f"sop_{key}",
        )
        st.session_state["sop_checks"][key] = checked
        if not checked:
            all_checked = False

    st.divider()
    if all_checked:
        st.success("今日所有检查项已完成!")
    else:
        completed = sum(1 for v in st.session_state["sop_checks"].values() if v)
        total = len(sop_items)
        st.progress(completed / total, text=f"完成进度: {completed}/{total}")

    st.subheader("周度检查")
    weekly_items = [
        ("weekly_report", "生成周度广告报告"),
        ("weekly_keyword", "更新关键词库"),
        ("weekly_budget", "评估并调整周预算"),
        ("weekly_competitor", "深度竞品分析"),
        ("weekly_optimization", "批量优化操作"),
    ]
    for key, label in weekly_items:
        st.checkbox(label, key=f"weekly_{key}", value=False)

with tab_troubleshoot:
    st.subheader("问题诊断 Q&A")

    symptom_category = st.selectbox(
        "选择症状类别",
        ["广告表现", "流量问题", "转化问题", "排名问题", "利润问题"],
    )

    troubleshooting_db = {
        "广告表现": {
            "ACOS突然升高": {
                "可能原因": [
                    "竞品降价导致转化率下降",
                    "搜索词偏移 (不相关搜索词增加)",
                    "CPC竞价被推高",
                    "季节性需求下降",
                ],
                "诊断步骤": [
                    "检查搜索词报告,找出高花费低转化词",
                    "对比近期竞品价格变化",
                    "查看关键词CPC趋势",
                    "分析类目搜索量趋势",
                ],
                "解决方案": [
                    "添加高花费低转化词到否定列表",
                    "降低高ACOS关键词竞价10-20%",
                    "暂停表现差的广告组",
                    "增加表现好的关键词预算",
                ],
            },
            "广告无曝光": {
                "可能原因": [
                    "竞价过低",
                    "Listing相关性差",
                    "广告预算耗尽过早",
                    "类目节点错误",
                ],
                "诊断步骤": [
                    "检查竞价是否低于建议竞价",
                    "验证Listing类目节点",
                    "检查广告活动预算使用情况",
                    "查看广告投放状态",
                ],
                "解决方案": [
                    "提高竞价至建议竞价以上",
                    "优化Listing标题和后台搜索词",
                    "增加广告组预算",
                    "修正类目节点",
                ],
            },
        },
        "流量问题": {
            "自然流量下降": {
                "可能原因": [
                    "关键词排名下降",
                    "竞品抢占流量",
                    "类目算法调整",
                ],
                "诊断步骤": [
                    "检查核心关键词排名变化",
                    "分析竞品广告和关键词布局",
                    "查看BSR趋势",
                ],
                "解决方案": [
                    "加强核心词广告投放",
                    "优化Listing提升相关性",
                    "增加长尾词覆盖",
                ],
            },
        },
        "转化问题": {
            "转化率下降": {
                "可能原因": [
                    "价格失去竞争力",
                    "差评增加",
                    "竞品优化",
                    "图片/Listing质量问题",
                ],
                "诊断步骤": [
                    "对比竞品价格",
                    "检查近期评论变化",
                    "分析竞品Listing优化动作",
                ],
                "解决方案": [
                    "调整价格或启用优惠券",
                    "积极处理差评",
                    "优化主图和A+内容",
                ],
            },
        },
        "排名问题": {
            "关键词排名下滑": {
                "可能原因": [
                    "广告预算不足",
                    "竞品加大投放",
                    "转化率下降",
                ],
                "诊断步骤": [
                    "检查广告投放数据",
                    "分析竞品广告变化",
                    "检查转化率趋势",
                ],
                "解决方案": [
                    "增加精准匹配预算",
                    "提高核心词竞价",
                    "优化Listing转化要素",
                ],
            },
        },
        "利润问题": {
            "利润率过低": {
                "可能原因": [
                    "广告成本过高",
                    "退货率高",
                    "产品成本上升",
                ],
                "诊断步骤": [
                    "分析各成本占比",
                    "检查退货率和原因",
                    "评估广告效率",
                ],
                "解决方案": [
                    "优化广告结构降低ACOS",
                    "改善产品质量降低退货",
                    "寻找供应链降本空间",
                ],
            },
        },
    }

    category_issues = troubleshooting_db.get(symptom_category, {})
    if category_issues:
        selected_issue = st.selectbox("选择具体问题", list(category_issues.keys()))
        issue_info = category_issues[selected_issue]

        st.subheader(f"诊断: {selected_issue}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.write("**可能原因**")
            for reason in issue_info["可能原因"]:
                st.write(f"- {reason}")
        with c2:
            st.write("**诊断步骤**")
            for i, step in enumerate(issue_info["诊断步骤"], 1):
                st.write(f"{i}. {step}")
        with c3:
            st.write("**解决方案**")
            for solution in issue_info["解决方案"]:
                st.write(f"- {solution}")
    else:
        st.info("该类别暂无诊断数据")

with tab_verify:
    st.subheader("推词验证追踪器")

    library = st.session_state.get("keyword_library")

    if library and library.classified_keywords:
        push_keywords = [
            kw for kw in library.classified_keywords
            if kw.priority in ("first_priority", "second_priority")
        ]

        if push_keywords:
            if "verify_data" not in st.session_state:
                st.session_state["verify_data"] = {}

            st.caption(f"共 {len(push_keywords)} 个推词目标")

            verify_rows = []
            for kw in push_keywords[:30]:
                vk = kw.keyword_text
                status = st.session_state["verify_data"].get(vk, "未开始")
                verify_rows.append({
                    "关键词": vk,
                    "翻译": kw.translation,
                    "优先级": kw.priority,
                    "流量层级": kw.traffic_level,
                    "CPC ($)": kw.cpc,
                    "推词CPA ($)": kw.push_cpa,
                    "日预算 ($)": kw.daily_budget_needed,
                    "日订单目标": kw.daily_order_target,
                    "状态": status,
                })

            vdf = pd.DataFrame(verify_rows)
            st.dataframe(vdf, use_container_width=True, hide_index=True)

            st.subheader("更新推词状态")
            update_kw = st.selectbox(
                "选择关键词",
                options=[kw.keyword_text for kw in push_keywords[:30]],
                key="verify_update_kw",
            )
            new_status = st.selectbox(
                "新状态",
                options=["未开始", "进行中", "已上首页", "已稳定", "失败-暂停"],
                key="verify_new_status",
            )
            if st.button("更新状态"):
                st.session_state["verify_data"][update_kw] = new_status
                st.success(f"已更新: {update_kw} → {new_status}")
                st.rerun()
        else:
            st.info("无推词目标关键词")
    else:
        st.info("请先构建关键词库")

with tab_warnings:
    st.subheader("何时不应操作")

    warnings = [
        {
            "scenario": "刚完成大幅优化",
            "rule": "优化后至少观察48-72小时再调整",
            "reason": "算法需要时间学习新的投放模式,过早调整会干扰数据收集",
            "action": "等待数据稳定后再评估",
        },
        {
            "scenario": "ACOS暂时升高但关键词排名在上升",
            "rule": "不要在推词期因ACOS升高而暂停",
            "reason": "推词期ACOS升高是正常的,关键看排名是否在提升",
            "action": "关注排名趋势而非短期ACOS",
        },
        {
            "scenario": "单日数据波动",
            "rule": "不要基于单日数据做决策",
            "reason": "单日数据噪声大,容易做出错误判断",
            "action": "至少观察3-7天趋势再行动",
        },
        {
            "scenario": "竞争对手大幅降价",
            "rule": "不要盲目跟进价格战",
            "reason": "价格战会损害利润空间,且难以恢复",
            "action": "差异化策略: 强化卖点,增加附加值,优化广告精准度",
        },
        {
            "scenario": "系统Bug或数据延迟",
            "rule": "不要在数据异常时做重要决策",
            "reason": "亚马逊系统偶尔出现数据延迟或错误",
            "action": "等待数据恢复正常后再分析",
        },
        {
            "scenario": "节假日/促销季前",
            "rule": "不要在大型促销前大幅调整结构",
            "reason": "促销期间流量和竞争格局变化大,调整风险高",
            "action": "提前2周完成优化,促销期仅做微调",
        },
        {
            "scenario": "预算有限时",
            "rule": "不要同时推太多关键词",
            "reason": "预算分散导致每个词都推不上去",
            "action": "集中预算推3-5个核心词,推稳后再扩",
        },
        {
            "scenario": "新品期前2周",
            "rule": "不要过早否定搜索词",
            "reason": "新品期数据不足,过早否定会错失潜在机会词",
            "action": "至少积累2周数据后再开始否定",
        },
    ]

    for w in warnings:
        with st.expander(f"⚠️ {w['scenario']}"):
            st.write(f"**规则**: {w['rule']}")
            st.write(f"**原因**: {w['reason']}")
            st.write(f"**正确做法**: {w['action']}")
