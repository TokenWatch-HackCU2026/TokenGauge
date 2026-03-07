from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine
import models
from routers import auth, usage

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TokenWatch API")

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
def health():
    return {"status": "ok"}
