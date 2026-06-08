import os
from anthropic import Anthropic
from dotenv import load_dotenv

# Import the parser function you wrote earlier!
from parser import extract_resume_text

# 1. Load the secret key from your .env file
load_dotenv()
test_key = os.getenv("ANTHROPIC_API_KEY")

def generate_cover_letter(resume_text, job_description):
    print("Waking up Claude and sending the documents...")
    
    # This automatically finds the ANTHROPIC_API_KEY in your environment
    client = Anthropic() 
    
    # 2. Build the exact prompt we want Claude to read
    prompt = f"""
    You are an expert career coach writing a cover letter for me. 
    
    CRITICAL INSTRUCTIONS:
    1. DO NOT use any markdown formatting (no asterisks **, no dashes ---, no hash symbols).
    2. Write a concise, impactful letter (strictly between 250 and 300 words). It MUST fit on a single page.
    3. Expand on my technical projects, coursework, and skills in detail. Connect them deeply to the job requirements so it doesn't sound like fluff.
    4. Keep it grounded, professional, and confident. Do not use AI buzzwords like "delve" or "testament".
    
    Start the letter EXACTLY like this (do not add anything before my name):
    Nathan Tien
    Clarksburg, MD
    (301) 913-4624
    nathantien05@gmail.com
    
    [Insert Company/Department Name]
    
    Dear [Insert Hiring Manager or Coordinator],
    
    Here is my parsed resume:
    {resume_text}
    
    Here is the job description I am applying for:
    {job_description}
    """

    # 3. Call the Claude 4.6 Sonnet model
    response = client.messages.create(
        model="claude-sonnet-4-6", # <-- Just the simple name!
        max_tokens=800,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.content[0].text