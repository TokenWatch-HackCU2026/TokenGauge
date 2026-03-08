import asyncio
import logging
import os

import motor.motor_asyncio
from beanie import init_beanie
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

import certifi

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "tokengauge")

_client: motor.motor_asyncio.AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global _client

    from models import User, ApiCall, Alert, SpikeEvent

    retries = 5
    for attempt in range(retries):
        try:
            client_kwargs: dict = {
                "serverSelectionTimeoutMS": 5000,
            }
            # Only use TLS CA file for Atlas (SRV) connections
            if MONGO_URI.startswith("mongodb+srv"):
                client_kwargs["tlsCAFile"] = certifi.where()
            _client = motor.motor_asyncio.AsyncIOMotorClient(
                MONGO_URI,
                **client_kwargs,
            )
            await _client.admin.command("ping")
            await init_beanie(
                database=_client[DB_NAME],
                document_models=[User, ApiCall, Alert, SpikeEvent],
            )
            logger.info("Connected to MongoDB (%s / %s)", MONGO_URI, DB_NAME)
            return
        except Exception as exc:
            logger.warning(
                "MongoDB connection attempt %d/%d failed: %s", attempt + 1, retries, exc
            )
            if attempt < retries - 1:
                await asyncio.sleep(2**attempt)

    raise RuntimeError("Could not connect to MongoDB after %d attempts" % retries)


def get_db():
    if _client is None:
        raise RuntimeError("Database not connected")
    return _client[DB_NAME]


async def disconnect_db() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("Disconnected from MongoDB")
