from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .api.deps import init_db
from .api import auth, users, features, news

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(features.router)
app.include_router(news.router)

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/")
def root():
    return {"ok": True, "name": settings.app_name}
