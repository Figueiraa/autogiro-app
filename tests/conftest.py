import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.database import Base, get_db
from app.infrastructure.persistence.models.client_model import Client as ClientModel
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def pytest_collection_modifyitems(items):
    """Marca automaticamente cada teste conforme a pasta (`unit` ou `integration`).

    Permite rodar uma suíte específica: `pytest -m unit` / `pytest -m integration`.
    """
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="function")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(loop_scope="function")
async def db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="function")
async def client(db: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# CPF válido pelos dígitos verificadores, usado como o cliente já autenticado.
# Deliberadamente diferente do CPF dos casos de teste (529.982.247-25), para que
# cadastrar um cliente novo não colida com este por duplicidade.
AUTH_CPF = "111.444.777-35"
AUTH_CPF_DIGITS = "11144477735"


@pytest_asyncio.fixture(loop_scope="function")
async def auth_client(db: AsyncSession):
    """Cliente HTTP autenticado pelo fluxo da Fase 3: token emitido a partir do CPF.

    O cliente é semeado direto na base porque em produção ele já existe quando a
    Lambda `autogiro-auth` é chamada — ela consulta, não cadastra. A autenticação em
    si passa pela rota real (`POST /auth/token`), então os testes exercitam o mesmo
    caminho de emissão e validação de token usado em produção.
    """
    app.dependency_overrides[get_db] = lambda: db

    db.add(ClientModel(name="Cliente de Teste", cpf_cnpj=AUTH_CPF_DIGITS))
    await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/v1/auth/token", json={"cpf": AUTH_CPF})
        token = resp.json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c
    app.dependency_overrides.clear()
