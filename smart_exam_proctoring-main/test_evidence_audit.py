import requests
import json
from app import app

def run_audit():
    with app.test_client() as client:
        # Mock admin session
        with client.session_transaction() as sess:
            sess['admin_id'] = 'admin'
        
        # 1. Fetch current debug evidence
        print("Fetching initial debug evidence...")
        res = client.get('/api/admin/evidence_debug')
        data = res.get_json()
        
        if not data:
            print("No evidence data available to test.")
            return
            
        initial_ids = [item['id'] for item in data]
        target_id = 12 if 12 in initial_ids else initial_ids[0]
        
        print(f"Targeting ID for deletion: {target_id}")
        
        # 2. Delete it
        del_res = client.post(f'/delete_evidence/{target_id}')
        print(f"Delete response: {del_res.get_json()}")
        
        # 3. Fetch debug again
        print("Fetching debug evidence after deletion...")
        res2 = client.get('/api/admin/evidence_debug')
        data2 = res2.get_json()
        final_ids = [item['id'] for item in data2]
        
        print(f"IDs returned by API: {final_ids}")
        print(f"Target ID {target_id} still exists in return array? {target_id in final_ids}")
        print(f"Current evidence count: {len(final_ids)}")

if __name__ == '__main__':
    run_audit()
