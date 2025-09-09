# app/automation.py
"""
Playwright automation for Outlook signup (desktop).
- Always launches Edge visibly with persistent profile (maximized window).
- Falls back to Playwright bundled Chromium if Edge fails.
- Detects CAPTCHA / anti-bot pages and saves screenshots for human-in-loop.
- IMPROVED: Detailed logging, updated selectors, slow visible interactions
"""

import time, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from .logger import JobLogger

# Hosts & keywords to detect Microsoft bot protection
PROTECTION_HOSTS = ["hsprotect", "perimeterx", "arkoselabs", "crcldu", "fpt.live.com"]
CAPTCHA_KEYWORDS = ["help us", "captcha", "prove you're not", "press and hold", "verify", "puzzle", "challenge", "security check"]

# Global browser context for keeping browser alive
_active_contexts = {}

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

def _safe_screenshot(page, logger: JobLogger, name_suffix="screenshot"):
    """Capture screenshot bytes safely with logging."""
    try:
        screenshot = page.screenshot()
        logger.log("screenshot_taken", True, f"Screenshot captured ({len(screenshot)} bytes)")
        return screenshot
    except Exception as e:
        logger.log("screenshot_failed", False, f"Screenshot failed: {e}")
        return None

def _debug_page_elements(page, logger: JobLogger):
    """Log all input fields and buttons found on the page for debugging."""
    try:
        # Find all input elements
        inputs = page.query_selector_all("input")
        logger.log("debug_inputs", True, f"Found {len(inputs)} input elements")
        
        for i, inp in enumerate(inputs):
            try:
                tag_name = inp.evaluate("el => el.tagName")
                input_type = inp.evaluate("el => el.type") 
                input_name = inp.evaluate("el => el.name")
                input_id = inp.evaluate("el => el.id")
                input_placeholder = inp.evaluate("el => el.placeholder")
                is_visible = inp.is_visible()
                
                logger.log("debug_input_detail", True, 
                    f"Input {i}: type={input_type}, name={input_name}, id={input_id}, "
                    f"placeholder={input_placeholder}, visible={is_visible}")
            except Exception as e:
                logger.log("debug_input_error", False, f"Error analyzing input {i}: {e}")
        
        # Find all buttons
        buttons = page.query_selector_all("button, input[type='submit'], input[type='button']")
        logger.log("debug_buttons", True, f"Found {len(buttons)} button elements")
        
        for i, btn in enumerate(buttons):
            try:
                tag_name = btn.evaluate("el => el.tagName")
                btn_type = btn.evaluate("el => el.type")
                btn_text = btn.evaluate("el => el.textContent")
                btn_value = btn.evaluate("el => el.value") 
                btn_id = btn.evaluate("el => el.id")
                is_visible = btn.is_visible()
                
                logger.log("debug_button_detail", True,
                    f"Button {i}: tag={tag_name}, type={btn_type}, text='{btn_text}', "
                    f"value='{btn_value}', id={btn_id}, visible={is_visible}")
            except Exception as e:
                logger.log("debug_button_error", False, f"Error analyzing button {i}: {e}")
                
    except Exception as e:
        logger.log("debug_elements_failed", False, f"Failed to debug page elements: {e}")

def _slow_type(page, selector: str, text: str, logger: JobLogger, delay_per_char=0.15):
    """Type text slowly and visibly with highlighting."""
    try:
        logger.log("typing_start", True, f"Starting to type '{text}' in selector: {selector}")
        
        # Wait for element to be available
        page.wait_for_selector(selector, timeout=10000)
        logger.log("typing_selector_found", True, f"Selector {selector} found and ready")
        
        # Focus and highlight the field
        page.focus(selector)
        logger.log("typing_focused", True, f"Focused field: {selector}")
        
        # Add visual highlight using JavaScript
        page.evaluate(f"""
            const el = document.querySelector('{selector}');
            if (el) {{
                el.style.border = '3px solid #00ff00';
                el.style.backgroundColor = '#ffffcc';
                el.style.boxShadow = '0 0 10px #00ff00';
            }}
        """)
        logger.log("typing_highlighted", True, f"Added visual highlight to {selector}")
        
        time.sleep(1.0)  # Let user see the highlight
        
        # Clear field first
        page.fill(selector, "")
        logger.log("typing_cleared", True, f"Cleared field {selector}")
        time.sleep(0.5)
        
        # Type character by character
        for i, char in enumerate(text):
            page.type(selector, char, delay=delay_per_char * 1000)  # Playwright expects ms
            if (i + 1) % 3 == 0:  # Log every 3 characters to avoid spam
                logger.log("typing_progress", True, f"Typed {i+1}/{len(text)} characters")
        
        logger.log("typing_complete", True, f"Finished typing all {len(text)} characters")
        
        # Remove highlight after typing
        page.evaluate(f"""
            const el = document.querySelector('{selector}');
            if (el) {{
                el.style.border = '';
                el.style.backgroundColor = '';
                el.style.boxShadow = '';
            }}
        """)
        logger.log("typing_unhighlighted", True, f"Removed highlight from {selector}")
        
        time.sleep(1.0)  # Pause after typing
        return True
        
    except Exception as e:
        logger.log("typing_error", False, f"Failed to type in {selector}: {e}")
        return False

def _slow_click(page, selector: str, logger: JobLogger, highlight_duration=2.0):
    """Click element with visual feedback."""
    try:
        logger.log("clicking_start", True, f"Preparing to click: {selector}")
        
        # Wait for element to be available
        page.wait_for_selector(selector, timeout=10000)
        logger.log("clicking_selector_found", True, f"Selector {selector} found and ready")
        
        # Highlight the button/element before clicking
        page.evaluate(f"""
            const el = document.querySelector('{selector}');
            if (el) {{
                el.style.outline = '4px solid #ff0000';
                el.style.outlineOffset = '2px';
                el.style.backgroundColor = '#ffcccc';
            }}
        """)
        logger.log("clicking_highlighted", True, f"Added visual highlight to {selector}")
        
        time.sleep(highlight_duration)
        
        page.click(selector)
        logger.log("clicking_clicked", True, f"Successfully clicked: {selector}")
        
        # Remove highlight
        page.evaluate(f"""
            const el = document.querySelector('{selector}');
            if (el) {{
                el.style.outline = '';
                el.style.outlineOffset = '';
                el.style.backgroundColor = '';
            }}
        """)
        logger.log("clicking_unhighlighted", True, f"Removed highlight from {selector}")
        
        time.sleep(1.0)  # Wait after click
        return True
        
    except Exception as e:
        logger.log("clicking_error", False, f"Failed to click {selector}: {e}")
        return False

def _wait_and_log(page, logger: JobLogger, seconds=3.0, reason="General wait"):
    """Wait with logging."""
    logger.log("waiting", True, f"Waiting {seconds}s - {reason}")
    time.sleep(seconds)
    logger.log("wait_complete", True, f"Wait completed - {reason}")

def cleanup_context(job_id: str):
    """Clean up browser context for a job."""
    global _active_contexts
    if job_id in _active_contexts:
        try:
            ctx = _active_contexts[job_id]
            ctx.close()
            del _active_contexts[job_id]
        except Exception:
            pass

def run_signup(job_id: str, email: str, password: str, logger: JobLogger, headless: bool = False):
    """
    Automates Outlook signup with visible interactions and detailed logging.
    Returns dict with keys: status, screenshot, error
    status ∈ { completed, waiting_for_human, failed, error }
    """
    global _active_contexts
    
    logger.log("automation_start", True, f"Starting Outlook signup automation for {email}")
    user_data_dir = Path(logger.path).parent / f"{job_id}_profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    logger.log("profile_dir_created", True, f"Profile directory: {user_data_dir}")

    def _try_channel(channel_name=None):
        """Try launching with specific channel (e.g., msedge) or bundled Chromium."""
        try:
            logger.log("browser_launch_start", True, f"Attempting to launch browser with channel: {channel_name}")
            
            with sync_playwright() as p:
                ctx_kwargs = {
                    "user_data_dir": str(user_data_dir),
                    "headless": False,  # always show browser
                    "args": [
                        "--start-maximized",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor"
                    ],
                }
                if channel_name:
                    ctx_kwargs["channel"] = channel_name

                ctx = p.chromium.launch_persistent_context(**ctx_kwargs)
                logger.log("browser_launched", True, f"Browser launched successfully with channel: {channel_name}")
                
                # Store context globally so it doesn't close during CAPTCHA
                _active_contexts[job_id] = ctx
                logger.log("context_stored", True, f"Browser context stored for job: {job_id}")
                
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.set_default_timeout(60000)
                logger.log("page_ready", True, "Page created and timeout set to 60s")
                
                # Add user agent to look more human
                page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
                })
                logger.log("user_agent_set", True, "User agent configured")

                # Navigate to signup with visible progress
                logger.log("navigation_start", True, "Navigating to https://signup.live.com")
                page.goto("https://signup.live.com", wait_until="networkidle")
                
                # Log page info after navigation
                current_url = page.url
                page_title = page.title()
                logger.log("navigation_complete", True, f"Navigation complete. URL: {current_url}, Title: {page_title}")
                
                _wait_and_log(page, logger, 3.0, "Let page fully load")
                
                # Debug: Log all elements on the page
                _debug_page_elements(page, logger)

                # Protection check
                if _is_protection_page(page):
                    logger.log("protection_detected", False, f"Bot protection detected on URL: {current_url}")
                    shot = _safe_screenshot(page, logger, "protection")
                    if shot:
                        logger.save_screenshot(shot, name_suffix="protection.png")
                    return {"status": "waiting_for_human", "screenshot": shot, "error": None}

                # UPDATED SELECTORS FOR CURRENT MICROSOFT SIGNUP PAGE
                # Step 1: Look for email input field (the page shows "Enter your email address")
                email_selectors = [
                    'input[name="loginfmt"]',          # Most common
                    'input[type="email"]',             # Generic email input
                    'input[placeholder*="email"]',     # Placeholder contains "email"
                    'input[aria-label*="email"]',      # ARIA label contains "email"
                    '#i0116',                          # Microsoft's common email input ID
                    'input[name="Email"]',             # Alternative name
                    'input[id*="Email"]',              # ID contains "Email"
                ]
                
                email_filled = False
                logger.log("email_search_start", True, f"Searching for email input field with {len(email_selectors)} selectors")
                
                for i, selector in enumerate(email_selectors):
                    try:
                        logger.log("email_selector_try", True, f"Trying email selector {i+1}/{len(email_selectors)}: {selector}")
                        
                        if page.is_visible(selector, timeout=3000):
                            logger.log("email_field_found", True, f"✅ Email field found with selector: {selector}")
                            
                            # Type the full email address (not just alias)
                            if _slow_type(page, selector, email, logger, delay_per_char=0.2):
                                email_filled = True
                                logger.log("email_filled_success", True, f"Successfully filled email: {email}")
                                
                                _wait_and_log(page, logger, 2.0, "After email input")
                                
                                # Look for Next/Continue button
                                next_selectors = [
                                    'input[type="submit"]',
                                    'button[type="submit"]', 
                                    'input[value="Next"]',
                                    'button:has-text("Next")',
                                    '#idSIButton9',              # Microsoft's common Next button ID
                                    'input[id="idSIButton9"]',
                                    '.btn-primary',
                                    '[data-report-event="Signin_Submit"]'
                                ]
                                
                                next_clicked = False
                                logger.log("next_button_search", True, f"Searching for Next button with {len(next_selectors)} selectors")
                                
                                for j, next_sel in enumerate(next_selectors):
                                    try:
                                        logger.log("next_selector_try", True, f"Trying Next selector {j+1}/{len(next_selectors)}: {next_sel}")
                                        if page.is_visible(next_sel, timeout=2000):
                                            logger.log("next_button_found", True, f"✅ Next button found: {next_sel}")
                                            if _slow_click(page, next_sel, logger, highlight_duration=2.0):
                                                next_clicked = True
                                                break
                                    except Exception as e:
                                        logger.log("next_selector_error", False, f"Next selector {next_sel} failed: {e}")
                                
                                if next_clicked:
                                    logger.log("next_clicked_success", True, "Successfully clicked Next button")
                                    page.wait_for_load_state("networkidle", timeout=30000)
                                    _wait_and_log(page, logger, 3.0, "After clicking Next")
                                else:
                                    logger.log("next_click_failed", False, "Could not find or click Next button")
                                
                                break
                    except Exception as e:
                        logger.log("email_selector_error", False, f"Email selector {selector} failed: {e}")
                        continue

                if not email_filled:
                    logger.log("email_fill_failed", False, "❌ Could not find or fill any email input field")
                    # Take screenshot for debugging
                    shot = _safe_screenshot(page, logger, "no_email_field")
                    if shot:
                        logger.save_screenshot(shot, name_suffix="no_email_field.png")

                # Step 2: Look for password field (might be on next page)
                _wait_and_log(page, logger, 2.0, "Before password field search")
                
                password_selectors = [
                    'input[name="passwd"]',            # Microsoft's common password field
                    'input[name="Password"]',          # Alternative
                    'input[type="password"]',          # Generic password input
                    '#i0118',                          # Microsoft's common password input ID  
                    'input[placeholder*="password"]',   # Placeholder contains "password"
                    'input[aria-label*="password"]',   # ARIA label contains "password"
                ]
                
                password_filled = False
                logger.log("password_search_start", True, f"Searching for password field with {len(password_selectors)} selectors")
                
                for i, selector in enumerate(password_selectors):
                    try:
                        logger.log("password_selector_try", True, f"Trying password selector {i+1}/{len(password_selectors)}: {selector}")
                        
                        if page.is_visible(selector, timeout=5000):
                            logger.log("password_field_found", True, f"✅ Password field found with selector: {selector}")
                            
                            if _slow_type(page, selector, password, logger, delay_per_char=0.15):
                                password_filled = True
                                logger.log("password_filled_success", True, "Successfully filled password")
                                
                                _wait_and_log(page, logger, 2.0, "After password input")
                                
                                # Look for submit/create account button
                                submit_selectors = [
                                    'input[type="submit"]',
                                    'button[type="submit"]',
                                    'input[value="Next"]',
                                    'input[value="Create account"]',
                                    'button:has-text("Create account")',
                                    'button:has-text("Next")',
                                    '#idSIButton9',
                                    'input[id="idSIButton9"]',
                                ]
                                
                                submit_clicked = False
                                logger.log("submit_button_search", True, f"Searching for submit button with {len(submit_selectors)} selectors")
                                
                                for j, submit_sel in enumerate(submit_selectors):
                                    try:
                                        logger.log("submit_selector_try", True, f"Trying submit selector {j+1}/{len(submit_selectors)}: {submit_sel}")
                                        if page.is_visible(submit_sel, timeout=3000):
                                            logger.log("submit_button_found", True, f"✅ Submit button found: {submit_sel}")
                                            if _slow_click(page, submit_sel, logger, highlight_duration=2.5):
                                                submit_clicked = True
                                                break
                                    except Exception as e:
                                        logger.log("submit_selector_error", False, f"Submit selector {submit_sel} failed: {e}")
                                
                                if submit_clicked:
                                    logger.log("submit_clicked_success", True, "Successfully clicked Submit button")
                                    page.wait_for_load_state("networkidle", timeout=30000)
                                    _wait_and_log(page, logger, 4.0, "After clicking Submit")
                                else:
                                    logger.log("submit_click_failed", False, "Could not find or click Submit button")
                                
                                break
                    except Exception as e:
                        logger.log("password_selector_error", False, f"Password selector {selector} failed: {e}")
                        continue

                if not password_filled:
                    logger.log("password_fill_failed", False, "❌ Could not find or fill password field")
                    
                # Log final URL after all interactions
                final_url = page.url
                final_title = page.title()
                logger.log("final_page_info", True, f"Final URL: {final_url}, Final Title: {final_title}")

                # Analyze current page state
                page_text = ""
                try:
                    page_text = page.content()
                    logger.log("page_content_retrieved", True, f"Retrieved page content ({len(page_text)} characters)")
                except Exception as e:
                    logger.log("page_content_failed", False, f"Failed to get page content: {e}")

                # CAPTCHA / protection detection
                if _contains_captcha_text(page_text) or _is_protection_page(page):
                    logger.log("captcha_detected", False, "🧩 CAPTCHA/protection detected - keeping browser open")
                    
                    # Add visual indicator for user
                    try:
                        page.evaluate("""
                            const banner = document.createElement('div');
                            banner.style.cssText = `
                                position: fixed; top: 0; left: 0; right: 0; 
                                background: #ff6b6b; color: white; padding: 15px; 
                                text-align: center; font-size: 16px; font-weight: bold;
                                z-index: 10000; box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                            `;
                            banner.textContent = '🤖 CAPTCHA DETECTED - Please solve it manually, then click RESUME in the web interface';
                            document.body.prepend(banner);
                        """)
                        logger.log("captcha_banner_added", True, "Added CAPTCHA instruction banner to page")
                    except Exception:
                        logger.log("captcha_banner_failed", False, "Failed to add CAPTCHA banner")
                    
                    shot = _safe_screenshot(page, logger, "captcha")
                    if shot:
                        logger.save_screenshot(shot, name_suffix="captcha.png")
                    
                    return {"status": "waiting_for_human", "screenshot": shot, "error": None}

                # Success detection - look for welcome or success indicators
                success_indicators = ["welcome", "congratulations", "account created", "success", "inbox", "outlook"]
                page_text_lower = (page_text or "").lower()
                final_url_lower = final_url.lower()
                
                is_success = any(indicator in page_text_lower for indicator in success_indicators) or \
                           any(indicator in final_url_lower for indicator in ["outlook", "live.com/mail"])
                
                if is_success:
                    logger.log("success_detected", True, "🎉 SUCCESS - Account creation completed!")
                    
                    # Add success banner
                    try:
                        page.evaluate("""
                            const banner = document.createElement('div');
                            banner.style.cssText = `
                                position: fixed; top: 0; left: 0; right: 0; 
                                background: #51cf66; color: white; padding: 15px; 
                                text-align: center; font-size: 16px; font-weight: bold;
                                z-index: 10000; box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                            `;
                            banner.textContent = '✅ SUCCESS - Account created successfully!';
                            document.body.prepend(banner);
                        """)
                        logger.log("success_banner_added", True, "Added success banner to page")
                    except Exception:
                        logger.log("success_banner_failed", False, "Failed to add success banner")
                        
                    shot = _safe_screenshot(page, logger, "success")
                    _wait_and_log(page, logger, 5.0, "Let user see success message")
                    
                    # Now we can close the browser
                    cleanup_context(job_id)
                    return {"status": "completed", "screenshot": shot, "error": None}

                # Unknown state - keep browser open for inspection
                logger.log("unknown_state", False, f"⚠️ Unknown state - keeping browser open. URL: {final_url}")
                
                # Debug: Take screenshot and log page content snippet
                shot = _safe_screenshot(page, logger, "unknown_state")
                if shot:
                    logger.save_screenshot(shot, name_suffix="unknown_state.png")
                
                # Log a snippet of page content for debugging
                if page_text:
                    snippet = page_text[:500] + "..." if len(page_text) > 500 else page_text
                    logger.log("page_content_snippet", True, f"Page content snippet: {snippet}")
                
                # Add inspection banner
                try:
                    page.evaluate("""
                        const banner = document.createElement('div');
                        banner.style.cssText = `
                            position: fixed; top: 0; left: 0; right: 0; 
                            background: #ffd43b; color: #000; padding: 15px; 
                            text-align: center; font-size: 16px; font-weight: bold;
                            z-index: 10000; box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                        `;
                        banner.textContent = '⚠️ UNKNOWN STATE - Please check manually and click RESUME if needed';
                        document.body.prepend(banner);
                    """)
                    logger.log("unknown_banner_added", True, "Added unknown state banner to page")
                except Exception:
                    logger.log("unknown_banner_failed", False, "Failed to add unknown state banner")
                
                return {"status": "waiting_for_human", "screenshot": shot, "error": None}

        except Exception as e:
            tb = traceback.format_exc()
            logger.log("channel_exception", False, f"Browser channel {channel_name} failed with exception: {e}")
            logger.log("channel_traceback", False, f"Full traceback: {tb}")
            cleanup_context(job_id)
            return {"status": "error", "screenshot": None, "error": str(e), "traceback": tb}

    # Try Edge first
    logger.log("edge_attempt", True, "🌐 Attempting to launch Microsoft Edge...")
    res = _try_channel("msedge")
    if res["status"] != "error":
        return res

    # Fallback to Chromium
    logger.log("chromium_fallback", True, "🌐 Edge failed, falling back to bundled Chromium...")
    res2 = _try_channel(None)
    if res2["status"] != "error":
        return res2

    # Both failed
    logger.log("browser_launch_failed", False, "❌ Both Edge and Chromium failed to launch")
    return {"status": "failed", "screenshot": None, "error": "Could not launch any browser"}

def resume_signup(job_id: str, logger: JobLogger):
    """
    Resume a signup process that was waiting for human intervention.
    Uses the existing browser context if available.
    """
    global _active_contexts
    
    logger.log("resume_start", True, f"🔄 Attempting to resume job: {job_id}")
    
    if job_id not in _active_contexts:
        logger.log("resume_no_context", False, "❌ No active browser context found for resume")
        return {"status": "error", "screenshot": None, "error": "Browser context not found"}
    
    try:
        ctx = _active_contexts[job_id]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        logger.log("resume_context_found", True, "✅ Found existing browser context")
        
        # Remove any existing banners
        try:
            page.evaluate("""
                const banners = document.querySelectorAll('[style*="position: fixed"][style*="top: 0"]');
                banners.forEach(b => b.remove());
            """)
            logger.log("resume_banners_removed", True, "Removed existing banners")
        except Exception:
            logger.log("resume_banners_failed", False, "Failed to remove banners")
        
        _wait_and_log(page, logger, 2.0, "After resume cleanup")
        
        # Get current page info
        current_url = page.url
        current_title = page.title()
        logger.log("resume_current_page", True, f"Current page - URL: {current_url}, Title: {current_title}")
        
        # Re-analyze current page state
        page_text = ""
        try:
            page_text = page.content()
            logger.log("resume_page_content", True, f"Retrieved current page content ({len(page_text)} characters)")
        except Exception as e:
            logger.log("resume_content_failed", False, f"Failed to get page content: {e}")
        
        # Check if CAPTCHA is still present
        if _contains_captcha_text(page_text) or _is_protection_page(page):
            logger.log("resume_still_captcha", False, "🧩 CAPTCHA still present after resume")
            shot = _safe_screenshot(page, logger, "resume_captcha")
            return {"status": "waiting_for_human", "screenshot": shot, "error": "CAPTCHA still present"}
        
        # Check for success
        success_indicators = ["welcome", "congratulations", "account created", "success", "inbox", "outlook"]
        page_text_lower = (page_text or "").lower()
        current_url_lower = current_url.lower()
        
        is_success = any(indicator in page_text_lower for indicator in success_indicators) or \
                   any(indicator in current_url_lower for indicator in ["outlook", "live.com/mail"])
        
        if is_success:
            logger.log("resume_success", True, "🎉 Account creation completed after resume!")
            shot = _safe_screenshot(page, logger, "resume_success")
            cleanup_context(job_id)
            return {"status": "completed", "screenshot": shot, "error": None}
        
        # Still unknown state
        logger.log("resume_still_unknown", False, "⚠️ Still in unknown state after resume")
        shot = _safe_screenshot(page, logger, "resume_unknown")
        return {"status": "waiting_for_human", "screenshot": shot, "error": "Still in unknown state"}
        
    except Exception as e:
        logger.log("resume_exception", False, f"❌ Resume failed with exception: {e}")
        cleanup_context(job_id)
        return {"status": "error", "screenshot": None, "error": str(e)}