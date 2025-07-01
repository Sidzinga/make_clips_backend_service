import os
import logging
import pyodbc
from datetime import datetime
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('CleanupJob')

# Get environment variables
SQL_SERVER = os.environ['SQL_SERVER']
SQL_DATABASE = os.environ['SQL_DATABASE']
SQL_USERNAME = os.environ['SQL_USERNAME']
SQL_PASSWORD = os.environ['SQL_PASSWORD']
UPLOAD_PATH = os.getenv('UPLOAD_PATH', r'D:\home\site\wwwroot\uploads')
DOWNLOAD_PATH = os.getenv('DOWNLOAD_PATH', r'D:\home\site\wwwroot\downloads')


def get_db_connection():
    conn_str = f"Driver={{ODBC Driver 18 for SQL Server}};Server={SQL_SERVER};Database={SQL_DATABASE};Uid={SQL_USERNAME};Pwd={SQL_PASSWORD};Encrypt=yes;TrustServerCertificate=no;"
    return pyodbc.connect(conn_str)


def cleanup_files():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.utcnow()

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
                    logger.info(f"Deleted expired file: {path}")

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
                    logger.info(f"Deleted orphaned file: {path}")
                cursor.execute("DELETE FROM original_files WHERE id = ?", file_id)
            except Exception as e:
                logger.error(f"Error deleting orphaned file: {str(e)}")

        conn.commit()


if __name__ == '__main__':
    logger.info("Starting cleanup WebJob")
    while True:
        try:
            cleanup_files()
        except Exception as e:
            logger.error(f"Cleanup cycle failed: {str(e)}")
        time.sleep(300)  # Run every 5 minutes