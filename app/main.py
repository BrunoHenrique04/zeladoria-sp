from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app import regras
from app.config import APP_VERSION
from app.database import Base, engine
from app.routes import ocorrencias
from app.schemas import CategoriaSaida


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Zeladoria SP",
    version=APP_VERSION,
    description=(
        "API de ocorrências urbanas da cidade de São Paulo. "
        "Inspirada no projeto open source CivicLens (licença MIT)."
    ),
    lifespan=lifespan,
)
app.include_router(ocorrencias.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
    except Exception as erro:  # o motivo exato vai para o log do container
        raise HTTPException(503, "banco de dados indisponível") from erro
    return {"status": "ok", "versao": APP_VERSION}


@app.get("/categorias", response_model=list[CategoriaSaida], tags=["catálogo"])
def listar_categorias() -> list[CategoriaSaida]:
    return [CategoriaSaida(**vars(c)) for c in regras.CATEGORIAS.values()]


@app.get("/subprefeituras", tags=["catálogo"])
def listar_subprefeituras() -> list[str]:
    return sorted(regras.SUBPREFEITURAS)
