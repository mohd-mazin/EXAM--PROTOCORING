import os

CSS_TO_APPEND = """
/* Back Navigation Button */
.back-btn {
    position: fixed; /* Sticky on all pages */
    top: 20px;
    left: 20px;
    display: inline-flex;
    align-items: center;
    padding: 10px 15px;
    background-color: var(--card-bg);
    color: var(--primary-color);
    text-decoration: none;
    border-radius: 12px;
    font-weight: 600;
    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
    z-index: 9999;
    border: 2px solid transparent;
}
.back-btn:hover, .back-btn:focus {
    transform: translateX(-5px);
    box-shadow: 0 6px 15px rgba(0,0,0,0.15);
    background-color: var(--primary-color);
    color: white;
    outline: none;
}
@media (max-width: 768px) {
    .back-btn {
        top: 10px;
        left: 10px;
        padding: 8px 12px;
        font-size: 0.9rem;
    }
}
"""

with open('static/css/style.css', 'a', encoding='utf-8') as f:
    f.write("\n" + CSS_TO_APPEND)

BUTTONS = {
    'templates/verify_face.html': '<a href="/login" class="back-btn" title="Back to Student Login" aria-label="Back to Student Login">&#11013; Back to Student Login</a>\n',
    'templates/gallery.html': '<a href="/admin" class="back-btn" title="Back to Admin Portal" aria-label="Back to Admin Portal">&#11013; Back to Admin Portal</a>\n',
    'templates/architecture.html': '<a href="/admin" class="back-btn" title="Back to Admin Portal" aria-label="Back to Admin Portal">&#11013; Back to Admin Portal</a>\n',
    'templates/report.html': '<a href="/dashboard" class="back-btn" title="Back to Dashboard" aria-label="Back to Dashboard">&#11013; Back to Dashboard</a>\n',
    'templates/replay.html': '<a href="/dashboard" class="back-btn" title="Back to Dashboard" aria-label="Back to Dashboard">&#11013; Back to Dashboard</a>\n'
}

for path, button_html in BUTTONS.items():
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Inject right after <body>
        if '<body' in content:
            body_end = content.find('>', content.find('<body')) + 1
            new_content = content[:body_end] + '\n' + button_html + content[body_end:]
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Added back button to {path}")
        else:
            print(f"No body tag found in {path}")
    else:
        print(f"File {path} not found")

print("Navigation injection complete.")
