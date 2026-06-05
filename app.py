from flask import Flask, render_template, jsonify, request
from werkzeug.utils import secure_filename
import csv
import os
import subprocess
import json

app = Flask(__name__)
# Tells Flask where to save the uploads securely
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

PYTHON_PATH = r"C:\Users\name\AppData\Local\Microsoft\WindowsApps\python3.11.exe"
CONFIG_FILE = "config.json"
PROGRESS_FILE = "progress.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"target_url": "", "max_pages": 10, "resume_path": "", "transcript_path": ""}

@app.route('/')
def dashboard():
    # Load History and track processed URLs to remove them from the Queue
    history_jobs = []
    processed_urls = set()
    
    if os.path.exists("application.csv"):
        with open("application.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                history_jobs.append(row)
                processed_urls.add(row.get("Job URL", "").strip())
                
    # Load Current Queue, skipping jobs that are already processed
    current_queue = []
    if os.path.exists("jobs.txt"):
        with open("jobs.txt", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        url = parts[1].strip()
                        if url not in processed_urls:
                            current_queue.append({"Company": parts[0].strip(), "Job URL": url})

    return render_template('index.html', history=history_jobs, queue=current_queue, config=load_config())

@app.route('/save_config', methods=['POST'])
def save_config():
    try:
        new_data = request.json
        print("DEBUG: Received data from website:", new_data)
        # 1. Load the existing file so we don't lose your paths/URLs
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                try:
                    config = json.load(f)
                except:
                    config = {}
        else:
            config = {}
            
        # 2. Merge the new stuff (keywords) with the old stuff (paths)
        config.update(new_data)
        
        # 3. Save the result
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
            
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error saving config: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"status": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "No selected file"}), 400
    
    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)
    
    return jsonify({"status": "Success", "path": os.path.abspath(save_path)})

@app.route('/progress', methods=['GET'])
def get_progress():
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r") as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify({"percent": 0, "message": "Idle"})

@app.route('/run_scraper', methods=['POST'])
def run_scraper():
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"percent": 0, "message": "Initializing Scraper..."}, f)
    subprocess.Popen([PYTHON_PATH, "scraper.py"])
    return jsonify({"status": "Scraper initiated!"})

@app.route('/run_bot', methods=['POST'])
def run_bot():
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"percent": 0, "message": "Initializing Auto-Applier..."}, f)
    subprocess.Popen([PYTHON_PATH, "bot.py"])
    return jsonify({"status": "Auto-Applier initiated!"})

if __name__ == '__main__':
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"percent": 0, "message": "Idle"}, f)
    app.run(debug=True, port=5000)