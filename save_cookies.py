from playwright.sync_api import sync_playwright
import json
import time

def save_handshake_cookies():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto("https://app.joinhandshake.com/login")
        
        print("Log in manually in the browser window...")
        print("After you are FULLY logged in and can see the Handshake dashboard...")
        print("Come back here and press ENTER to save cookies")
        
        input("Press ENTER when you are logged in...")  # Wait for you manually
        
        cookies = context.cookies()
        with open("handshake_cookies.json", "w") as f:
            json.dump(cookies, f)
            
        print("Cookies saved!")
        
        # Keep browser open so you can verify
        time.sleep(2)
        browser.close()

save_handshake_cookies()