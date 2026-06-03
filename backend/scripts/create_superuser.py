#!/usr/bin/env python
"""
Bootstrap the first superuser. Run once at setup:
    python scripts/create_superuser.py
"""
import asyncio
import getpass
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.analytics import init_db, AsyncSessionLocal, User
from services.auth_service import hash_password
from sqlalchemy import select


async def main():
    await init_db()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.is_superuser == True))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"A superuser already exists: {existing.email}")
            print("To add more users, log in as superuser and use the admin UI.")
            return

        print("=== Create Superuser ===")
        email = input("Email: ").strip()
        name = input("Name: ").strip()
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")

        if password != confirm:
            print("Passwords do not match.")
            sys.exit(1)
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            sys.exit(1)

        user = User(
            email=email,
            name=name,
            password_hash=hash_password(password),
            is_active=True,
            is_superuser=True,
            force_password_change=False,
        )
        session.add(user)
        await session.commit()
        print(f"\nSuperuser created: {email}")
        print("You can now log in and configure the business via the admin UI.")
        print("For ChangePay, run: python scripts/seed_changepay_config.py")


if __name__ == "__main__":
    asyncio.run(main())
