from __future__ import annotations

import os
import re
from typing import Any, Optional

import pandas as pd

from src.data_layer.models import (
    AdCampaignRecord,
    CompetitorKeyword,
    KeepaDailyRecord,
    Keyword,
    KeywordClassified,
    KeywordTrafficShare,
)


def _safe_float(val: Any) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("%", "").replace("$", "").replace(",", "").replace("，", "").replace("％", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val: Any) -> int:
    f = _safe_float(val)
    return int(f) if f else 0


def _extract_asins_from_columns(columns: list[str]) -> list[str]:
    asins = []
    for col in columns:
        m = re.match(r"^B0[A-Z0-9]{8}$", str(col).strip())
        if m:
            asins.append(m.group())
    return asins


def _detect_format(filename: str, columns: list[str], sheet_names: list[str] = None) -> str:
    cols_str = " ".join(str(c) for c in columns)
    fname_lower = filename.lower()

    if "asinadkwview" in fname_lower or "广告搜索词" in cols_str or "SP广告流量占比" in cols_str:
        return "sif_ad_view"

    if "asinadkwview" not in fname_lower:
        if "强/弱相关判定" in cols_str or "流量层级" in cols_str:
            return "gpt_categorization"

        has_unique_words = sheet_names and any("unique" in s.lower() for s in sheet_names)
        if has_unique_words and ("SPR" in cols_str or "spr" in cols_str.lower()):
            return "ss_keyword_analyze"

        if "提升与降低-精准_推荐竞价" in cols_str or "提升与降低-精准" in cols_str:
            return "ss_cpc_category"

        if ("客户搜索词" in cols_str or "客戶搜索詞" in cols_str) and "匹配类型" in cols_str:
            return "amazon_sp_report"

        if "搜索词频率排名" in cols_str or "搜索词频的排名" in cols_str or "前3ASIN点击" in cols_str:
            return "amazon_search_terms"

        if "buybox价格" in cols_str.lower() or "buybox" in cols_str.lower() or ("评分" in cols_str and "评论数" in cols_str and "bsr" in cols_str.lower()):
            return "keepa_history"

        asins_in_cols = _extract_asins_from_columns(columns)
        has_type_col = any("关键词类型" in str(c) or "流量词类型" in str(c) or "排名位置" in str(c) for c in columns)
        if asins_in_cols:
            if "有效竞品数" in cols_str:
                return "sif_compare"
            if has_type_col:
                return "ss_compare"
            if "月搜索量" in cols_str or "月購買量" in cols_str:
                return "ss_compare"
            if "关键词" in cols_str:
                return "sif_compare"

    return "unknown"


class FileImporter:
    def __init__(self):
        self._loaded: dict[str, Any] = {}

    def auto_import(self, path: str) -> dict[str, Any]:
        filename = os.path.basename(path)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".xlsx", ".xls", ".csv"):
            return {"format": "unsupported", "path": path}

        if ext == ".csv":
            df = pd.read_csv(path, encoding="utf-8-sig", nrows=0)
            columns = list(df.columns)
            fmt = _detect_format(filename, columns)
        else:
            xls = pd.ExcelFile(path)
            sheet_names = xls.sheet_names
            main_sheet = None
            for sn in sheet_names:
                if sn.lower() not in ("notes", "note"):
                    main_sheet = sn
                    break
            if main_sheet is None:
                return {"format": "unsupported", "path": path}
            columns = self._read_columns(path, main_sheet)
            fmt = _detect_format(filename, columns, sheet_names)

        result = {"format": fmt, "path": path, "filename": filename}
        dispatch = {
            "sif_compare": self.import_sif_compare,
            "sif_ad_view": self.import_sif_ad_view,
            "ss_compare": self.import_ss_compare,
            "ss_keyword_analyze": self.import_ss_keyword_analyze,
            "ss_cpc_category": self.import_ss_cpc_category,
            "keepa_history": self.import_keepa_history,
            "amazon_search_terms": self.import_amazon_search_terms,
            "amazon_sp_report": self.import_amazon_sp_report,
            "gpt_categorization": self.import_gpt_categorization,
        }
        handler = dispatch.get(fmt)
        if handler:
            result["data"] = handler(path)
        else:
            result["data"] = None
        return result

    def import_directory(self, dir_path: str) -> list[dict[str, Any]]:
        results = []
        for root, dirs, files in os.walk(dir_path):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in (".xlsx", ".xls", ".csv"):
                    full_path = os.path.join(root, f)
                    try:
                        r = self.auto_import(full_path)
                        results.append(r)
                    except Exception as e:
                        results.append({"format": "error", "path": full_path, "error": str(e)})
        return results

    def _read_columns(self, path: str, sheet: str) -> list[str]:
        raw = pd.read_excel(path, sheet_name=sheet, header=None, nrows=4)
        for i in range(min(4, len(raw))):
            row = raw.iloc[i].fillna("").astype(str).tolist()
            non_empty = [c.strip() for c in row if c.strip() and c.strip() != "nan"]
            if len(non_empty) >= 3:
                has_kw = any("关键词" in c or "搜索词" in c or "keyword" in c.lower() or "日期" in c or "Buybox" in c or "#" == c.strip() for c in non_empty)
                if has_kw:
                    return [c.strip() for c in row]
        return []

    def _get_header_row(self, path: str, sheet: str) -> int:
        raw = pd.read_excel(path, sheet_name=sheet, header=None, nrows=5)
        for i in range(min(5, len(raw))):
            row = raw.iloc[i].fillna("").astype(str).tolist()
            non_empty = sum(1 for c in row if c.strip() and c.strip() != "nan")
            if non_empty >= 3:
                has_kw = any("关键词" in c or "搜索词" in c or "#" == c.strip() or "日期" in c or "Buybox" in c for c in row)
                if has_kw:
                    return i
        return 1

    def _load_df(self, path: str, sheet: str = None) -> pd.DataFrame:
        if sheet is None:
            xls = pd.ExcelFile(path)
            for sn in xls.sheet_names:
                if sn.lower() not in ("notes", "note"):
                    sheet = sn
                    break
            if sheet is None:
                sheet = xls.sheet_names[0]
        hr = self._get_header_row(path, sheet)
        df = pd.read_excel(path, sheet_name=sheet, header=hr)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    def import_sif_compare(self, path: str) -> dict:
        df = self._load_df(path)
        asins = _extract_asins_from_columns(list(df.columns))
        keywords = []
        traffic_shares = []
        for _, row in df.iterrows():
            kw_text = str(row.get("关键词", "")).strip()
            if not kw_text or kw_text == "nan":
                continue
            kw = Keyword(
                text=kw_text,
                translation=str(row.get("翻译", "")).strip(),
                aba_rank_weekly=_safe_int(row.get("周搜索量排名", row.get("ABA周排名(位)", row.get("ABA周排名", 0)))),
                weekly_search_volume=_safe_int(row.get("周搜索量", 0)),
                product_count=_safe_int(row.get("在售商品数", row.get("搜索商品数", 0))),
            )
            if "有效竞品数" in df.columns:
                kw.product_count = _safe_int(row.get("有效竞品数", kw.product_count)) or kw.product_count
            keywords.append(kw)
            for asin in asins:
                share = _safe_float(row.get(asin, 0))
                type_col = f"{asin}关键词类型"
                rank_label = str(row.get(type_col, "")).strip() if type_col in df.columns else ""
                if share > 0:
                    traffic_shares.append(KeywordTrafficShare(
                        asin=asin, keyword=kw_text,
                        traffic_share=share / 100 if share > 1 else share,
                        rank_label=rank_label,
                    ))
        return {"keywords": keywords, "traffic_shares": traffic_shares, "asins": asins, "dataframe": df}

    def import_sif_ad_view(self, path: str) -> dict:
        xls = pd.ExcelFile(path)
        main_sheet = xls.sheet_names[0]
        snapshot_date = ""
        m = re.search(r"(\d{4}-\d{2}-\d{2})", main_sheet)
        if m:
            snapshot_date = m.group(1)
        df = self._load_df(path, main_sheet)
        competitor_keywords = []
        for _, row in df.iterrows():
            kw_col = None
            for c in ["广告搜索词", "广告关键词", "关键词"]:
                if c in df.columns:
                    kw_col = c
                    break
            kw_text = str(row.get(kw_col, "")).strip() if kw_col else ""
            if not kw_text or kw_text == "nan":
                continue
            sp_col = None
            for c in df.columns:
                if "SP广告流量占比" in c or "SP广告占有率" in c:
                    sp_col = c
                    break
            ls_col = None
            for c in df.columns:
                if "Listing在该词下的SP广告流量份额" in c:
                    ls_col = c
                    break
            competitor_keywords.append(CompetitorKeyword(
                keyword=kw_text,
                translation=str(row.get("翻译", "")).strip(),
                sp_occupancy=_safe_float(row.get(sp_col, 0)) / 100 if _safe_float(row.get(sp_col, 0)) > 1 else _safe_float(row.get(sp_col, 0)),
                listing_traffic_share=_safe_float(row.get(ls_col, 0)) / 100 if _safe_float(row.get(ls_col, 0)) > 1 else _safe_float(row.get(ls_col, 0)),
                campaign_count=_safe_int(row.get("有曝光的广告活动", row.get("包含的活动", 0))),
                ad_group_count=_safe_int(row.get("有曝光的广告组", row.get("包含的广告组", 0))),
                variant_count=_safe_int(row.get("有曝光的变体", row.get("包含的变体", 0))),
                weekly_search_volume=_safe_int(row.get("月搜索量", row.get("搜索量", 0))),
                product_count=_safe_int(row.get("搜索商品数", 0)),
                snapshot_date=snapshot_date,
            ))
        return {"competitor_keywords": competitor_keywords, "snapshot_date": snapshot_date, "dataframe": df}

    def import_ss_compare(self, path: str) -> dict:
        df = self._load_df(path)
        asins = _extract_asins_from_columns(list(df.columns))
        keywords = []
        traffic_shares = []
        for _, row in df.iterrows():
            kw_text = str(row.get("关键词", "")).strip()
            if not kw_text or kw_text == "nan":
                continue
            kw = Keyword(
                text=kw_text,
                translation=str(row.get("关键词翻译", row.get("翻译", ""))).strip(),
                aba_rank_monthly=_safe_int(row.get("ABA排名(月)", row.get("ABA排名", 0))),
                monthly_search_volume=_safe_int(row.get("月搜索量", 0)),
                monthly_purchases=_safe_int(row.get("月购买量", 0)),
                purchase_rate=_safe_float(row.get("购买率", 0)),
                product_count=_safe_int(row.get("商品数", row.get("商品數", 0))),
                cpc_exact=_safe_float(row.get("竞竞价", row.get("競競價", 0))),
            )
            keywords.append(kw)
            for asin in asins:
                share = _safe_float(row.get(asin, 0))
                share = share / 100 if share > 1 else share
                type_col = f"{asin}流量词类型"
                rank_col = f"{asin}关键词排名位置"
                rank_label = ""
                if type_col in df.columns:
                    rank_label = str(row.get(type_col, "")).strip()
                elif rank_col in df.columns:
                    rank_label = str(row.get(rank_col, "")).strip()
                if share > 0:
                    traffic_shares.append(KeywordTrafficShare(
                        asin=asin, keyword=kw_text,
                        traffic_share=share, rank_label=rank_label,
                    ))
        return {"keywords": keywords, "traffic_shares": traffic_shares, "asins": asins, "dataframe": df}

    def import_ss_keyword_analyze(self, path: str) -> dict:
        xls = pd.ExcelFile(path)
        unique_words = {}
        for sn in xls.sheet_names:
            if "unique" in sn.lower():
                uw_df = pd.read_excel(path, sheet_name=sn)
                for _, r in uw_df.iterrows():
                    word = str(r.iloc[0]).strip()
                    freq = _safe_int(r.iloc[1]) if len(r) > 1 else 0
                    if word and word != "nan":
                        unique_words[word] = freq
        df = self._load_df(path)
        keywords = []
        for _, row in df.iterrows():
            kw_text = str(row.get("关键词", "")).strip()
            if not kw_text or kw_text == "nan":
                continue
            cpc_val = str(row.get("PPC竞价", "")).strip().replace("$", "")
            cpc_range = str(row.get("竞竞价范围", "")).strip().replace("$", "")
            cpc_low, cpc_high = 0.0, 0.0
            if "-" in cpc_range:
                parts = cpc_range.split("-")
                cpc_low = _safe_float(parts[0])
                cpc_high = _safe_float(parts[1]) if len(parts) > 1 else 0.0
            keywords.append(Keyword(
                text=kw_text,
                translation=str(row.get("关键词翻译", "")).strip(),
                aba_rank_weekly=_safe_int(row.get("ABA周排名", row.get("ABA排名(周)", 0))),
                aba_rank_monthly=_safe_int(row.get("ABA月排名", row.get("ABA排名(月)", 0))),
                monthly_search_volume=_safe_int(row.get("月搜索量", 0)),
                monthly_purchases=_safe_int(row.get("月购买量", 0)),
                purchase_rate=_safe_float(row.get("购买率", 0)),
                spr=_safe_int(row.get("SPR", 0)),
                click_share_top1=_safe_float(row.get("点击份额", 0)),
                conversion_share_top1=_safe_float(row.get("转化份额", 0)),
                product_count=_safe_int(row.get("商品数", 0)),
                cpc_exact=_safe_float(cpc_val),
                cpc_range_low=cpc_low,
                cpc_range_high=cpc_high,
            ))
        return {"keywords": keywords, "unique_words": unique_words, "dataframe": df}

    def import_ss_cpc_category(self, path: str) -> dict:
        df = self._load_df(path)
        keywords = []
        for _, row in df.iterrows():
            kw_text = str(row.get("关键词", "")).strip()
            if not kw_text or kw_text == "nan":
                continue
            keywords.append(Keyword(
                text=kw_text,
                translation=str(row.get("翻译", "")).strip(),
                weekly_search_volume=_safe_int(row.get("周搜索量", 0)),
                aba_rank_weekly=_safe_int(row.get("周搜索排名", row.get("ABA周排名", 0))),
                click_share_top1=_safe_float(row.get("点击", 0)),
                conversion_share_top1=_safe_float(row.get("转化", 0)),
                product_count=_safe_int(row.get("该类目下关键词收录的产品数", row.get("类目下关键词记录的产品数", 0))),
                cpc_exact=_safe_float(row.get("提升与降低-精准_推荐竞价", row.get("竞价降低-精准_建议竞价", 0))),
                cpc_phrase=_safe_float(row.get("提升与降低-词组_推荐竞价", row.get("竞价降低-词组_建议竞价", 0))),
                cpc_broad=_safe_float(row.get("提升与降低-广泛_推荐竞价", row.get("竞价降低-广泛_建议竞价", 0))),
            ))
        return {"keywords": keywords, "dataframe": df}

    def import_keepa_history(self, path: str) -> dict:
        df = self._load_df(path)
        records = []
        cat_bsr_col = None
        for c in df.columns:
            if "BSR[" in c or ("BSR" in c and "排名" not in c):
                cat_bsr_col = c
                break
        for _, row in df.iterrows():
            date_val = str(row.get("日期", "")).strip()
            if not date_val or date_val == "nan":
                continue
            bsr_cat = _safe_int(row.get(cat_bsr_col, 0)) if cat_bsr_col else 0
            records.append(KeepaDailyRecord(
                date=date_val,
                buybox_price=_safe_float(row.get("Buybox价格($)", 0)),
                price=_safe_float(row.get("价格($)", 0)),
                prime_price=_safe_float(row.get("Prime价格($)", 0)),
                coupon_price=_safe_float(row.get("Coupon价格($)", 0)),
                coupon_discount=str(row.get("Coupon折扣", "")).strip(),
                deal_price=_safe_float(row.get("Deal价格($)", 0)),
                fba_price=_safe_float(row.get("FBA价格($)", 0)),
                fbm_price=_safe_float(row.get("FBM价格($)", 0)),
                list_price=_safe_float(row.get("最高价格($)", 0)),
                bsr_overall=_safe_int(row.get("BSR排名", 0)),
                bsr_category=bsr_cat,
                rating=_safe_float(row.get("评分", 0)),
                reviews=_safe_int(row.get("评论数", 0)),
                buybox_sellers=_safe_int(row.get("买家数", 0)),
            ))
        return {"records": records, "dataframe": df}

    def import_amazon_search_terms(self, path: str) -> dict:
        df = self._load_df(path)
        keywords = []
        for _, row in df.iterrows():
            kw_text = str(row.get("搜索词", "")).strip()
            if not kw_text or kw_text == "nan":
                continue
            keywords.append(Keyword(
                text=kw_text,
                aba_rank_weekly=_safe_int(row.get("搜索词频率排名", row.get("搜索词频的排名", 0))),
                click_share_top3=_safe_float(row.get("前3ASIN点击量占比", row.get("前3ASIN点击份额", 0))),
                conversion_share_top3=_safe_float(row.get("前3ASIN转化占比", row.get("前3ASIN转化份额", 0))),
                top1_asin=str(row.get("#1已点击的ASIN", row.get("#1带来的ASIN", ""))).strip(),
                top1_title=str(row.get("#1商品名称", "")).strip(),
                top1_brand=str(row.get("#1品牌", "")).strip(),
                click_share_top1=_safe_float(row.get("#1点击份额", 0)),
                conversion_share_top1=_safe_float(row.get("#1转化份额", 0)),
            ))
        return {"keywords": keywords, "dataframe": df}

    def import_amazon_sp_report(self, path: str) -> dict:
        df = self._load_df(path)
        records = []
        for _, row in df.iterrows():
            date_val = str(row.get("日期", "")).strip()
            if not date_val or date_val == "nan":
                continue
            records.append(AdCampaignRecord(
                date=date_val,
                sku=str(row.get("SKU", "")).strip(),
                currency=str(row.get("币种", "USD")).strip(),
                campaign_name=str(row.get("广告活动名称", "")).strip(),
                ad_group_name=str(row.get("广告组名称", "")).strip(),
                targeting=str(row.get("投放", "")).strip(),
                match_type=str(row.get("匹配类型", "")).strip(),
                customer_search_term=str(row.get("客户搜索词", "")).strip(),
                impressions=_safe_int(row.get("展示量", 0)),
                clicks=_safe_int(row.get("点击量", 0)),
                ctr=_safe_float(row.get("点击率(CTR)", 0)),
                cpc=_safe_float(row.get("每次点击成本(CPC)", 0)),
                spend=_safe_float(row.get("花费", 0)),
                sales_7d=_safe_float(row.get("7天总销售额", 0)) if str(row.get("7天总销售额", "")).strip() else None,
                acos=_safe_float(row.get("销售成本比(ACOS)", 0)) if str(row.get("销售成本比(ACOS)", "")).strip() else None,
                roas=_safe_float(row.get("投放回报率(ROAS)", 0)) if str(row.get("投放回报率(ROAS)", "")).strip() else None,
                orders_7d=_safe_int(row.get("7天总订单量(#)", 0)) if str(row.get("7天总订单量(#)", "")).strip() else None,
                units_7d=_safe_int(row.get("7天总销量(#)", 0)) if str(row.get("7天总销量(#)", "")).strip() else None,
            ))
        return {"records": records, "dataframe": df}

    def import_gpt_categorization(self, path: str) -> dict:
        df = self._load_df(path)
        classified = []
        for _, row in df.iterrows():
            kw_text = str(row.get("关键词", "")).strip()
            if not kw_text or kw_text == "nan":
                continue
            classified.append(KeywordClassified(
                keyword_text=kw_text,
                translation=str(row.get("翻译", "")).strip(),
                aba_rank_weekly=_safe_int(row.get("ABA周排名(位)", row.get("ABA周排名", row.get("周搜索量排名", 0)))),
                weekly_search_volume=_safe_int(row.get("周搜索量", 0)),
                monthly_search_volume=_safe_int(row.get("月搜索量", 0)),
                relevance=str(row.get("强/弱相关判定", "")).strip(),
                traffic_level=str(row.get("流量层级", "")).strip(),
                effective_competitor_count=_safe_int(row.get("有效竞品数", 0)),
            ))
        return {"classified_keywords": classified, "dataframe": df}
