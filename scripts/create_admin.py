import asyncio
import getpass
import os

from sqlalchemy import select

from app.auth import hash_password
from app.database import async_session
from app.models import User


async def main():
    print("BantuDulu - Create/Rotate Admin")
    email = (os.getenv("ADMIN_EMAIL") or input("Admin email: ")).strip().lower()
    nama = (os.getenv("ADMIN_NAME") or input("Nama admin [Admin BantuDulu]: ")).strip() or "Admin BantuDulu"
    no_hp = (os.getenv("ADMIN_PHONE") or input("Nomor HP: ")).strip()
    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Password admin baru (min 12): ")

    if "@" not in email:
        raise SystemExit("Email tidak valid")
    if len(password) < 12:
        raise SystemExit("Password admin minimal 12 karakter")

    async with async_session() as db:
        row = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if row:
            row.nama = nama[:100]
            row.no_hp = no_hp[:20]
            row.password = hash_password(password)
            row.role = "ADMIN"
            action = "rotated"
        else:
            row = User(
                nama=nama[:100],
                email=email,
                no_hp=no_hp[:20],
                password=hash_password(password),
                role="ADMIN",
            )
            db.add(row)
            action = "created"
        await db.commit()
        await db.refresh(row)
        print(f"ADMIN {action.upper()}: {row.email} ({row.id})")


if __name__ == "__main__":
    asyncio.run(main())
