import sys
from app import app

print("=== FLASK ROUTE MAP ===")
for rule in app.url_map.iter_rules():
    print(rule)

print("\n=== FIND DUPLICATE ADMIN ===")
with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'def admin(' in line or 'def admin_dashboard(' in line or '/admin' in line or '/delete_evidence' in line:
            print(f"Line {i+1}: {line.strip()}")
