import os
import re

files = [
    'templates/report.html',
    'templates/admin.html',
    'templates/admin_dashboard.html',
    'templates/gallery.html',
    'templates/architecture.html'
]

NEW_BUTTONS = """
<a href="/dashboard" class="back-btn student-btn" style="position:fixed; top:20px; left:20px; z-index:9999; background:#f39c12; color:white; padding:10px 16px; border-radius:8px; text-decoration:none; font-weight:600;">
&#11013; Back to Student Dashboard
</a>
<a href="/admin" class="back-btn admin-btn" style="position:fixed; top:70px; left:20px; z-index:9999; background:#2563eb; color:white; padding:10px 16px; border-radius:8px; text-decoration:none; font-weight:600;">
&#11013; Back to Admin Dashboard
</a>
"""

# Regex to match the banner div
banner_pattern = re.compile(r'<div style="background:red; color:white; padding:20px; font-size:24px; font-weight:bold; position:fixed; top:0; width:100%; z-index:100000; text-align:center;">.*?</div>', re.DOTALL)

# Regex to match the old back-admin-btn block
old_btn_pattern = re.compile(r'<a href="/admin" class="back-admin-btn">.*?</a>', re.DOTALL)

# Regex to match the old back-btn block (if any exist from earlier injections)
old_student_btn_pattern = re.compile(r'<a href="/dashboard" class="back-btn"[^>]*>.*?</a>', re.DOTALL)

# Also remove the <style> blocks previously injected for .back-admin-btn
style_pattern = re.compile(r'<style>\s*\.back-admin-btn\s*\{.*?</style>', re.DOTALL)

for f in files:
    if not os.path.exists(f):
        continue
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
        
    # Remove old cruft
    content = banner_pattern.sub('', content)
    content = old_btn_pattern.sub('', content)
    content = old_student_btn_pattern.sub('', content)
    content = style_pattern.sub('', content)
    
    # Remove the new buttons if they were already added (to prevent duplicates during testing)
    content = content.replace(NEW_BUTTONS, '')
    
    # Inject new buttons right after <body...>
    body_match = re.search(r'<body[^>]*>', content)
    if body_match:
        idx = body_match.end()
        content = content[:idx] + '\n' + NEW_BUTTONS + content[idx:]
        
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
        
    print(f"Processed {f}")

print("Done fixing templates.")
