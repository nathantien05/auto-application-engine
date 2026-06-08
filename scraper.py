import os
import json
import time
import re
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# --- PROGRESS TRACKER HELPER ---
def update_progress(percent, message):
    try:
        with open("progress.json", "w") as f:
            json.dump({"percent": percent, "message": message}, f)
    except Exception:
        pass # Ignore lock errors if the browser reads it at the exact same millisecond

def scrape_job_urls(search_url, output_file="jobs.txt", max_pages=10):
    with open("config.json", "r") as f:
        config = json.load(f)
    
    role_keywords = config.get("role_keywords", [])
    exclude_keywords = config.get("exclude_keywords", [])
    
    # Compile patterns here based on the config values
    role_pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, role_keywords)) + r')\b', re.IGNORECASE)
    exclude_pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, exclude_keywords)) + r')\b', re.IGNORECASE)

    print("🔍 Scraping job URLs (ROLE + EXPERIENCE FILTER ACTIVATED)...")
    update_progress(5, "Launching Browser...")
    
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        if os.path.exists("handshake_cookies.json"):
            with open("handshake_cookies.json", "r") as f:
                raw_cookies = json.load(f)
            
            cookies = []
            for c in raw_cookies:
                name = c.get("name")
                value = c.get("value")
                if name and value is not None:
                    cookies.append({
                        "name": str(name),
                        "value": str(value),
                        "url": "https://app.joinhandshake.com" 
                    })
            context.add_cookies(cookies)
        else:
            update_progress(0, "⚠️ No cookies found!")
            return

        intercepted_jobs = {}
        scraping_state = {"phase": "Initial Load"}

        def aggressive_job_finder(data):
            found = []
            if isinstance(data, dict):
                is_graphql_job = data.get("__typename") in ["Job", "JobPosting"] and data.get("id")
                is_rest_job = data.get("id") and data.get("employer") and isinstance(data.get("employer"), dict)
                
                if is_graphql_job or is_rest_job:
                    found.append(data)
                
                for key, value in data.items():
                    found.extend(aggressive_job_finder(value))
            elif isinstance(data, list):
                for item in data:
                    found.extend(aggressive_job_finder(item))
            return found

        def handle_response(response):
            try:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    data = response.json()
                    hidden_jobs = aggressive_job_finder(data)
                    
                    for job in hidden_jobs:
                        job_id = str(job.get("id"))
                        company = "Unknown"
                        if isinstance(job.get("employer"), dict):
                            company = job["employer"].get("name", "Unknown")
                        elif job.get("employer_name"):
                            company = job["employer_name"]
                            
                        title = str(job.get("title", "")).strip()
                        if not title:
                            title = str(job.get("job_title", "")).strip()
                            
                        is_technical_role = role_pattern.search(title)
                        is_too_senior = exclude_pattern.search(title)
                        
                        if is_technical_role and not is_too_senior and job_id.isdigit() and job_id not in intercepted_jobs:
                            intercepted_jobs[job_id] = {"company": company, "title": title}
                        elif is_technical_role and is_too_senior and job_id.isdigit() and job_id not in intercepted_jobs:
                            intercepted_jobs[job_id] = "SKIPPED"
            except Exception:
                pass 

        page = context.new_page()
        page.on("response", handle_response)
        
        update_progress(10, "Loading Search Results...")
        page.goto(search_url, wait_until="domcontentloaded")
        page.wait_for_timeout(5000) 
        
        if "login" in page.url or "sign-in" in page.url:
            update_progress(0, "❌ Blocked at login page.")
            browser.close()
            return
        
        for page_num in range(1, max_pages + 1):
            percent = int((page_num / max_pages) * 90)
            valid_count = sum(1 for v in intercepted_jobs.values() if v != "SKIPPED")
            update_progress(percent, f"Scraping Page {page_num} of {max_pages} (Found {valid_count} jobs)...")
            
            page.wait_for_timeout(8000) 
            
            if page_num < max_pages:
                clicked = page.evaluate("""() => {
                    const elements = Array.from(document.querySelectorAll('button, a'));
                    const nextBtns = elements.filter(el => {
                        const aria = (el.getAttribute('aria-label') || '').toLowerCase().trim();
                        const title = (el.getAttribute('title') || '').toLowerCase().trim();
                        const hook = (el.getAttribute('data-hook') || '').toLowerCase().trim();
                        return aria === 'next page' || title === 'next page' || hook === 'search-pagination-next' || aria === 'next';
                    });
                    
                    for (let btn of nextBtns) {
                        if (!btn.disabled && btn.getAttribute('aria-disabled') !== 'true') {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                
                if clicked:
                    page.wait_for_timeout(2500) 
                else:
                    break
                
        browser.close()
        
        job_entries = []
        for job_id, info in intercepted_jobs.items():
            if info != "SKIPPED":
                company_clean = info["company"].replace(",", "").replace(" ", "_").replace('"', '')
                title_clean = info["title"].replace(",", "").replace('"', '')
                full_url = f"https://app.joinhandshake.com/jobs/{job_id}"
                job_entries.append(f"{company_clean},{title_clean},{full_url}")
            
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(job_entries))
            
        update_progress(100, f"✅ Done! Found {len(job_entries)} highly relevant jobs.")

if __name__ == "__main__":
    with open("config.json", "r") as f:
        config = json.load(f)
        
    SEARCH_URL = config.get("target_url", "")
    MAX_PAGES = int(config.get("max_pages", 10))
    print("Max amount of Jobs, 300")
    if SEARCH_URL:
        scrape_job_urls(SEARCH_URL, max_pages=MAX_PAGES)