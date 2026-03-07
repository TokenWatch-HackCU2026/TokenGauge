"""
Seed script for local development.
Creates a test user if it doesn't already exist.

Usage:
    python seed.py
"""
import asyncio

from auth import hash_password
from database import connect_db, disconnect_db
from models import User

TEST_EMAIL = "test@tokenwatch.dev"
TEST_PASSWORD = "password123"


async def seed() -> None:
    await connect_db()

    user = await User.find_one(User.email == TEST_EMAIL)
    if not user:
        user = User(
            email=TEST_EMAIL,
            password_hash=hash_password(TEST_PASSWORD),
            full_name="Test User",
        )
        await user.insert()
        print(f"[seed] Created user '{TEST_EMAIL}' (password: {TEST_PASSWORD}) -> {user.id}")
    else:
        print(f"[seed] User already exists -> {user.id}")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(seed())
