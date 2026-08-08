import sys
from app import app

print("=== FLASK ROUTE MAP ===")
for rule in app.url_map.iter_rules():
    print(f"{rule} | Methods: {rule.methods}")
