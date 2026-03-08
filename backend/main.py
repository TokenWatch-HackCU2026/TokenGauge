import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import connect_db, disconnect_db
from routers import auth, usage, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await disconnect_db()


app = FastAPI(title="TokenGauge API", lifespan=lifespan)

allowed_origins = [
    "http://localhost:5173",
    "https://tokengauge.onrender.com",
]
if os.getenv("FRONTEND_URL") and os.getenv("FRONTEND_URL") not in allowed_origins:
    allowed_origins.append(os.getenv("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(usage.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "queue-push-v1"}
