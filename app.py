import os
import json
import subprocess
from flask import Flask, render_template, send_from_directory, jsonify, request
from dotenv import load_dotenv

load_dotenv()
from werkzeug.utils import secure_filename

app = Flask(__name__)

IMAGES_DIR = "images"
RUNS_DIR = "runs"
RESULTS_FILE = os.path.join(RUNS_DIR, "results.json")

def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r") as f:
            return json.load(f)
    return {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

@app.route("/runs/<path:filename>")
def serve_run(filename):
    return send_from_directory(RUNS_DIR, filename)

@app.route("/api/images")
def get_images():
    if not os.path.exists(IMAGES_DIR):
        return jsonify([])
    
    images = os.listdir(IMAGES_DIR)
    detection_results = load_results()
    results = []
    
    for img in images:
        if img.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            has_output = os.path.exists(os.path.join(RUNS_DIR, img))
            plates = detection_results.get(img, [])
            results.append({
                "filename": img,
                "input_url": f"/images/{img}",
                "output_url": f"/runs/{img}" if has_output else None,
                "plates": plates
            })
            
    return jsonify(results)

@app.route("/api/process", methods=["POST"])
def process_all():
    try:
        subprocess.run(["python", "platform-anpr.py"], check=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
def upload_files():
    if 'files' not in request.files:
        return jsonify({"success": False, "error": "No files provided"}), 400
    
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({"success": False, "error": "No selected files"}), 400
        
    saved_files = []
    for file in files:
        if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            filename = secure_filename(file.filename)
            filepath = os.path.join(IMAGES_DIR, filename)
            file.save(filepath)
            saved_files.append(filename)
            
    if not saved_files:
        return jsonify({"success": False, "error": "No valid image formats found."}), 400
        
    try:
        subprocess.run(["python", "platform-anpr.py"], check=True)
        return jsonify({"success": True, "filenames": saved_files})
    except Exception as e:
        return jsonify({"success": False, "error": f"Upload succeeded but processing failed: {str(e)}"}), 500

@app.route("/api/delete/<filename>", methods=["DELETE"])
def delete_file(filename):
    filename = secure_filename(filename)
    img_path = os.path.join(IMAGES_DIR, filename)
    run_path = os.path.join(RUNS_DIR, filename)
    
    deleted = False
    try:
        if os.path.exists(img_path):
            os.remove(img_path)
            deleted = True
        if os.path.exists(run_path):
            os.remove(run_path)
            deleted = True
        
        # Remove from results.json too
        results = load_results()
        if filename in results:
            del results[filename]
            with open(RESULTS_FILE, "w") as f:
                json.dump(results, f, indent=2)
            
        if deleted:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

import csv
from io import StringIO
from flask import Response

@app.route("/api/export", methods=["GET"])
def export_csv():
    results = load_results()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Filename', 'Detected Plate', 'Confidence (%)'])
    
    for filename, plates in results.items():
        if not plates:
            cw.writerow([filename, 'None', '0.0'])
        else:
            for plate in plates:
                cw.writerow([filename, plate.get('plate_text', ''), plate.get('confidence', 0)])
                
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=anpr_results.csv"}
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)
