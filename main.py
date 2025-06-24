import os
import time
import re
import logging
import pyodbc
import threading
from datetime import datetime, timedelta, UTC
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from makeVid import make_vid
import requests
from urllib.parse import urlparse
import uuid
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Azure Configuration from Environment Variables
app.config.update({
    'ALLOWED_DOMAINS': os.getenv('ALLOWED_DOMAINS', 'youtube.com,vimeo.com').split(','),
    'MAX_URL_SIZE': int(os.getenv('MAX_URL_SIZE', 524288000)),  # 500MB
    'UPLOAD_FOLDER': os.getenv('UPLOAD_PATH', '/mounts/store/uploads'),
    'DOWNLOADS': os.getenv('DOWNLOAD_PATH', '/mounts/store/downloads'),
    'FILE_LIFETIME': int(os.getenv('FILE_LIFETIME', 30)),  # minutes
    'SQL_SERVER': os.environ['SQL_SERVER'],
    'SQL_DATABASE': os.environ['SQL_DATABASE'],
    'SQL_USERNAME': os.environ['SQL_USERNAME'],
    'SQL_PASSWORD': os.environ['SQL_PASSWORD']
})

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOADS'], exist_ok=True)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('VideoEditor')


def get_db_connection():
    """Create and return a new database connection for each operation"""
    conn_str = f"Driver={{ODBC Driver 18 for SQL Server}};Server={app.config['SQL_SERVER']};Database={app.config['SQL_DATABASE']};Uid={app.config['SQL_USERNAME']};Pwd={app.config['SQL_PASSWORD']};Encrypt=yes;TrustServerCertificate=no;"
    return pyodbc.connect(conn_str)


def init_db():
    """Initialize database schema in Azure SQL"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Create tables if they don't exist
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='original_files')
        CREATE TABLE original_files (
            id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
            filename NVARCHAR(255) NOT NULL,
            path NVARCHAR(MAX) NOT NULL,
            created_at DATETIME DEFAULT GETDATE()
        )
        """)
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='processed_files')
        CREATE TABLE processed_files (
            id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
            filename NVARCHAR(255) NOT NULL,
            title NVARCHAR(255) NOT NULL,
            path NVARCHAR(MAX) NOT NULL,
            original_id UNIQUEIDENTIFIER,
            created_at DATETIME DEFAULT GETDATE(),
            expires_at DATETIME,
            FOREIGN KEY (original_id) REFERENCES original_files(id)
        )
        """)
        conn.commit()
        logger.info("Database tables initialized")


# Initialize database on app start
init_db()

CORS(app, resources={r"/api/*": {"origins": os.getenv('CORS_ORIGINS')}})


def cleanup_files():
    """Background task to clean up expired files"""
    logger.info("Cleanup thread started")
    while True:
        try:
            now = datetime.now(UTC)
            logger.info("Running cleanup cycle")

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Cleanup expired processed files
                cursor.execute("""
                    SELECT id, path, original_id 
                    FROM processed_files 
                    WHERE expires_at < ?
                """, now)
                expired_processed = cursor.fetchall()

                for row in expired_processed:
                    file_id, path, original_id = row
                    try:
                        # Delete processed file
                        if os.path.exists(path):
                            os.remove(path)
                            logger.info(f"Deleted expired processed file: {path}")

                        # Delete original file if exists
                        if original_id:
                            cursor.execute("SELECT path FROM original_files WHERE id = ?", original_id)
                            original_path = cursor.fetchone()
                            if original_path and os.path.exists(original_path[0]):
                                os.remove(original_path[0])
                                logger.info(f"Deleted original file: {original_path[0]}")

                        # Delete database records
                        cursor.execute("DELETE FROM processed_files WHERE id = ?", file_id)
                        if original_id:
                            cursor.execute("DELETE FROM original_files WHERE id = ?", original_id)
                    except Exception as e:
                        logger.error(f"Error deleting files: {str(e)}")

                # Cleanup orphaned original files (older than 30 minutes)
                cursor.execute("""
                    SELECT id, path FROM original_files
                    WHERE id NOT IN (SELECT original_id FROM processed_files)
                    AND created_at < DATEADD(minute, -30, GETDATE())
                """)
                orphaned_originals = cursor.fetchall()

                for row in orphaned_originals:
                    file_id, path = row
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                            logger.info(f"Deleted orphaned original file: {path}")
                        cursor.execute("DELETE FROM original_files WHERE id = ?", file_id)
                    except Exception as e:
                        logger.error(f"Error deleting orphaned file: {str(e)}")

                conn.commit()

        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

        # Run every 5 minutes
        time.sleep(300)


# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_files, daemon=True)
cleanup_thread.start()


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
        head_response = requests.head(url, allow_redirects=True, timeout=10)
        content_type = head_response.headers.get('Content-Type', '')

        if 'video/' not in content_type:
            return jsonify({'error': 'URL does not point to a video file'}), 400

        # Download the video
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Generate filename
        filename = secure_filename(os.path.basename(urlparse(url).path)) or 'video.mp4'
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        unique_name = f"url_{timestamp}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

        # Save file
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive chunks
                    f.write(chunk)

        # Save to database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            file_id = uuid.uuid4()
            cursor.execute("""
                INSERT INTO original_files (id, filename, path) 
                VALUES (?, ?, ?)
            """, (file_id, unique_name, save_path))
            conn.commit()

        return jsonify({
            'fileId': str(file_id),
            'videoName': unique_name,
            'message': 'Video processed successfully',
            'videoUrl': f"/api/uploads/{unique_name}"
        }), 200

    except requests.exceptions.RequestException as e:
        logger.error(f"URL fetch failed: {str(e)}")
        return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"URL processing error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/process', methods=['POST'])
def process_video():
    data = request.json
    source = data.get('source')
    segments = data.get('segments')
    title = data.get('title')

    # Extract filename from source URL
    filename = source.split('/')[-1]
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    output_filename = f"Short-{title}.mp4"
    output_path = os.path.join(app.config['DOWNLOADS'], output_filename)
    expires_at = datetime.now(UTC) + timedelta(minutes=app.config['FILE_LIFETIME'])

    # Process video
    make_vid(segments, input_path, output_path)

    # Save to database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        processed_id = uuid.uuid4()

        # Get original file ID
        cursor.execute("SELECT id FROM original_files WHERE filename = ?", filename)
        original_row = cursor.fetchone()
        original_id = original_row[0] if original_row else None

        cursor.execute("""
            INSERT INTO processed_files 
            (id, filename, title, path, original_id, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (processed_id, output_filename, title, output_path, original_id, expires_at))
        conn.commit()

    return jsonify({
        'videoUrl': f'/api/download/{output_filename}',
        'filename': output_filename,
        'task_id': str(processed_id)
    }), 202


@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(
            app.config['DOWNLOADS'],
            filename,
            mimetype='video/mp4',
            as_attachment=True
        )
    except FileNotFoundError:
        abort(404, description="File not found")


@app.route('/api/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Generate unique filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        unique_name = f"upload_{timestamp}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        file.save(save_path)

        # Save to database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            file_id = uuid.uuid4()
            cursor.execute("""
                INSERT INTO original_files (id, filename, path) 
                VALUES (?, ?, ?)
            """, (file_id, unique_name, save_path))
            conn.commit()

        return jsonify({
            "fileId": str(file_id),
            'videoName': unique_name,
            'videoUrl': f'/api/uploads/{unique_name}'
        }), 200

    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # For local development
    app.run(host='0.0.0.0', port=5000, debug=True)