import time

from flask import Flask,request,jsonify,send_from_directory, abort
# from pyngrok import ngrok
from flask_cors import CORS
from makeVid import make_vid
import os
from datetime import datetime
import requests
from urllib.parse import urlparse
from werkzeug.utils import secure_filename
import re

app = Flask(__name__)

app.config['ALLOWED_DOMAINS'] = {'youtube.com', 'vimeo.com', 'example.com'}  # Whitelist domains
app.config['MAX_URL_SIZE'] = 1024 * 1024 * 500  # 500MB limit for URL downloads
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'Uploads')
app.config['DOWNLOADS'] = os.path.join(os.getcwd(), 'Download')

CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})



download = ''

def is_valid_video_url(url):
    """Validate URL format and domain"""
    try:
        result = urlparse(url)
        if all([result.scheme, result.netloc]):
            domain = '.'.join(result.netloc.split('.')[-2:])
            return domain in app.config['ALLOWED_DOMAINS']
        return False
    except:
        return False




@app.route('/api/Home',methods = ["GET","POST"] )
def home():
    try:
        if request.method == "POST":
            segments = request.get_json()["videoSegments"]
            file = request.get_json()["fileName"]
            name = request.get_json()["title"] + ".mp4"
            make_vid(segments,file,name)
            global download
            download = name
            print(name)

            return jsonify({
                "status": "success",
                "message": "Scenes saved successfully",
                "task_id": "12345"
            }), 200
    except Exception as e:
        print(e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500



def extract_unique_name(path):

    pattern = r'\/uploads\/([^\/"]+?)(?:\.mp4)?(?="|$)'
    match = re.search(pattern, path)
    return match.group(1) if match else None


@app.route('/api/uploads/<filename>', methods=['GET'])
def serve_video(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        mimetype='video/mp4'
    )


@app.route('/api/process_url', methods=['POST'])
def process_url():
    data = request.json
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    if not is_valid_video_url(url):
        return jsonify({'error': 'Invalid or unauthorized URL'}), 400

    try:
        # Verify URL points to a video
        head_response = requests.head(url, allow_redirects=True)
        content_type = head_response.headers.get('Content-Type', '')

        if 'video/' not in content_type:
            return jsonify({'error': 'URL does not point to a video file'}), 400

        # Download the video
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()

        # Generate filename
        filename = secure_filename(os.path.basename(urlparse(url).path)) or 'video.mp4'
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_name = f"url_{timestamp}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

        # Save with progress
        with open(save_path, 'wb') as f:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive chunks
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Optional: Add progress tracking here
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100


        return jsonify({
            'videoName':{unique_name},
            'message': 'Video processed successfully',
            'videoUrl': f"/uploads/{unique_name}"
        }), 200

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/process', methods=['POST'])
def process_video():
    data = request.json

    source = data.get('source')
    file_in_download = data.get('backEndRef')
    segments = data.get('segments')
    title = data.get('title')
    video = f'Uploads/{file_in_download}'
    # name = extract_unique_name(source)
    task = make_vid(segments,video,  title)

    return jsonify({
        '':'',
        'videoUrl':f'download/Short-{title}.mp4',
        'filename':f'Short-{title}.mp4',
        'task_id': task,
        # 'status_url': f'/api/tasks/{task}'
    }), 202

@app.route('/api/download/<path:filename>')
def download_file(filename):
    try:

        return send_from_directory(
            app.config['DOWNLOADS'],
            filename,
            mimetype='video/mp4',
            as_attachment=True
        )
    except FileNotFoundError:

       abort(404)


@app.route('/api/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['video']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400


    try:

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        new_file_name = f"url_{timestamp}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_file_name)
        file.save(save_path)

        return jsonify({
            'videoName':f'{new_file_name}',
            'message': 'File uploaded successfully',
            'videoUrl': f'/uploads/{new_file_name}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_flask():
    app.run(port=5000)

# print("hello")
run_flask()
if __name__ == '__main__':
    app.run(debug=True)
