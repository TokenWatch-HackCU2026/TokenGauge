"""
Seed script for local development.
Creates a test org and test user if they don't already exist.

Usage:
    python seed.py
"""
import asyncio

from passlib.context import CryptContext

from database import connect_db, disconnect_db
from models import Org, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TEST_EMAIL = "test@tokenwatch.dev"
TEST_PASSWORD = "password123"
ORG_NAME = "Test Org"


async def seed() -> None:
    await connect_db()

    # Org
    org = await Org.find_one(Org.name == ORG_NAME)
    if not org:
        from beanie import PydanticObjectId
        org = Org(name=ORG_NAME, plan="free", owner_id=PydanticObjectId())
        await org.insert()
        print(f"[seed] Created org '{ORG_NAME}' -> {org.id}")
    else:
        print(f"[seed] Org already exists -> {org.id}")

    # User
    user = await User.find_one(User.email == TEST_EMAIL)
    if not user:
        user = User(
            email=TEST_EMAIL,
            password_hash=pwd_context.hash(TEST_PASSWORD),
            org_id=org.id,
        )
        await user.insert()
        org.owner_id = user.id
        await org.save()
        print(f"[seed] Created user '{TEST_EMAIL}' (password: {TEST_PASSWORD}) -> {user.id}")
    else:
        print(f"[seed] User already exists -> {user.id}")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(seed())
