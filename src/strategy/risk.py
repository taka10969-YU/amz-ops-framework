from __future__ import annotations

from src.data_layer.models import RiskAlert
from config.settings import DEFAULT_THRESHOLDS


class RiskManager:

    RISK_CATALOG = [
        "广告花费飙升",
        "自然位掉落",
        "竞品反击",
        "差评攻击",
        "断货风险",
        "类目被删",
        "账户限制",
        "VCPM虚好",
    ]

    def identify_risks(self, current_state: dict) -> list[RiskAlert]:
        alerts: list[RiskAlert] = []
        if not current_state:
            return alerts

        daily_spend = current_state.get("daily_spend", 0)
        avg_spend = current_state.get("avg_spend", 0)
        if avg_spend and daily_spend > 0 and daily_spend > avg_spend * 1.5:
            alerts.append(RiskAlert(
                risk_type="广告花费飙升",
                trigger_condition="daily_spend > avg_spend * 1.5",
                current_value=str(daily_spend),
                threshold=str(avg_spend * 1.5),
                severity="高",
                strategy="减轻",
                action="检查竞价调整、否定无效词、暂停高花费低转化广告组",
                owner="广告运营",
            ))

        core_position = current_state.get("core_keyword_position", 0)
        if core_position > 30:
            alerts.append(RiskAlert(
                risk_type="自然位掉落",
                trigger_condition="core_keyword_position > 30",
                current_value=str(core_position),
                threshold="30",
                severity="高",
                strategy="减轻",
                action="加强精准投放、检查Listing质量、增加广告预算保护核心词",
                owner="广告运营",
            ))

        comp_spend_increase = current_state.get("competitor_spend_increase", 0)
        if comp_spend_increase > 50:
            alerts.append(RiskAlert(
                risk_type="竞品反击",
                trigger_condition="competitor_spend_increase > 50%",
                current_value=f"{comp_spend_increase}%",
                threshold="50%",
                severity="中",
                strategy="减轻",
                action="监控竞品动态、差异化投放、强化自身优势词防御",
                owner="广告运营",
            ))

        rating_drop = current_state.get("rating_drop_weekly", 0)
        if rating_drop >= 0.3:
            alerts.append(RiskAlert(
                risk_type="差评攻击",
                trigger_condition="rating_drop >= 0.3 in one week",
                current_value=str(rating_drop),
                threshold="0.3",
                severity="高",
                strategy="规避",
                action="分析差评来源、联系亚马逊申诉异常差评、加大好评引导",
                owner="客服/运营",
            ))

        inventory_days = current_state.get("inventory_days", 999)
        if inventory_days < 7:
            alerts.append(RiskAlert(
                risk_type="断货风险",
                trigger_condition="inventory_days < 7",
                current_value=str(inventory_days),
                threshold="7",
                severity="紧急",
                strategy="规避",
                action="紧急补货、适度提价、降低广告预算减少消耗速度",
                owner="供应链",
            ))

        auto_impressions = current_state.get("auto_ad_impressions", -1)
        if auto_impressions == 0:
            alerts.append(RiskAlert(
                risk_type="类目被删",
                trigger_condition="auto_ad_impressions == 0",
                current_value=str(auto_impressions),
                threshold="0",
                severity="紧急",
                strategy="规避",
                action="检查类目节点、联系卖家支持恢复类目、检查Listing合规性",
                owner="运营",
            ))

        if current_state.get("account_restricted", False):
            alerts.append(RiskAlert(
                risk_type="账户限制",
                trigger_condition="account_restricted flag",
                current_value="True",
                threshold="False",
                severity="紧急",
                strategy="转移",
                action="立即联系卖家支持、检查违规原因、准备申诉材料",
                owner="管理层",
            ))

        vcpm_good = current_state.get("vcpm_data_good", False)
        total_orders = current_state.get("total_orders", 0)
        prev_orders = current_state.get("prev_total_orders", 0)
        if vcpm_good and total_orders <= prev_orders:
            alerts.append(RiskAlert(
                risk_type="VCPM虚好",
                trigger_condition="vcpm_data_good but total_orders flat",
                current_value=f"orders={total_orders}, prev={prev_orders}",
                threshold="orders should grow",
                severity="中",
                strategy="减轻",
                action="切换为CPC投放、检查流量质量、否定无效展示位",
                owner="广告运营",
            ))

        return alerts

    def generate_contingency(self, risks: list[RiskAlert]) -> list[dict]:
        if not risks:
            return []

        strategy_actions = {
            "规避": [
                "识别风险源头并主动回避",
                "品牌垄断词不做正面竞争",
                "下沉市场推广需谨慎评估",
            ],
            "转移": [
                "使用FBA减少物流风险",
                "注册品牌降低跟卖风险",
                "购买相关保险覆盖损失",
            ],
            "减轻": [
                "分散关键词投放降低集中风险",
                "建立否定词库减少无效消耗",
                "多广告类型组合分散流量来源",
            ],
            "接受": [
                "低概率风险持续监控即可",
                "不可避免的季节性波动正常应对",
            ],
        }

        contingency: list[dict] = []
        severity_order = {"紧急": 0, "高": 1, "中": 2, "低": 3}
        sorted_risks = sorted(risks, key=lambda r: severity_order.get(r.severity, 4))

        for risk in sorted_risks:
            actions = strategy_actions.get(risk.strategy, strategy_actions["减轻"])
            contingency.append({
                "risk_type": risk.risk_type,
                "severity": risk.severity,
                "strategy": risk.strategy,
                "immediate_action": risk.action,
                "strategy_actions": actions,
                "owner": risk.owner,
            })

        return contingency

    def should_not_act(self, state: dict) -> list[str]:
        reasons: list[str] = []
        if not state:
            return reasons

        ctr = state.get("ctr", 0)
        cvr = state.get("cvr", 0)
        track_avg_ctr = state.get("track_avg_ctr", 0)
        track_avg_cvr = state.get("track_avg_cvr", 0)
        if track_avg_ctr > 0 and track_avg_cvr > 0:
            if ctr < track_avg_ctr and cvr < track_avg_cvr:
                reasons.append("CTR和CVR均低于轨道均值，不应增加付费流量")

        aba_decline_weeks = state.get("aba_decline_weeks", 0)
        market_down_threshold = DEFAULT_THRESHOLDS.get("market_down_weeks", 2)
        if aba_decline_weeks >= market_down_threshold:
            reasons.append(f"市场下行已{aba_decline_weeks}周，不应强行推词")

        traffic_monopoly = state.get("traffic_monopoly", 0)
        sales_monopoly = state.get("sales_monopoly", 0)
        monopoly_traffic = DEFAULT_THRESHOLDS.get("monopoly_traffic_high", 0.50)
        monopoly_sales = DEFAULT_THRESHOLDS.get("monopoly_sales_high", 0.30)
        if traffic_monopoly > monopoly_traffic and sales_monopoly > monopoly_sales:
            reasons.append("品牌垄断市场，直接推词效果差，需差异化策略")

        net_margin = state.get("net_margin", 0)
        ad_spend_ratio = state.get("ad_spend_ratio", 0)
        if net_margin < 0.15 and ad_spend_ratio > 0.15:
            reasons.append("利润率<15%且广告占比>15%，应减少广告而非增加")

        push_cost = state.get("push_cost", 0)
        gross_profit = state.get("gross_profit", 0)
        if gross_profit > 0 and push_cost > gross_profit * 3:
            reasons.append("推词成本超过毛利3倍，应更换关键词")

        rating = state.get("rating", 0)
        if rating < 4.0 and rating > 0:
            reasons.append("产品评分<4.0，应优先改进产品而非加大广告")

        return reasons
