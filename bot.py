import csv
from datetime import datetime
import os
import json
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import time
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from parser import extract_resume_text
from writer import generate_cover_letter

with open("config.json", "r") as f:
    config = json.load(f)

# These variables now hold the full paths to your files from the uploads/ folder
RESUME_PATH = config.get("resume_path")
TRANSCRIPT_PATH = config.get("transcript_path")

# --- NATIVE PDF WRITER ---
def save_to_pdf(text, company_name):
    pdf = FPDF(unit="in", format="Letter")
    pdf.set_margins(left=1.0, top=1.0, right=1.0)
    pdf.set_auto_page_break(auto=True, margin=1.0)
    pdf.add_page()
    
    text = text.replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'").replace('\u2014', "-").replace('\u2013', "-")
    is_first_line = True
    
    for line in text.split('\n'):
        clean_line = line.strip()
        if is_first_line and not clean_line:
            continue
        if is_first_line and "Nathan Tien" in clean_line:
            pdf.set_font("Times", style="B", size=22)
            pdf.cell(w=0, h=0.3, text=clean_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_y(pdf.get_y() + 0.05)
            is_first_line = False
        elif not clean_line:
            pdf.set_y(pdf.get_y() + 0.15)
        else:
            pdf.set_font("Times", size=11)
            pdf.multi_cell(w=0, h=0.2, text=clean_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            is_first_line = False
            
    output_folder = "cover_letters"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    filename = f"{output_folder}/Nathan_Tien_{company_name}_Cover_Letter.pdf"
    pdf.output(filename)
    print(f"   -> SUCCESS! PDF saved to: {filename}")
    return filename


# --- HANDSHAKE APPLICATION HANDLER ---
def handle_handshake_apply(page, company_name, job_description_text):
    print("   -> Looking for Handshake Apply button...")

    # CHECK IF ALREADY APPLIED
    withdraw_btn = page.locator("button:has-text('Withdraw Application'), a:has-text('Withdraw Application')")
    if withdraw_btn.count() > 0:
        print(f"   -> ⚠️ Already applied to {company_name}. Skipping.")
        return False, "Already Applied"

    # CHECK IF EXTERNAL APPLICATION
    external_btn = page.locator("button:has-text('Apply Externally'), a:has-text('Apply Externally')")
    if external_btn.count() > 0:
        print(f"   -> ⚠️ External application required. Skipping.")
        return False, "External Application"

    # 1. OPEN MODAL
    apply_btn = page.locator("button:has-text('Apply'):visible, a:has-text('Apply'):visible").first
    if apply_btn.count() == 0:
        return False, "Apply button not found"
        
    apply_btn.click()
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)
    
    required_files = 0
    if page.locator("text='Attach your resume'").count() > 0:
        required_files += 1
    if page.locator("text='Attach your cover letter'").count() > 0:
        required_files += 1
    if page.locator("text='Attach your transcript'").count() > 0:
        required_files += 1
    
    print(f"   -> This job requires {required_files} files")

    # 5. UPLOAD FILES
    print("   -> Uploading files...")

    resume_search = page.locator("input[placeholder*='Search your resumes']")
    if resume_search.count() > 0:
        resume_search.first.click()
        resume_name = os.path.basename(RESUME_PATH)
        resume_option = page.locator(f"//div[contains(@class, 'option') or contains(@class, 'item') or @role='option']//*[contains(text(), '{resume_name}')]").first
        if resume_option.count() == 0:
            resume_input = page.locator("input[name='file-Resume']")
            resume_input.first.set_input_files(RESUME_PATH)
        else:
            resume_option.wait_for(state="visible")
            resume_option.click()

    transcript_search = page.locator("input[placeholder*='Search your transcripts']")
    if transcript_search.count() > 0:
        transcript_search.first.click()
        transcript_name = os.path.basename(TRANSCRIPT_PATH)
        transcript_option = page.locator(f"//div[contains(@class, 'option') or contains(@class, 'item') or @role='option']//*[contains(text(), '{transcript_name}')]").first
        if transcript_option.count() == 0:
            transcript_input = page.locator("input[name='file-Transcript']")
            transcript_input.first.set_input_files(TRANSCRIPT_PATH)
        else:
            transcript_option.wait_for(state="visible")
            transcript_option.click()

    cover_letter_search = page.locator("input[placeholder*='Search your cover letters']")
    if cover_letter_search.count() > 0:
        cover_letter_input = page.locator("input[name='file-Cover Letter']")
        print("   -> Generating cover letter...")
        cover_letter_path = save_to_pdf(
            generate_cover_letter(extract_resume_text(RESUME_PATH), job_description_text),
            company_name
        )
        cover_letter_input.first.set_input_files(cover_letter_path)
        print("   -> Uploaded cover letter")

    # 6. WAIT FOR EXACTLY REQUIRED_FILES PREVIEW LINKS
    print(f"   -> Waiting for {required_files} files to finish uploading...")
    
    max_wait = 60
    elapsed = 0
    
    while elapsed < max_wait:
        preview_count = page.locator("a:has-text('Preview document')").count()
        print(f"   -> {preview_count}/{required_files} files ready...")
        
        if preview_count >= required_files:
            print("   -> ✅ All files uploaded!")
            time.sleep(2)
            break
            
        time.sleep(2)
        elapsed += 2
    else:
        print("   -> ❌ Timeout: Files never finished uploading.")
        return False, "File Upload Timeout"

    # 7. SUBMIT
    print("   -> Clicking Submit...")
    submit_btn = page.locator("button:has-text('Submit Application'), button:has-text('Submit')").first
    submit_btn.click()
    
    try:
        page.wait_for_selector("text=Application submitted", timeout=5000)
        print(f"   -> ✅ APPLICATION SUBMITTED for {company_name}!")
        return True, "SUCCESS"
    except:
        print(f"   -> ❌ Submission failed.")
        return False, "Submission failed (no confirmation)"

# --- MAIN PIPELINE ---
def auto_apply_pipeline(job_url, company_name):
    print(f"\n1. Deploying Stealth Bot to: {job_url}")

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        if os.path.exists("handshake_cookies.json"):
            with open("handshake_cookies.json", "r") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            print("   -> Handshake cookies loaded!")
        else:
            print("   -> ⚠️ No cookies found! Run save_cookies.py first.")
            return False, "No cookies"

        page = context.new_page()
        page.goto(job_url, wait_until="domcontentloaded")
        time.sleep(5)

        print("2. Extracting job requirements...")
        job_description_text = page.locator("body").inner_text()

        if len(job_description_text) < 500 or "Page not found" in job_description_text:
            print("   ❌ ERROR: Broken job page. Skipping.")
            browser.close()
            return False, "Broken Job Page"

        print("3. Executing Application Logic...")
        success, reason = handle_handshake_apply(page, company_name, job_description_text)

        if not success:
            print(f"   -> ❌ Could not apply to {company_name}. Reason: {reason}")

        print("4. Application cycle complete. Closing browser.")
        browser.close()
        
        return success, reason

# --- BATCH PROCESSOR ---
if __name__ == "__main__":
    print("🤖 BATCH PROCESSOR INITIATED...\n")

    results_filename = "application.csv"
    duplicates_filename = "duplicates.csv"
    job_count = 0
    
    # RESTRUCTURED HEADER: Success and Failed are now separate columns!
    if not os.path.exists(results_filename):
        with open(results_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Success", "Failed", "Reason", "Company", "Job URL", "Timestamp"])

    if not os.path.exists(duplicates_filename):
        with open(duplicates_filename, "w", newline="", encoding="utf-8") as dup_file:
            duplicates = csv.writer(dup_file)
            duplicates.writerow(["Reason", "Company", "Job URL", "Timestamp"])

    with open("jobs.txt", "r") as file:
        lines = file.readlines()

    for line in lines:
        if job_count == 295:
            break;
        if not line.strip():
            continue

        parts = line.split(",")
        target_company = parts[0].strip()
        target_title = parts[1].strip()
        target_job_url = parts[2].strip()

        print(f"\n====================================================")
        print(f"🚀 STARTING APPLICATION FOR: {target_company.upper()}")
        print(f"====================================================")

        # Initialize empty columns
        col_success = ""
        col_failed = ""
        col_reason = ""

        try:
            is_success, reason = auto_apply_pipeline(target_job_url, target_company)
            
            # Route the text to the correct column based on success/failure
            if is_success:
                col_success = "SUCCESS"
                col_reason = "Applied"
                job_count += 1
            else:
                col_failed = "FAILED"
                col_reason = reason

                
        except Exception as e:
            print(f"❌ Failed to process {target_company}. Error: {e}")
            col_failed = "ERROR"
            col_reason = str(e)[:50] 

        # Log to the CSV file and duplicates file with the new 6-column layout
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if reason == "Already Applied":
            with open(duplicates_filename, "a", newline="", encoding="utf-8") as dup_file:
                duplicates = csv.writer(dup_file)
                duplicates.writerow([col_reason, target_company, target_job_url, timestamp])
        else:
            with open(results_filename, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([col_success, col_failed, col_reason, target_company, target_job_url, timestamp])
        time.sleep(3)

    print(f"\n✅ ALL JOBS PROCESSED.")
    print(f"📁 OPEN THIS FILE TO SEE RESULTS: {os.path.abspath(results_filename)}")