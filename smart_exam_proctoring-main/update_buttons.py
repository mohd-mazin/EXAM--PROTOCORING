import os
import re

files = [
    'templates/admin.html',
    'templates/admin_dashboard.html',
    'templates/gallery.html',
    'templates/architecture.html',
    'templates/report.html'
]

NEW_BUTTON = """
<div style="position: fixed; top: 20px; right: 20px; display: flex; flex-direction: column; align-items: flex-end; gap: 10px; z-index: 10000;">
    <a href="/" class="home-btn" style="background:#2563eb; color:white; padding:8px 16px; border-radius:8px; text-decoration:none; font-weight:600; font-size:14px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display:flex; align-items:center; gap:6px;">
        &#127968; Back to Login Selection
    </a>
</div>
"""

student_btn_pattern = re.compile(r'<a href="/dashboard" class="back-btn student-btn".*?</a>', re.DOTALL)
admin_btn_pattern = re.compile(r'<a href="/admin" class="back-btn admin-btn".*?</a>', re.DOTALL)

for f in files:
    if not os.path.exists(f):
        continue
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
        
    # Remove old injected buttons
    content = student_btn_pattern.sub('', content)
    content = admin_btn_pattern.sub('', content)
    
    # Remove new button if it was already added (idempotency)
    content = content.replace(NEW_BUTTON, '')
    
    # Inject new button
    body_match = re.search(r'<body[^>]*>', content)
    if body_match:
        idx = body_match.end()
        content = content[:idx] + '\n' + NEW_BUTTON + content[idx:]
        
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
        
    print(f"Updated {f}")

print("Done updating buttons.")
