from __future__ import annotations

import asyncio
import base64
import csv
import json
import os
import sys

import pandas as pd
import requests as req_lib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.data_layer.models import Keyword, KeywordTrafficShare


class SellerSpriteScraper:
    def __init__(self, phone: str, password: str,
                 tt_user: str = "", tt_pass: str = "",
                 tt_api: str = "http://api.ttshitu.com",
                 headless: bool = True):
        self.phone = phone
        self.password = password
        self.tt_user = tt_user
        self.tt_pass = tt_pass
        self.tt_api = tt_api
        self.headless = headless
        self._browser = None
        self._context = None
        self._page = None

    def _aes_encrypt(self, text: str, key: str) -> str:
        cipher = AES.new(key.encode("utf-8"), AES.MODE_ECB)
        return base64.b64encode(
            cipher.encrypt(pad(text.encode("utf-8"), AES.block_size))
        ).decode("utf-8")

    def _solve_captcha(self, bg_b64: str, jigsaw_b64: str = None) -> dict:
        data = {
            "username": self.tt_user, "password": self.tt_pass,
            "typeid": "18" if jigsaw_b64 else "33",
            "image": jigsaw_b64 or bg_b64,
        }
        if jigsaw_b64:
            data["imageback"] = bg_b64
        resp = req_lib.post(f"{self.tt_api}/predict", json=data, timeout=60)
        r = resp.json()
        return r["data"] if r.get("success") else {"error": r.get("message")}

    async def _init_browser(self):
        from playwright.async_api import async_playwright
        from playwright_stealth import Stealth

        p = await async_playwright().start()
        self._playwright = p
        self._browser = await p.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        self._page = await self._context.new_page()
        s = Stealth()
        await s.apply_stealth_async(self._page)

    async def login(self) -> bool:
        if not self._page:
            await self._init_browser()
        page = self._page
        await page.goto(
            "https://www.sellersprite.com/cn/w/user/login",
            timeout=60000, wait_until="domcontentloaded",
        )
        await asyncio.sleep(5)
        for inp in await page.query_selector_all('input[name="email"]'):
            if await inp.is_visible():
                await inp.click(force=True)
                await inp.fill(self.phone)
                break
        for inp in await page.query_selector_all('input[type="password"]'):
            if await inp.is_visible():
                await inp.click(force=True)
                await inp.fill(self.password)
                break
        for btn in await page.query_selector_all('button[type="submit"]'):
            if await btn.is_visible() and "登录" in await btn.inner_text():
                await btn.click(force=True)
                break
        await asyncio.sleep(10)
        if "login" in page.url:
            return False
        return True

    async def keyword_reverse_lookup(
        self, asins: list[str], marketplace: str = "US"
    ) -> pd.DataFrame:
        if not self._page:
            await self._init_browser()
            if not await self.login():
                raise RuntimeError("Login failed")
        page = self._page
        asin_str = "|".join(asins)
        url = f"https://www.sellersprite.com/v2/keyword-reverse/{marketplace}/{asin_str}?v=false&q="
        captcha_data_list = []

        async def cap_handler(response):
            if "/captcha/get" in response.url:
                try:
                    d = await response.json()
                    if d.get("repData", {}).get("originalImageBase64"):
                        captcha_data_list.append(d["repData"])
                except Exception:
                    pass

        page.on("response", cap_handler)
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(15)

        if captcha_data_list:
            rep = captcha_data_list[-1]
            bg = rep.get("originalImageBase64", "")
            jig = rep.get("jigsawImageBase64", "")
            sk = rep.get("secretKey", "")
            token = rep.get("token", "")
            solve = self._solve_captcha(bg, jig if jig else None)
            if not solve.get("error"):
                ans = str(solve["result"])
                x = int(ans.split(",")[0]) if "," in ans else int(ans)
                enc = self._aes_encrypt(json.dumps({"x": x, "y": 5}), sk)
                await page.evaluate(f"""
                    async () => {{
                        const r = await fetch('/captcha/check', {{
                            method: 'POST', credentials: 'include',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{captchaType: 'blockPuzzle', pointJson: '{enc}', token: '{token}'}})
                        }});
                        return await r.text();
                    }}
                """)
                await asyncio.sleep(3)
                await page.reload(timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(15)

        for _ in range(12):
            await asyncio.sleep(5)
            rows_count = await page.evaluate("""
                () => {
                    let count = 0;
                    document.querySelectorAll('table tr').forEach((tr, idx) => {
                        if (idx > 0) {
                            const t = tr.innerText.trim();
                            if (t && !t.includes('暂无') && !t.includes('加载中')) count++;
                        }
                    });
                    return count;
                }
            """)
            if rows_count > 1:
                break

        tables_data = await page.evaluate("""
            () => {
                const result = [];
                document.querySelectorAll('table').forEach(table => {
                    const rows = [];
                    table.querySelectorAll('tr').forEach(tr => {
                        const cells = [];
                        tr.querySelectorAll('th, td').forEach(cell => cells.push(cell.innerText.trim()));
                        if (cells.length > 0 && cells.some(c => c)) rows.push(cells);
                    });
                    if (rows.length > 0) result.push(rows);
                });
                return result;
            }
        """)

        page.remove_listener("response", cap_handler)

        if tables_data and len(tables_data[0]) > 1:
            header = tables_data[0][0]
            data_rows = tables_data[0][1:]
            df = pd.DataFrame(data_rows, columns=header[: len(data_rows[0])] if data_rows else header)
            return df
        return pd.DataFrame()

    async def fetch_product_info(self, asin: str, marketplace: str = "US") -> dict:
        if not self._page:
            await self._init_browser()
            if not await self.login():
                raise RuntimeError("Login failed")
        url = f"https://www.sellersprite.com/v2/product-view/{marketplace}/{asin}"
        await self._page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(10)
        info = await self._page.evaluate("""
            () => {
                const getText = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? el.innerText.trim() : '';
                };
                return {
                    title: getText('h1, .product-title, [class*="title"]'),
                    price: getText('[class*="price"]'),
                    bsr: getText('[class*="bsr"], [class*="rank"]'),
                    rating: getText('[class*="rating"], [class*="star"]'),
                    reviews: getText('[class*="review"]'),
                };
            }
        """)
        info["asin"] = asin
        return info

    async def close(self):
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_playwright") and self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._context = None
        self._page = None
