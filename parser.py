import fitz  # This is the actual name of the PyMuPDF library inside Python

def extract_resume_text(file_path):
    print(f"Instructing the bot to read: {file_path}...")
    
    # Open the PDF document
    doc = fitz.open(file_path)
    full_text = ""
    
    # Loop through every page and extract the text
    for page in doc:
        full_text += page.get_text()
        
    doc.close()
    return full_text

if __name__ == "__main__":
    # Make sure this matches exactly what you named your uploaded file!
    my_resume_text = extract_resume_text("resume.pdf")
    
    print("\n--- RESUME SUCCESSFULLY EXTRACTED ---")
    # We will just print the first 500 characters so it doesn't flood your terminal
    print(my_resume_text[:500])
    print("...")
    print(f"\nTotal characters read: {len(my_resume_text)}")