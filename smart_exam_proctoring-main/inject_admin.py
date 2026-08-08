import os

CSS_TO_APPEND = """
<style>
.back-admin-btn {
    position: fixed;
    top: 20px;
    left: 20px;
    z-index: 9999;
    background: #2563eb;
    color: white;
    padding: 10px 16px;
    border-radius: 8px;
    text-decoration: none;
    font-weight: 600;
}
.back-admin-btn:hover {
    background: #1d4ed8;
}
</style>
"""

HTML_TO_APPEND = """
<a href="/admin" class="back-admin-btn">
    &#11013; Back to Admin Portal
</a>
"""

path = 'templates/admin.html'
if os.path.exists(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if '</head>' in content and '.back-admin-btn' not in content:
        content = content.replace('</head>', CSS_TO_APPEND + '\n</head>')
        
    if '<body' in content and 'back-admin-btn' not in content.split('<body')[1]:
        body_end = content.find('>', content.find('<body')) + 1
        content = content[:body_end] + '\n' + HTML_TO_APPEND + content[body_end:]
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Injected into {path}")
