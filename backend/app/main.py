"""
Ponto de entrada do backend FastAPI.

Execute em desenvolvimento:
    uvicorn app.main:app --reload

Em produção, usar systemd + uvicorn (ver docs/SETUP_UBUNTU.md).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, auth, health, relatorio_livre, relatorios


settings = get_settings()

app = FastAPI(
    title="Extrator Protheus — API",
    description="API do Extrator Protheus. Autenticação via cookie httpOnly.",
    version="0.1.0",
)

# CORS em desenvolvimento: libera o Vite (porta 5173).
# Em produção (quando o FastAPI servir o build estático do React), cors_origins
# fica vazio e nenhum origin extra é permitido.
if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,  # necessário pra cookies
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(relatorios.router)
app.include_router(relatorio_livre.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"app": "Extrator Protheus", "versao": "0.1.0", "docs": "/docs"}
