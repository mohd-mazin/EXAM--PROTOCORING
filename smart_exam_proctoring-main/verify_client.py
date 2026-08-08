import sys
from app import app
from flask import session

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['admin_id'] = 'admin'
        sess['student_id'] = 1
        
    print("\n--- RUNTIME VERIFICATION ---")
    routes = ['/admin', '/gallery', '/architecture', '/report']
    for r in routes:
        resp = client.get(r)
        html = resp.get_data(as_text=True)
        if 'ADMIN TEMPLATE TEST' in html:
            idx = html.find('ADMIN TEMPLATE TEST: ')
            if idx != -1:
                filename = html[idx+21:idx+50].split('<')[0].strip()
                print(f"Route {r:15} -> Renders: {filename:20}")
        else:
            print(f"Route {r:15} -> NO BANNER FOUND")
            
        if 'back-admin-btn' in html:
            print(f"  [+] Back Button: YES")
        else:
            print(f"  [-] Back Button: NO")
            
            # Show a snippet of HTML after body to prove it
            if '<body' in html:
                body_end = html.find('>', html.find('<body')) + 1
                snippet = html[body_end:body_end+200].strip().replace('\n', ' ')
                print(f"  [*] HTML Snippet: {snippet[:150]}...")
