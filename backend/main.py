import sys
from pathlib import Path

# Add root folder so we can import 'redis' module
sys.path.append(str(Path(__file__).resolve().parent.parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import connect_db, disconnect_db
from routers import auth, usage

from redis.client import connect_redis, disconnect_redis, redis_health_check


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await connect_redis()
    yield
    await disconnect_redis()
    await disconnect_db()


app = FastAPI(title="TokenWatch API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(usage.router)


@app.get("/health")
async def health():
    result = {"status": "ok"}
    result.update(await redis_health_check())
    return result
