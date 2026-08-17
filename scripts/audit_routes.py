import sys
sys.path.insert(0, r'C:\Users\SER5 MAX\bantudulu')
import os
os.environ['DB_ENGINE'] = 'mysql'

from app.main import app

print("=== ALL ROUTES ===")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        print(f"  {list(route.methods)} {route.path}")
    elif hasattr(route, 'routes'):
        for sr in route.routes:
            if hasattr(sr, 'path') and hasattr(sr, 'methods'):
                print(f"  {list(sr.methods)} {sr.path}")

print("\n=== STATIC FILES ===")
for route in app.routes:
    if hasattr(route, 'name') and route.name == 'static':
        print(f"  Static: {route}")
