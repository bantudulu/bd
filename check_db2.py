import sqlite3
import os

# Cek database di app/ (yang benar)
db_path = os.path.expanduser("~/bantudulu/app/bantudulu_v2.db")
print(f"Checking: {db_path}")
print(f"Exists: {os.path.exists(db_path)}, Size: {os.path.getsize(db_path) if os.path.exists(db_path) else 0}")

if not os.path.exists(db_path):
    print("Database not found!")
    exit()

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Cek semua tabel
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print(f"Tables ({len(tables)}): {tables}")

# Cek tabel yang mengandung pesanan/order
for tbl in tables:
    if 'esan' in tbl.lower() or 'rder' in tbl.lower() or 'Order' in tbl.lower():
        c.execute(f"SELECT count(*) FROM [{tbl}]")
        count = c.fetchone()[0]
        c.execute(f"PRAGMA table_info([{tbl}])")
        cols = [r[1] for r in c.fetchall()]
        print(f"\n--- {tbl} ({count} rows) ---")
        print(f"Columns: {cols}")
        if count > 0:
            c.execute(f"SELECT * FROM [{tbl}] LIMIT 5")
            rows = c.fetchall()
            for row in rows:
                print(f"  {row}")
        else:
            print("  (empty)")

# Juga cek semua data
for tbl in tables:
    c.execute(f"SELECT count(*) FROM [{tbl}]")
    count = c.fetchone()[0]
    print(f"  {tbl}: {count} rows")

conn.close()
