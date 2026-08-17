import sqlite3, os

db_path = os.path.expanduser("~/bantudulu/app/bantudulu_v2.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Cek user
c.execute("SELECT id, email, nama, role FROM users")
users = c.fetchall()
print("=== USERS ===")
for u in users:
    print(f"  {u[0][:12]}... | {u[1]:30s} | {u[2]:20s} | {u[3]}")

# Cek pesanan per user
print("\n=== PESANAN PER USER ===")
c.execute("SELECT user_id, status, count(*) FROM pesanan GROUP BY user_id, status ORDER BY user_id")
rows = c.fetchall()
for r in rows:
    print(f"  {r[0][:12]}... | status={r[1]:12s} | count={r[2]}")

# Cek total per user
print("\n=== TOTAL PESANAN PER USER ===")
c.execute("SELECT user_id, count(*) FROM pesanan GROUP BY user_id ORDER BY count(*) DESC")
rows = c.fetchall()
for r in rows:
    print(f"  {r[0][:12]}... | {r[1]} pesanan")

conn.close()
