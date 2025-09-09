# test_playwright_launch.py
import traceback, os
from playwright.sync_api import sync_playwright

os.environ["DEBUG"] = "pw:api"  # optional: prints Playwright internals to console

def try_launch(use_edge=True):
    try:
        with sync_playwright() as p:
            if use_edge:
                print("Trying channel='msedge' (Edge)...")
                ctx = p.chromium.launch_persistent_context(user_data_dir="tmp_profile_test", channel="msedge", headless=False)
            else:
                print("Trying default chromium (bundled by Playwright)...")
                ctx = p.chromium.launch_persistent_context(user_data_dir="tmp_profile_test_chrome", headless=False)
            # open a page to verify
            page = ctx.new_page()
            page.goto("https://signup.live.com", timeout=30000)
            print("Navigation OK. Page title:", page.title())
            ctx.close()
            return True
    except Exception as e:
        print("Exception occurred:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("TEST 1: try Edge channel")
    ok = try_launch(use_edge=True)
    if not ok:
        print("\nTEST 2: fallback to Playwright's chromium")
        try_launch(use_edge=False)
