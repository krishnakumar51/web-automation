# app/automation.py
"""
Playwright automation for Outlook signup (desktop).
- Always launches Edge visibly with persistent profile (maximized window).
- Falls back to Playwright bundled Chromium if Edge fails.
- Detects CAPTCHA / anti-bot pages and saves screenshots for human-in-loop.
"""

import time, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
from .logger import JobLogger

# Hosts & keywords to detect Microsoft bot protection
PROTECTION_HOSTS = ["hsprotect", "perimeterx", "arkoselabs", "crcldu", "fpt.live.com"]
CAPTCHA_KEYWORDS = ["help us", "captcha", "prove you're not", "press and hold"]


def _contains_captcha_text(text: str) -> bool:
    """Check if HTML/text contains common captcha phrases."""
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in CAPTCHA_KEYWORDS)


def _is_protection_page(page) -> bool:
    """Check if current page/frame URLs belong to known bot-protection hosts."""
    try:
        urls = [page.url.lower()] + [fr.url.lower() for fr in page.frames if fr.url]
        return any(any(host in u for host in PROTECTION_HOSTS) for u in urls)
    except Exception:
        return False


def _safe_screenshot(page):
    """Capture screenshot bytes safely."""
    try:
        return page.screenshot()
    except Exception:
        return None


def run_signup(job_id: str, email: str, password: str, logger: JobLogger, headless: bool = False):
    """
    Automates Outlook signup.
    Returns dict with keys: status, screenshot, error
    status ∈ { completed, waiting_for_human, failed, error }
    """
    logger.log("start", True, "Launching Playwright automation")
    user_data_dir = Path(logger.path).parent / f"{job_id}_profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    def _try_channel(channel_name=None):
        """Try launching with specific channel (e.g., msedge) or bundled Chromium."""
        try:
            with sync_playwright() as p:
                ctx_kwargs = {
                    "user_data_dir": str(user_data_dir),
                    "headless": False,  # always show browser
                    "args": ["--start-maximized"],
                }
                if channel_name:
                    ctx_kwargs["channel"] = channel_name

                ctx = p.chromium.launch_persistent_context(**ctx_kwargs)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.set_default_timeout(60000)

                # Navigate to signup
                logger.log("goto", True, "Navigating to signup.live.com")
                page.goto("https://signup.live.com", wait_until="networkidle")
                time.sleep(1.0)

                # Protection check
                if _is_protection_page(page):
                    logger.log("protection", False, f"Protection detected url={page.url}")
                    shot = _safe_screenshot(page)
                    if shot:
                        logger.save_screenshot(shot, name_suffix="protection.png")
                    return {"status": "waiting_for_human", "screenshot": shot, "error": None}

                # Step 1: alias input
                if page.is_visible('input[name="MemberName"]'):
                    page.fill('input[name="MemberName"]', email.split("@")[0])
                    logger.log("fill_alias", True, f"Filled alias {email}")
                    try:
                        page.click('input[type="submit"]')
                    except Exception:
                        pass
                    page.wait_for_load_state("networkidle")

                # Step 2: password input
                if page.is_visible('input[name="Password"]'):
                    page.fill('input[name="Password"]', password)
                    logger.log("fill_password", True, "Filled password")
                    try:
                        page.click('input[type="submit"]')
                    except Exception:
                        pass
                    page.wait_for_load_state("networkidle")

                # Analyze page content
                page_text = ""
                try:
                    page_text = page.content()
                except Exception as e:
                    logger.log("page_content_exc", False, f"{e}")

                # CAPTCHA / protection detection
                if _contains_captcha_text(page_text) or _is_protection_page(page):
                    logger.log("captcha_or_protection", False, "Detected captcha/protection")
                    shot = _safe_screenshot(page)
                    if shot:
                        logger.save_screenshot(shot, name_suffix="captcha.png")
                    return {"status": "waiting_for_human", "screenshot": shot, "error": None}

                # Success detection
                if "welcome" in (page_text or "").lower():
                    logger.log("completed", True, "Signup completed")
                    shot = _safe_screenshot(page)
                    return {"status": "completed", "screenshot": shot, "error": None}

                # Unknown state
                shot = _safe_screenshot(page)
                logger.log("unknown_state", False, f"Unknown state url={page.url}")
                return {"status": "waiting_for_human", "screenshot": shot, "error": None}

        except Exception as e:
            tb = traceback.format_exc()
            logger.log("channel_exception", False, f"Channel={channel_name} exception: {e}", extra={"traceback": tb})
            return {"status": "error", "screenshot": None, "error": str(e), "traceback": tb}

    # Try Edge first
    res = _try_channel("msedge")
    if res["status"] != "error":
        return res

    # Fallback to Chromium
    logger.log("fallback", True, "Falling back to bundled Chromium")
    res2 = _try_channel(None)
    if res2["status"] != "error":
        return res2

    # Both failed
    logger.log("fatal_error", False, "Both Edge and Chromium failed")
    return {"status": "failed", "screenshot": None, "error": "Playwright could not launch any browser"}
