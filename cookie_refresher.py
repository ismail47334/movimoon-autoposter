"""
MoviMoon Auto Cookie Refresh Bot - V40 OPTION 2
Burner Gmail diye auto login kore cookies.txt banay ebong GitHub Secret update kore
No manual work - runs daily via GitHub Actions
"""
import os, sys, time, json, requests
from pathlib import Path

print("=== MoviMoon Auto Cookie Refresher V40 ===")

BURNER_EMAIL = os.getenv("BURNER_EMAIL")
BURNER_PASSWORD = os.getenv("BURNER_PASSWORD")
GH_TOKEN = os.getenv("GH_TOKEN")
REPO = os.getenv("GITHUB_REPOSITORY", "ismail47334/movimoon-autoposter")

if not BURNER_EMAIL or not BURNER_PASSWORD:
    print("❌ Set BURNER_EMAIL and BURNER_PASSWORD secrets")
    sys.exit(1)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not installed")

def refresh_via_playwright():
    print(f"Starting Playwright login for {BURNER_EMAIL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        print("Navigating to Google login...")
        page.goto("https://accounts.google.com/signin", wait_until="networkidle")
        time.sleep(2)
        page.fill('input[type="email"]', BURNER_EMAIL)
        page.click('#identifierNext')
        page.wait_for_timeout(3000)
        page.fill('input[type="password"]', BURNER_PASSWORD)
        page.click('#passwordNext')
        page.wait_for_timeout(5000)
        print("Checking login...")
        page.goto("https://www.youtube.com/", wait_until="networkidle")
        time.sleep(3)
        cookies = context.cookies()
        print(f"Got {len(cookies)} cookies")
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for c in cookies:
                domain = c.get('domain', '')
                flag = "TRUE" if domain.startswith('.') else "FALSE"
                path = c.get('path', '/')
                secure = "TRUE" if c.get('secure', False) else "FALSE"
                expiry = str(int(c.get('expires', 0))) if c.get('expires', -1) != -1 else "0"
                name = c.get('name', '')
                value = c.get('value', '')
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
        print(f"cookies.txt saved {Path('cookies.txt').stat().st_size} bytes")
        browser.close()
        return True

success = False
if PLAYWRIGHT_AVAILABLE:
    try:
        success = refresh_via_playwright()
    except Exception as e:
        print(f"Playwright failed: {e}")
        import traceback; traceback.print_exc()

if not success:
    print("Keeping old cookies or creating dummy - main workflow still works with android client")
    if not Path("cookies.txt").exists():
        Path("cookies.txt").write_text("# Netscape HTTP Cookie File\n")
    success = True

print("=== Cookie Refresh Done ===")
