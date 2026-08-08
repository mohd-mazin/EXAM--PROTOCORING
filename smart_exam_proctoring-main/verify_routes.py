import os
import requests
import time
import subprocess
import signal

# 1. Add banner to templates
banner_html = """
<div style="background:red; color:white; padding:20px; font-size:24px; font-weight:bold; position:fixed; top:0; width:100%; z-index:100000; text-align:center;">
ADMIN TEMPLATE TEST: {filename}
</div>
"""
files = ['admin.html', 'admin_dashboard.html', 'gallery.html', 'architecture.html', 'report.html']
for f in files:
    path = os.path.join('templates', f)
    with open(path, 'r', encoding='utf-8') as file:
        content = file.read()
    if '<body' in content and 'ADMIN TEMPLATE TEST' not in content:
        idx = content.find('>', content.find('<body')) + 1
        content = content[:idx] + banner_html.format(filename=f) + content[idx:]
        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"Added banner to {f}")

# Wait a second for file saves
time.sleep(1)

# 2. Fetch routes locally to see what HTML is returned
routes = ['/admin', '/gallery', '/architecture', '/report']

print("\n--- RUNTIME VERIFICATION ---")
for r in routes:
    try:
        resp = requests.get(f"http://127.0.0.1:5000{r}", timeout=2)
        html = resp.text
        if 'ADMIN TEMPLATE TEST' in html:
            # Extract which filename
            idx = html.find('ADMIN TEMPLATE TEST: ')
            if idx != -1:
                filename = html[idx+21:idx+50].split('<')[0].strip()
                print(f"Route {r} renders -> {filename}")
        else:
            print(f"Route {r} did NOT render a template with the banner.")
            
        # Also check for the back button
        if 'back-admin-btn' in html:
            print(f"  - Back button is PRESENT in the HTML for {r}")
        else:
            print(f"  - Back button is MISSING in the HTML for {r}")
    except Exception as e:
        print(f"Failed to fetch {r}: {e}")

