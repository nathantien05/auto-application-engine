import fitz

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
