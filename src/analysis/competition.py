from src.data_layer.models import (
    Product,
    KeywordClassified,
    CompetitorKeyword,
    KeepaDailyRecord,
    AttackPlan,
)


class CompetitionAssessor:
    def classify_competitors(self, products: list[Product]) -> dict[str, list[Product]]:
        tiers = {"头部": [], "腰部": [], "尾部": []}
        for product in products:
            if product.bsr_category <= 0:
                tiers["尾部"].append(product)
            elif product.bsr_category <= 10:
                tiers["头部"].append(product)
            elif product.bsr_category <= 50:
                tiers["腰部"].append(product)
            else:
                tiers["尾部"].append(product)
        return tiers

    def find_weaknesses(
        self,
        competitor: Product,
        ad_data: list[CompetitorKeyword] | None = None,
        keepa_data: list[KeepaDailyRecord] | None = None,
    ) -> list[dict]:
        weaknesses = []

        weaknesses.append(
            {
                "weakness": "视觉方案差",
                "discovery_method": "人工检查Listing图片、A+、视频质量",
                "attack_method": "升级主图、增加视频、优化A+内容，视觉碾压",
                "priority": "高",
            }
        )

        if ad_data is not None and len(ad_data) < 20:
            weaknesses.append(
                {
                    "weakness": "广告投入少",
                    "discovery_method": f"广告关键词数量仅{len(ad_data)}个，低于20个阈值",
                    "attack_method": "加大广告覆盖，抢占其未覆盖的关键词流量",
                    "priority": "高",
                }
            )

        if competitor.rating < 4.0:
            weaknesses.append(
                {
                    "weakness": "评论评分低",
                    "discovery_method": f"当前评分{competitor.rating}，低于4.0阈值",
                    "attack_method": "在标题/五点中强调品质优势，截取对评分敏感的买家",
                    "priority": "中",
                }
            )

        if keepa_data and len(keepa_data) >= 2:
            records_sorted = sorted(keepa_data, key=lambda r: r.date)
            review_counts = [
                r.reviews for r in records_sorted if r.reviews > 0
            ]
            if len(review_counts) >= 2:
                first = review_counts[0]
                last = review_counts[-1]
                total = len(review_counts)
                recent_half = review_counts[max(0, total // 2) :]
                early_half = review_counts[: max(1, total // 2)]
                avg_early = sum(early_half) / len(early_half)
                avg_recent = sum(recent_half) / len(recent_half)
                if first > 0 and last > 0:
                    if (avg_recent - avg_early) / avg_early > 0.3:
                        weaknesses.append(
                            {
                                "weakness": "翻新链接",
                                "discovery_method": "评论增速异常，疑似翻新",
                                "attack_method": "在广告中标注自身产品为老牌可靠选择，打击其信任基础",
                                "priority": "中",
                            }
                        )

        if ad_data and len(ad_data) > 0:
            total_traffic = sum(
                kw.listing_traffic_share for kw in ad_data
            )
            if total_traffic > 0:
                max_share = max(kw.listing_traffic_share for kw in ad_data)
                if max_share / total_traffic > 0.6:
                    top_kw = max(ad_data, key=lambda kw: kw.listing_traffic_share)
                    weaknesses.append(
                        {
                            "weakness": "单一关键词依赖",
                            "discovery_method": f"关键词'{top_kw.keyword}'占流量{max_share / total_traffic:.0%}，超过60%阈值",
                            "attack_method": "集中攻击其核心关键词，抢夺流量命脉",
                            "priority": "高",
                        }
                    )

        if keepa_data and len(keepa_data) >= 4:
            records_sorted = sorted(keepa_data, key=lambda r: r.date)
            prices = []
            for r in records_sorted:
                p = r.buybox_price if r.buybox_price > 0 else r.price
                if p > 0:
                    prices.append(p)
            if len(prices) >= 4:
                recent_4 = prices[-4:]
                if all(recent_4[i] < recent_4[i - 1] for i in range(1, len(recent_4))):
                    weaknesses.append(
                        {
                            "weakness": "价格战不可持续",
                            "discovery_method": f"连续4周降价，从{recent_4[0]}降至{recent_4[-1]}",
                            "attack_method": "保持合理定价，用优惠券/Prime折扣替代直接降价",
                            "priority": "中",
                        }
                    )

        return weaknesses

    def generate_attack_matrix(
        self,
        competitors: list[Product],
        ad_data_map: dict[str, list] | None = None,
        keepa_data_map: dict[str, list] | None = None,
    ) -> list[dict]:
        if not competitors:
            return []

        if ad_data_map is None:
            ad_data_map = {}
        if keepa_data_map is None:
            keepa_data_map = {}

        matrix = []
        for comp in competitors:
            ad_data = ad_data_map.get(comp.asin)
            keepa_data = keepa_data_map.get(comp.asin)
            comp_weaknesses = self.find_weaknesses(comp, ad_data, keepa_data)

            if not comp_weaknesses:
                matrix.append(
                    {
                        "asin": comp.asin,
                        "title": comp.title,
                        "bsr_category": comp.bsr_category,
                        "rating": comp.rating,
                        "weaknesses": [],
                        "attack_priority": "低",
                    }
                )
            else:
                has_high = any(w["priority"] == "高" for w in comp_weaknesses)
                matrix.append(
                    {
                        "asin": comp.asin,
                        "title": comp.title,
                        "bsr_category": comp.bsr_category,
                        "rating": comp.rating,
                        "weaknesses": comp_weaknesses,
                        "attack_priority": "高" if has_high else "中",
                    }
                )

        priority_order = {"高": 0, "中": 1, "低": 2}
        matrix.sort(key=lambda x: priority_order.get(x["attack_priority"], 3))
        return matrix

    def generate_overtake_plan(
        self,
        own_product: Product,
        competitor: Product,
        own_keywords: list[KeywordClassified] | None = None,
        competitor_ad_data: list[CompetitorKeyword] | None = None,
        competitor_keepa: list[KeepaDailyRecord] | None = None,
    ) -> AttackPlan:
        weaknesses = self.find_weaknesses(competitor, competitor_ad_data, competitor_keepa)

        copy_actions = []
        differentiate_actions = []

        if competitor_ad_data:
            sorted_keywords = sorted(
                competitor_ad_data,
                key=lambda kw: kw.listing_traffic_share,
                reverse=True,
            )
            for kw in sorted_keywords[:5]:
                copy_actions.append(
                    f"复制已验证关键词: '{kw.keyword}' (流量占比{kw.listing_traffic_share:.0%})"
                )

            low_competition = [
                kw for kw in competitor_ad_data if kw.product_count > 0 and kw.weekly_search_volume / kw.product_count > 10
            ]
            if low_competition:
                differentiate_actions.append(
                    "竞争对手未充分覆盖的低竞争高搜索词，优先抢占"
                )

        if competitor.rating < 4.0:
            differentiate_actions.append(
                "对手评分偏低，强化品质卖点与好评展示"
            )

        if competitor.price > own_product.price:
            differentiate_actions.append(
                f"对手定价${competitor.price}，我方${own_product.price}，利用价格优势"
            )

        copy_actions.append("复制其广告结构中有效的投放方式")

        if competitor_keepa and len(competitor_keepa) >= 2:
            records = sorted(competitor_keepa, key=lambda r: r.date)
            latest = records[-1]
            if latest.coupon_discount:
                copy_actions.append(
                    f"复制优惠券策略: {latest.coupon_discount}"
                )

        phased_plan = [
            {
                "阶段": "短期 (1-3月)",
                "目标": "复制已验证策略，快速起量",
                "行动": [
                    "复制对手核心关键词的广告投放",
                    "制定与其匹配的定价/优惠券策略",
                    "集中推词预算抢夺核心搜索位",
                ],
            },
            {
                "阶段": "中期 (3-6月)",
                "目标": "扩展未覆盖词，建立差异化",
                "行动": [
                    "挖掘对手未覆盖的关键词机会",
                    "强化视觉/品质/服务差异化",
                    "启动品牌广告(SB/SBV)建立品牌认知",
                ],
            },
            {
                "阶段": "长期 (6-12月)",
                "目标": "建立关键词护城河，降低广告依赖",
                "行动": [
                    "巩固自然排名，降低核心词CPC",
                    "建立长尾关键词矩阵",
                    "将广告重心转向防御和增量",
                ],
            },
        ]

        return AttackPlan(
            competitor_asin=competitor.asin,
            weaknesses=weaknesses,
            copy_actions=copy_actions,
            differentiate_actions=differentiate_actions,
            phased_plan=phased_plan,
        )
