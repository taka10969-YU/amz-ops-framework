from __future__ import annotations

from src.data_layer.models import OptimizationAction


class Troubleshooter:

    SCENARIOS: dict[str, list[dict]] = {
        "场景一_广告结构问题": [
            {
                "problem": "关键词重复竞价",
                "symptoms": ["同一词多个活动", "CPC高", "ACOS高"],
                "solution": "合并广告结构，关键词分层管理",
            },
            {
                "problem": "泛广告不否词",
                "symptoms": ["自动/词组点击多不转化", "花费高无订单"],
                "solution": "定期否词，高转化词挪到精准",
            },
            {
                "problem": "未区分生命周期",
                "symptoms": ["老品用新品策略", "花费占比高"],
                "solution": "核心词自然位不掉前提下，减少精准，拓二三级词",
            },
            {
                "problem": "老品无法突破",
                "symptoms": ["SP硬怼", "花费占比高利润低"],
                "solution": "用SP高转化词打SB/SBV",
            },
        ],
        "场景二_预算及出价问题": [
            {
                "problem": "预算不足",
                "symptoms": ["预算提前耗尽", "展现下降", "高ACOS", "广告时段时间不够"],
                "solution": "增加预算，按转化高峰时段分配",
            },
            {
                "problem": "出价过高",
                "symptoms": ["CPC高于市场均值", "ACOS飙升", "点击少花费高"],
                "solution": "降低出价，使用动态竞价策略，参考市场CPC区间",
            },
            {
                "problem": "预算分配不均",
                "symptoms": ["表现好的活动预算不够", "表现差的消耗过多", "整体ACOS偏高"],
                "solution": "预算倾斜法重新分配，低ACOS多预算，高ACOS减预算",
            },
        ],
        "场景三_关键词相关性问题": [
            {
                "problem": "大词无转化",
                "symptoms": ["高展现低转化", "ACOS>50%", "搜索词不精准", "花费高订单少"],
                "solution": "否定泛词，聚焦长尾精准词，降低大词出价",
            },
            {
                "problem": "精准词流量不足",
                "symptoms": ["展现低", "点击少", "预算花不完", "订单量上不去"],
                "solution": "提高出价或扩展匹配类型，检查搜索词是否匹配",
            },
            {
                "problem": "关键词老化",
                "symptoms": ["转化率持续下降", "搜索量减少", "竞争加剧", "ACOS逐步升高"],
                "solution": "挖掘新词，替换低效老词，拓二三级长尾词",
            },
        ],
        "场景四_数据监控问题": [
            {
                "problem": "无数据追踪",
                "symptoms": ["不知ACOS变化", "无法判断效果", "决策凭感觉", "无数据报表"],
                "solution": "建立数据看板，每日监控核心指标(ACOS/CPA/CTR/CVR)",
            },
            {
                "problem": "指标理解错误",
                "symptoms": ["只看点击不看转化", "忽视自然排位", "过度关注单日数据", "忽视趋势"],
                "solution": "建立多维指标体系，关注7天/14天趋势，结合自然位和广告位分析",
            },
        ],
        "场景五_账户系统问题": [
            {
                "problem": "广告被拒",
                "symptoms": ["活动暂停", "无展现", "状态显示拒审", "广告被标记违规"],
                "solution": "检查listing合规性，修改违规内容后重新提交审核",
            },
            {
                "problem": "账户暂停",
                "symptoms": ["所有活动停运", "收到违规通知", "无法创建新活动"],
                "solution": "联系卖家支持，整改违规问题后提交申诉",
            },
            {
                "problem": "系统延迟",
                "symptoms": ["数据不更新", "展现突然为0", "第三方数据不一致", "销售数据延迟"],
                "solution": "等待24-48小时系统更新，联系客服确认数据",
            },
        ],
        "场景六_产品状态问题": [
            {
                "problem": "差评影响",
                "symptoms": ["评分下降", "转化率降低", "广告效果变差", "CTR下降"],
                "solution": "紧急处理差评，优化产品质量，增加好评稀释，暂时降低广告投入",
            },
            {
                "problem": "类目被删",
                "symptoms": ["搜索不到产品", "广告无展现", "流量骤降", "BSR消失"],
                "solution": "重新申请类目，检查listing合规性，联系卖家支持恢复",
            },
            {
                "problem": "断货14天内",
                "symptoms": ["库存不足", "广告暂停", "排名下降", "自然位开始松动"],
                "solution": "紧急补货，降低广告出价减少消耗，保留核心词投放",
            },
            {
                "problem": "断货14天外",
                "symptoms": ["长期无货", "排名大幅下降", "关键词权重丢失", "需重新推广"],
                "solution": "重新推词，恢复广告投放，参考新品策略，预算适当提高",
            },
            {
                "problem": "非热销款",
                "symptoms": ["转化率低", "点击率低", "广告成本高", "库存周转慢"],
                "solution": "评估是否继续投放，考虑清仓促销，减少广告预算",
            },
        ],
        "场景七_节奏问题": [
            {
                "problem": "旺季前",
                "symptoms": ["市场需求上升", "竞争加剧", "CPC上涨", "ABA排名上升"],
                "solution": "提前备货，增加预算，抢占广告位，布局旺季核心词",
            },
            {
                "problem": "旺季中",
                "symptoms": ["订单暴增", "库存消耗快", "广告效率高", "CPC较高"],
                "solution": "保持投放力度，密切监控库存，及时调整出价保持位置",
            },
            {
                "problem": "淡季",
                "symptoms": ["需求下降", "转化率低", "库存积压", "ACOS升高"],
                "solution": "减少预算，聚焦核心词，考虑清仓促销，测试新关键词",
            },
        ],
        "场景八_优化频率": [
            {
                "problem": "大红海市场",
                "symptoms": ["竞争激烈", "排位变化快", "CPC高", "竞品频繁调整"],
                "solution": "每日多次优化，密切监控竞品，快速响应市场变化",
            },
            {
                "problem": "中等竞争市场",
                "symptoms": ["排位相对稳定", "CPC适中", "有改善空间", "变化较慢"],
                "solution": "2-3天优化一次，关注趋势变化，稳步调整",
            },
            {
                "problem": "蓝海市场",
                "symptoms": ["竞争少", "排位稳定", "CPC低", "增长空间大"],
                "solution": "3天优化一次，重点拓词，测试新广告类型",
            },
        ],
    }

    def diagnose(self, symptoms: list[str]) -> list[dict]:
        if not symptoms:
            return []

        results: list[dict] = []
        symptom_lower = [s.lower() for s in symptoms]

        for scenario_name, problems in self.SCENARIOS.items():
            for problem_entry in problems:
                problem_symptoms = problem_entry.get("symptoms", [])
                if not problem_symptoms:
                    continue

                matched: list[str] = []
                for ps in problem_symptoms:
                    ps_lower = ps.lower()
                    for user_s in symptom_lower:
                        if ps_lower in user_s or user_s in ps_lower:
                            matched.append(ps)
                            break

                if matched:
                    confidence = len(matched) / len(problem_symptoms)
                    results.append(
                        {
                            "scenario": scenario_name,
                            "problem": problem_entry["problem"],
                            "matched_symptoms": matched,
                            "all_symptoms": problem_symptoms,
                            "solution": problem_entry["solution"],
                            "confidence": round(confidence, 4),
                        }
                    )

        results.sort(key=lambda r: (len(r["matched_symptoms"]), r["confidence"]), reverse=True)
        return results
