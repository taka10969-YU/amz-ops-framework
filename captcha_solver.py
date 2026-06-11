import asyncio
import base64
import json
import math
import os
import random
import time

import requests

API_URL = "http://api.ttshitu.com"

_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ttshitu_config.json")
if os.path.exists(_config_path):
    _cfg = json.loads(open(_config_path, encoding="utf-8").read())
    TTSHITU_USERNAME = _cfg.get("username", "")
    TTSHITU_PASSWORD = _cfg.get("password", "")
else:
    TTSHITU_USERNAME = os.environ.get("TTSHITU_USERNAME", "")
    TTSHITU_PASSWORD = os.environ.get("TTSHITU_PASSWORD", "")


def predict_base64(image_bytes, typeid=3, imageback_bytes=None, timeout=60, retries=3):
    b64_image = base64.b64encode(image_bytes).decode()
    data = {
        "username": TTSHITU_USERNAME,
        "password": TTSHITU_PASSWORD,
        "typeid": str(typeid),
        "image": b64_image,
    }
    if imageback_bytes is not None:
        data["imageback"] = base64.b64encode(imageback_bytes).decode()
    for attempt in range(retries):
        try:
            resp = requests.post(f"{API_URL}/predict", json=data, timeout=timeout)
            result = resp.json()
            if result.get("success"):
                return result["data"]
            msg = str(result.get("message", ""))
            if any(x in msg for x in ["人工不足", "超时", "timeout", "请延长超时时间"]):
                time.sleep(2)
                continue
            return {"error": msg}
        except requests.RequestException as exc:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            return {"error": str(exc)}
    return {"error": "重试仍失败"}


def report_error(error_id, timeout=30):
    try:
        data = {"id": error_id}
        resp = requests.post(f"{API_URL}/reporterror.json", json=data, timeout=timeout)
        result = resp.json()
        return "报错成功" if result.get("success") else result.get("message")
    except requests.RequestException:
        return "报错请求失败"


SLIDER_CAPTCHA_DETECT_SELECTORS = [
    "[class*='captcha']",
    "[class*='slider']",
    "[class*='verify']",
    "[class*='geetest']",
    "[class*='gt_']",
    "[class*='nc_']",
    "[id*='captcha']",
    "[id*='slider']",
    "[id*='verify']",
]

SLIDER_BG_SELECTORS = [
    "img[class*='captcha']",
    "img[class*='puzzle']",
    "img[class*='bg']",
    "canvas[class*='captcha']",
    ".captcha_background img",
    ".geetest_canvas_bg",
    ".geetest_canvas_img",
    "canvas.geetest_canvas_slice",
    ".geetest_widget img",
    ".geetest_item_wrap img",
    "img[src*='captcha']",
    "img[src*='puzzle']",
    ".verify-img-panel img",
    ".verify-img-panel canvas",
    "[class*='captcha'] img",
    "[class*='captcha'] canvas",
    "[class*='slider-bg']",
    "[class*='captcha_bg']",
    "[class*='captchaBg']",
]

SLIDER_PIECE_SELECTORS = [
    "img[class*='puzzle']",
    "img[class*='piece']",
    "img[class*='slice']",
    "img[class*='block']",
    ".geetest_canvas_slice",
    "canvas.geetest_canvas_slice",
    "[class*='captcha'] img[class*='slice']",
    "[class*='captcha'] img[class*='piece']",
    "[class*='captcha'] img[class*='block']",
    ".verify-img-panel img:nth-child(2)",
]

SLIDER_BUTTON_SELECTORS = [
    "[class*='slider-btn']",
    "[class*='slide-btn']",
    "[class*='drag-btn']",
    "[class*='slider_button']",
    "[class*='sliderButton']",
    ".geetest_slider_button",
    "[class*='nc_iconfont']",
    "[class*='btn_slide']",
    "[class*='handle']",
    "button[class*='slider']",
    "div[class*='slider'] span",
    "div[class*='slider'] div",
    ".verify-slide-block",
    "[class*='captcha'] [class*='btn']",
    "[class*='captcha'] [class*='handle']",
    "[class*='captcha'] [class*='slider']",
]

AMAZON_CAPTCHA_SELECTORS = [
    "#auth-captcha-image",
    "img[src*='captcha']",
    "img[src*='Captcha']",
    "img[alt*='captcha' i]",
    "img[alt*='CAPTCHA']",
]

AMAZON_CAPTCHA_INPUT_SELECTORS = [
    "#captchacharacters",
    "input[name='field-keywords'][type='text']",
    "input[name='cvf_captcha_input']",
    "input[name='captchacharacters']",
    "input[placeholder*='captcha' i]",
    "input[placeholder*='characters' i]",
]

AMAZON_CAPTCHA_SUBMIT_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    ".a-button-input[type='submit']",
    "#continue",
]


async def detect_slider_captcha(page):
    for selector in SLIDER_CAPTCHA_DETECT_SELECTORS:
        try:
            els = await page.query_selector_all(selector)
            for el in els:
                if await el.is_visible():
                    bg_el = None
                    for bg_sel in SLIDER_BG_SELECTORS:
                        try:
                            candidate = await page.query_selector(bg_sel)
                            if candidate and await candidate.is_visible():
                                bg_el = candidate
                                break
                        except Exception:
                            continue
                    if bg_el:
                        btn_el = None
                        for btn_sel in SLIDER_BUTTON_SELECTORS:
                            try:
                                candidate = await page.query_selector(btn_sel)
                                if candidate and await candidate.is_visible():
                                    btn_el = candidate
                                    break
                            except Exception:
                                continue
                        return bg_el, btn_el
        except Exception:
            continue
    return None, None


async def _get_element_image(el, page):
    img_src = await el.get_attribute("src")
    if img_src and img_src.startswith("data:"):
        _, b64_data = img_src.split(",", 1)
        return base64.b64decode(b64_data)
    if img_src and img_src.startswith("http"):
        resp = requests.get(img_src, timeout=30)
        return resp.content
    tag = await el.evaluate("el => el.tagName.toLowerCase()")
    if tag == "canvas":
        data_url = await el.evaluate("el => el.toDataURL('image/png')")
        _, b64_data = data_url.split(",", 1)
        return base64.b64decode(b64_data)
    return await el.screenshot()


async def _get_slider_width(page):
    width = await page.evaluate("""
        () => {
            const selectors = [
                '[class*="captcha"]',
                '[class*="slider"]',
                '[class*="verify"]',
            ];
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    if (el.offsetParent !== null && el.getBoundingClientRect().width > 100) {
                        return el.getBoundingClientRect().width;
                    }
                }
            }
            return 0;
        }
    """)
    return width or 280


async def _human_slide(page, btn_el, offset_x, duration_ms=800):
    box = await btn_el.bounding_box()
    if not box:
        return False
    start_x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2
    end_x = start_x + offset_x
    steps = max(10, int(duration_ms / 30))
    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    await asyncio.sleep(0.1)
    for i in range(1, steps + 1):
        progress = i / steps
        ease = 0.5 - 0.5 * math.cos(progress * math.pi)
        x = start_x + (end_x - start_x) * ease
        y = start_y + random.uniform(-2, 2)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.01, 0.04))
    await asyncio.sleep(random.uniform(0.05, 0.15))
    await page.mouse.up()
    await asyncio.sleep(1.5)
    return True


async def solve_slider_captcha(page, max_attempts=5):
    for attempt in range(max_attempts):
        bg_el, btn_el = await detect_slider_captcha(page)
        if not bg_el:
            print(f"[captcha] no slider captcha detected (attempt {attempt + 1})", flush=True)
            return False

        try:
            bg_bytes = await _get_element_image(bg_el, page)
            if not bg_bytes:
                print("[captcha] failed to get background image", flush=True)
                continue

            piece_el = None
            for piece_sel in SLIDER_PIECE_SELECTORS:
                try:
                    candidate = await page.query_selector(piece_sel)
                    if candidate and await candidate.is_visible():
                        piece_el = candidate
                        break
                except Exception:
                    continue

            piece_bytes = await _get_element_image(piece_el, page) if piece_el else None

            if piece_bytes:
                result = predict_base64(bg_bytes, typeid=27, imageback_bytes=piece_bytes)
            else:
                result = predict_base64(bg_bytes, typeid=33)

            if "error" in result:
                print(f"[captcha] recognition failed: {result['error']}", flush=True)
                continue

            captcha_id = result.get("id", "")

            if piece_bytes:
                offset_str = str(result.get("result", ""))
                try:
                    offset_x = float(offset_str)
                except ValueError:
                    print(f"[captcha] cannot parse offset: {offset_str}", flush=True)
                    continue
                slider_width = await _get_slider_width(page)
                bg_width = await bg_el.evaluate("el => el.getBoundingClientRect().width") or 280
                if bg_width > 0 and abs(offset_x) > bg_width:
                    offset_x = offset_x * slider_width / bg_width
            else:
                offset_str = str(result.get("result", ""))
                try:
                    offset_x = float(offset_str)
                except ValueError:
                    print(f"[captcha] cannot parse offset: {offset_str}", flush=True)
                    continue

            print(f"[captcha] slider offset: {offset_x:.1f}px (id={captcha_id})", flush=True)

            if not btn_el:
                print("[captcha] slider button not found", flush=True)
                return False

            slid = await _human_slide(page, btn_el, offset_x)
            if not slid:
                continue

            still_captcha, _ = await detect_slider_captcha(page)
            if not still_captcha:
                print("[captcha] slider solved successfully!", flush=True)
                return True

            print(f"[captcha] wrong offset, retrying (attempt {attempt + 1})", flush=True)
            if captcha_id:
                report_error(captcha_id)
            await asyncio.sleep(1)

        except Exception as exc:
            print(f"[captcha] exception: {exc}", flush=True)
            continue

    print(f"[captcha] slider failed after {max_attempts} attempts", flush=True)
    return False


async def detect_text_captcha(page):
    for selector in AMAZON_CAPTCHA_SELECTORS:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                input_el = None
                for inp_sel in AMAZON_CAPTCHA_INPUT_SELECTORS:
                    try:
                        candidate = await page.query_selector(inp_sel)
                        if candidate and await candidate.is_visible():
                            input_el = candidate
                            break
                    except Exception:
                        continue
                return el, input_el
        except Exception:
            continue
    return None, None


async def solve_text_captcha(page, max_attempts=3):
    for attempt in range(max_attempts):
        img_el, input_el = await detect_text_captcha(page)
        if not img_el:
            return False

        try:
            img_bytes = await _get_element_image(img_el, page)
            if not img_bytes:
                continue

            result = predict_base64(img_bytes, typeid=3)
            if "error" in result:
                print(f"[captcha] text recognition failed: {result['error']}", flush=True)
                continue

            captcha_text = str(result.get("result", "")).strip()
            captcha_id = result.get("id", "")
            if not captcha_text:
                continue

            print(f"[captcha] text recognized: '{captcha_text}' (id={captcha_id})", flush=True)

            if input_el:
                await input_el.fill("")
                await input_el.type(captcha_text, delay=50)
                submit_el = None
                for sub_sel in AMAZON_CAPTCHA_SUBMIT_SELECTORS:
                    try:
                        candidate = await page.query_selector(sub_sel)
                        if candidate and await candidate.is_visible():
                            submit_el = candidate
                            break
                    except Exception:
                        continue
                if submit_el:
                    await submit_el.click()
                else:
                    await input_el.press("Enter")
                await asyncio.sleep(3)

                still_img, _ = await detect_text_captcha(page)
                if not still_img:
                    print("[captcha] text captcha solved!", flush=True)
                    return True
                print(f"[captcha] wrong text answer (attempt {attempt + 1})", flush=True)
                if captcha_id:
                    report_error(captcha_id)
            else:
                return False
        except Exception as exc:
            print(f"[captcha] exception: {exc}", flush=True)
            continue

    return False


async def auto_solve_captcha(page, max_slider=5, max_text=3):
    slider_bg, _ = await detect_slider_captcha(page)
    if slider_bg:
        print("[captcha] slider captcha detected, auto-solving...", flush=True)
        return await solve_slider_captcha(page, max_attempts=max_slider)

    text_img, _ = await detect_text_captcha(page)
    if text_img:
        print("[captcha] text captcha detected, auto-solving...", flush=True)
        return await solve_text_captcha(page, max_attempts=max_text)

    captcha_count = await page.evaluate("""
        () => document.querySelectorAll(
            '[class*="captcha"], [class*="slider"], [class*="verify"]'
        ).length
    """)
    if captcha_count > 0:
        print(f"[captcha] {captcha_count} generic captcha elements found, waiting for specific elements...", flush=True)
        await asyncio.sleep(2)
        slider_bg, _ = await detect_slider_captcha(page)
        if slider_bg:
            return await solve_slider_captcha(page, max_attempts=max_slider)
        text_img, _ = await detect_text_captcha(page)
        if text_img:
            return await solve_text_captcha(page, max_attempts=max_text)

    return False
