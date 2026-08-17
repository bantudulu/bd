import sqlite3
import os

db_path = os.path.expanduser("~/bantudulu/bantudulu_v2.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Cek semua tabel
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print(f"Tables: {tables}")

# Cek tabel pesanan (cek berbagai nama)
for tbl in tables:
    if 'esanan' in tbl or 'order' in tbl.lower() or 'Order' in tbl:
        c.execute(f"SELECT count(*) FROM [{tbl}]")
        count = c.fetchone()[0]
        c.execute(f"PRAGMA table_info([{tbl}])")
        cols = [r[1] for r in c.fetchall()]
        print(f"\n--- {tbl} ({count} rows) ---")
        print(f"Columns: {cols}")
        if count > 0:
            c.execute(f"SELECT * FROM [{tbl}] LIMIT 3")
            rows = c.fetchall()
            for row in rows:
                print(f"  {row}")
        break
else:
    print("\nTidak ada tabel pesanan ditemukan!")
    
conn.close()
