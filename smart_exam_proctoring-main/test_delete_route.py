import sys
import io
from app import app, get_db_connection
import sqlite3

# Suppress werkzeug logs for clear output
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def run_test():
    with app.test_client() as client:
        # Create a mock session
        with client.session_transaction() as sess:
            sess['admin_id'] = 'admin'
            
        # Get a valid ID
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM violations WHERE evidence_path IS NOT NULL LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print("No evidence found to test.")
            return
            
        vid = row[0]
        
        # Hit route
        res = client.post(f'/delete_evidence/{vid}')

run_test()
