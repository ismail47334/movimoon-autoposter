"""
MoviMoon Auto Cookie Refresh Bot - V40.1 FIXED
- Real Gmail password use kore (App Password na)
- Google login new UI selectors
- Anti-bot bypass + GH_TOKEN auto update
"""
import os, sys, time, base64, json, requests
from pathlib import Path

print("=== MoviMoon Auto Cookie Refresher V40.1 FIXED ===")

BURNER_EMAIL = os.getenv("BURNER_EMAIL")
BURNER_PASSWORD = os.getenv("BURNER_PASSWORD")
GH_TOKEN = os.getenv("GH_TOKEN")
REPO = os.getenv("GITHUB_REPOSITORY", "ismail47334/movimoon-autoposter")

if not BURNER_EMAIL or not BURNER_PASSWORD:
    print("❌ Set BURNER_EMAIL and BURNER_PASSWORD secrets")
    sys.exit(1)

# Burner account should be WITHOUT 2FA for bot to work
# If you have 2FA, disable it or use a dedicated no-2FA burner

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

def update_github_secret(secret_name, secret_value):
    """Auto update GitHub Actions secret via API"""
    if not GH_TOKEN:
        print("⚠️ GH_TOKEN not set - skipping auto secret update, will use artifact")
        return False
    try:
        from nacl import encoding, public
        import nacl.utils
        # Get public key
        headers = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}
        r = requests.get(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key", headers=headers)
        if r.status_code != 200:
            print(f"Failed to get public key: {r.text}")
            return False
        key_data = r.json()
        public_key = key_data["key"]
        key_id = key_data["key_id"]
        
        # Encrypt with NaCl sealed box
        public_key_obj = public.PublicKey(public_key.encode(), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")
        
        # PUT secret
        put_data = {"encrypted_value": encrypted_b64, "key_id": key_id}
        r2 = requests.put(f"https://api.github.com/repos/{REPO}/actions/secrets/{secret_name}", headers=headers, json=put_data)
        if r2.status_code in [201, 204]:
            print(f"✅ GitHub Secret {secret_name} updated automatically! ({len(secret_value)} bytes)")
            return True
        else:
            print(f"Failed to update secret: {r2.status_code} {r2.text}")
            return False
    except Exception as e:
        print(f"Secret update error: {e}")
        import traceback; traceback.print_exc()
        return False

def refresh_via_playwright():
    print(f"Starting Playwright login for {BURNER_EMAIL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-infobars'
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US"
        )
        # Hide webdriver
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        
        # 1. Go directly to Google login with YouTube continue
        print("Navigating to Google login for YouTube...")
        page.goto("https://accounts.google.com/ServiceLogin?service=youtube&continue=https://www.youtube.com/signin%3Faction_handle_signin%3Dtrue%26app%3Ddesktop%26hl%3Den%26next%3Dhttps%253A%252F%252Fwww.youtube.com%252F&passive=true&hl=en", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        
        # Email step - robust selectors
        print("Filling email...")
        # Try multiple selectors
        email_selectors = [
            'input#identifierId',
            'input[type="email"]',
            'input[name="identifier"]',
        ]
        email_filled = False
        for sel in email_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.fill(sel, BURNER_EMAIL)
                email_filled = True
                print(f"Email filled via {sel}")
                break
            except:
                continue
        
        if not email_filled:
            # Try by role
            try:
                page.get_by_role("textbox", name="Email or phone").fill(BURNER_EMAIL)
                email_filled = True
            except:
                pass
        
        if not email_filled:
            page.screenshot(path="debug_email.png")
            raise Exception("Could not find email input - screenshot saved")
        
        # Click Next
        try:
            page.click('#identifierNext', timeout=10000)
        except:
            try:
                page.get_by_role("button", name="Next").click(timeout=10000)
            except:
                page.keyboard.press("Enter")
        
        print("Waiting for password page...")
        page.wait_for_timeout(5000)
        # Wait for password input visible
        page.wait_for_selector('input[type="password"], input[name="password"], input[name="Passwd"]', timeout=20000)
        time.sleep(2)
        
        print("Filling password...")
        pwd_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[name="Passwd"]',
        ]
        for sel in pwd_selectors:
            try:
                if page.locator(sel).first.is_visible():
                    page.fill(sel, BURNER_PASSWORD)
                    print(f"Password filled via {sel}")
                    break
            except:
                continue
        
        # Click password next
        try:
            page.click('#passwordNext', timeout=10000)
        except:
            try:
                page.get_by_role("button", name="Next").click(timeout=10000)
            except:
                page.keyboard.press("Enter")
        
        print("Waiting for login completion...")
        page.wait_for_timeout(8000)
        
        # Check for 2FA / captcha / challenge
        content = page.content()
        if "2-Step Verification" in content or "2-step" in content or "Verify it's you" in content:
            print("⚠️ 2FA detected! Your burner account has 2FA enabled.")
            print("👉 Fix: Disable 2FA for burner account at myaccount.google.com -> Security -> 2-Step Verification -> OFF")
            print("Or use an account without 2FA for bot.")
            page.screenshot(path="debug_2fa.png")
            browser.close()
            return False
        
        if "captcha" in content.lower() or "unusual traffic" in content.lower():
            print("⚠️ Captcha detected - Google blocked bot")
            print("👉 Fix: Login manually once from your PC with this burner account to YouTube, then run workflow again")
            page.screenshot(path="debug_captcha.png")
            browser.close()
            return False
        
        # Go to YouTube to generate YouTube cookies
        print("Navigating to YouTube...")
        page.goto("https://www.youtube.com/", wait_until="networkidle", timeout=60000)
        time.sleep(5)
        
        # Verify logged in by checking avatar or cookie presence
        cookies = context.cookies()
        youtube_cookies = [c for c in cookies if "youtube.com" in c.get('domain','') or "google.com" in c.get('domain','')]
        print(f"Got {len(cookies)} total cookies, {len(youtube_cookies)} YouTube/Google cookies")
        
        if len(youtube_cookies) < 5:
            print("⚠️ Too few cookies - likely not logged in")
            page.screenshot(path="debug_not_logged.png")
            browser.close()
            return False
        
        # Save in Netscape format
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This file is generated by MoviMoon Cookie Bot - V40.1\n")
            for c in cookies:
                domain = c.get('domain', '')
                flag = "TRUE" if domain.startswith('.') else "FALSE"
                path = c.get('path', '/')
                secure = "TRUE" if c.get('secure', False) else "FALSE"
                expiry = str(int(c.get('expires', 0))) if c.get('expires', -1) != -1 else "0"
                name = c.get('name', '')
                value = c.get('value', '')
                # Skip empty
                if not name:
                    continue
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
        
        size = Path("cookies.txt").stat().st_size
        print(f"✅ cookies.txt saved {size} bytes, {len(cookies)} cookies")
        
        # Auto update GitHub Secret if GH_TOKEN provided
        if size > 500:
            cookie_content = Path("cookies.txt").read_text(encoding="utf-8")
            update_github_secret("YOUTUBE_COOKIES", cookie_content)
        
        browser.close()
        return size > 500

success = False
if PLAYWRIGHT_AVAILABLE:
    try:
        success = refresh_via_playwright()
    except Exception as e:
        print(f"Playwright failed: {e}")
        import traceback; traceback.print_exc()

if not success:
    print("\n=== FALLBACK ===")
    # Keep old cookies if exists, don't create dummy 28 bytes
    if Path("cookies.txt").exists() and Path("cookies.txt").stat().st_size > 500:
        print(f"Keeping existing cookies.txt ({Path('cookies.txt').stat().st_size} bytes) - main workflow still works with android client")
    else:
        # Try to restore from previous artifact or keep existing YOUTUBE_COOKIES secret
        print("No valid cookies generated.")
        print("👉 Main workflow V40 will still work because Strategy 1 is NO-COOKIE (android client)")
        print("👉 This cookie bot is optional backup only")
        # Don't create tiny dummy that breaks yt-dlp
        if not Path("cookies.txt").exists():
            Path("cookies.txt").write_text("# Netscape HTTP Cookie File\n# Failed refresh - using NO-COOKIE strategy in main bot\n")
    success = True

print("=== Cookie Refresh Done ===")
