import asyncio
import json
import csv
import os
import sys
import base64
import requests as req_lib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

PHONE = os.environ.get("SS_PHONE", "")
PASSWORD = os.environ.get("SS_PASSWORD", "")
TT_USER = os.environ.get("TT_USER", "")
TT_PASS = os.environ.get("TT_PASS", "")
TT_API = "http://api.ttshitu.com"
REPORT_DIR = os.path.dirname(os.path.abspath(__file__))


def aes_encrypt(text, key):
    cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)
    return base64.b64encode(cipher.encrypt(pad(text.encode('utf-8'), AES.block_size))).decode('utf-8')


def solve_tt(bg_b64, jigsaw_b64=None):
    data = {"username": TT_USER, "password": TT_PASS,
            "typeid": "18" if jigsaw_b64 else "33",
            "image": jigsaw_b64 or bg_b64}
    if jigsaw_b64:
        data["imageback"] = bg_b64
    resp = req_lib.post(f"{TT_API}/predict", json=data, timeout=60)
    r = resp.json()
    return r["data"] if r.get("success") else {"error": r.get("message")}


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080}, locale="zh-CN",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        page = await context.new_page()
        s = Stealth()
        await s.apply_stealth_async(page)

        # LOGIN
        print("[1] Login...")
        await page.goto("https://www.sellersprite.com/cn/w/user/login", timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(5)
        for inp in await page.query_selector_all('input[name="email"]'):
            if await inp.is_visible():
                await inp.click(force=True); await inp.fill(PHONE); break
        for inp in await page.query_selector_all('input[type="password"]'):
            if await inp.is_visible():
                await inp.click(force=True); await inp.fill(PASSWORD); break
        for btn in await page.query_selector_all('button[type="submit"]'):
            if await btn.is_visible() and "登录" in await btn.inner_text():
                await btn.click(force=True); break
        await asyncio.sleep(10)
        if "login" in page.url:
            print("  FAIL"); await browser.close(); return
        print("  OK")

        # Test with example ASINs first
        test_asins = ["B07PCNGJP8", "B07XFBN7HX", "B07Z82895W"]
        
        for asin in test_asins:
            print(f"\n{'='*60}")
            print(f"[TEST] ASIN: {asin}")
            
            captcha_data_list = []
            async def cap_handler(response):
                if "/captcha/get" in response.url:
                    try:
                        d = await response.json()
                        if d.get("repData", {}).get("originalImageBase64"):
                            captcha_data_list.append(d["repData"])
                    except:
                        pass

            page.on("response", cap_handler)
            
            url = f"https://www.sellersprite.com/v2/keyword-reverse/US/{asin}?v=false&q="
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(15)

            # Solve captcha if present
            if captcha_data_list:
                print(f"  Captcha found! Solving...")
                rep = captcha_data_list[-1]
                bg = rep.get("originalImageBase64", "")
                jig = rep.get("jigsawImageBase64", "")
                sk = rep.get("secretKey", "")
                token = rep.get("token", "")

                solve = solve_tt(bg, jig if jig else None)
                print(f"  TT: {solve}")

                if not solve.get("error"):
                    ans = str(solve["result"])
                    x = int(ans.split(",")[0]) if "," in ans else int(ans)
                    enc = aes_encrypt(json.dumps({"x": x, "y": 5}), sk)

                    check = await page.evaluate(f"""
                        async () => {{
                            const r = await fetch('/captcha/check', {{
                                method: 'POST', credentials: 'include',
                                headers: {{'Content-Type': 'application/json'}},
                                body: JSON.stringify({{captchaType: 'blockPuzzle', pointJson: '{enc}', token: '{token}'}})
                            }});
                            return await r.text();
                        }}
                    """)
                    print(f"  Captcha check: {check[:200]}")

                    await asyncio.sleep(3)
                    await page.reload(timeout=60000, wait_until="domcontentloaded")
                    await asyncio.sleep(15)

            # Check page content
            page_info = await page.evaluate("""
                () => {
                    let rows = 0;
                    let texts = [];
                    document.querySelectorAll('table tr').forEach((tr, i) => {
                        const t = tr.innerText.trim();
                        if (i > 0 && t && !t.includes('加载中')) {
                            rows++;
                            if (texts.length < 3) texts.push(t);
                        }
                    });
                    const body = document.body.innerText;
                    let status = 'unknown';
                    if (body.includes('未能找到')) status = 'NOT_FOUND';
                    else if (body.includes('加载中')) status = 'LOADING';
                    else if (rows > 0) status = 'HAS_DATA';
                    
                    return {rows, status, texts, bodySnippet: body.substring(0, 300)};
                }
            """)

            print(f"  Status: {page_info['status']}")
            print(f"  Rows: {page_info['rows']}")
            
            if page_info['status'] == 'HAS_DATA':
                print(f"  Sample rows:")
                for t in page_info['texts']:
                    print(f"    {t[:150]}")
                
                # Extract full table data
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
                
                if tables_data:
                    header = tables_data[0][0] if tables_data[0] else []
                    data_rows = tables_data[0][1:] if len(tables_data[0]) > 1 else []
                    print(f"  Header: {header[:8]}")
                    print(f"  Total data rows: {len(data_rows)}")
                    
                    # Save
                    report = {"asin": asin, "header": header, "data": data_rows, "total": len(data_rows)}
                    with open(os.path.join(REPORT_DIR, f"keywords_{asin}.json"), "w", encoding="utf-8") as f:
                        json.dump(report, f, ensure_ascii=False, indent=2)
                    
                    if header and data_rows:
                        with open(os.path.join(REPORT_DIR, f"keywords_{asin}.csv"), "w", encoding="utf-8-sig", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow(header)
                            for row in data_rows:
                                writer.writerow(row)
                        print(f"  Saved CSV!")
            elif page_info['status'] == 'NOT_FOUND':
                print(f"  >>> 未找到关键词 <<<")

            page.remove_listener("response", cap_handler)

        await browser.close()
        print(f"\n[DONE]")

asyncio.run(main())
