import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_liveness(client: AsyncClient):
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness_checks_database(client: AsyncClient):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "database": "connected"}


@pytest.mark.asyncio
async def test_request_id_header_is_returned(client: AsyncClient):
    r = await client.get("/health")
    assert r.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_request_id_is_propagated(client: AsyncClient):
    r = await client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert r.headers.get("X-Request-ID") == "trace-123"


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    r = await client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Content-Security-Policy") == "default-src 'self'"


@pytest.mark.asyncio
async def test_api_is_versioned(client: AsyncClient):
    # Sem o prefixo de versão, a rota não existe.
    assert (await client.get("/clients")).status_code == 404
    # Com o prefixo, exige autenticação (401), provando que a rota vive sob /api/v1.
    assert (await client.get("/api/v1/clients")).status_code == 401


@pytest.mark.asyncio
async def test_emite_log_de_acesso_correlacionado(client: AsyncClient, caplog):
    """Cada requisição gera uma linha de log carregando o request_id.

    Sem isso o id existiria só no header da resposta, e não haveria como seguir
    o rastro de uma requisição bem-sucedida entre as réplicas.
    """
    import logging

    with caplog.at_level(logging.INFO, logger="autogiro.access"):
        await client.get("/health", headers={"X-Request-ID": "correlacao-xyz"})

    registros = [r for r in caplog.records if r.name == "autogiro.access"]
    assert registros, "nenhum log de acesso foi emitido"
    assert getattr(registros[-1], "request_id", None) == "correlacao-xyz"


@pytest.mark.asyncio
async def test_o_endpoint_de_metricas_nao_gera_log_de_acesso(
    client: AsyncClient, caplog
):
    """O scrape do Prometheus é de alta frequência e inundaria o log."""
    import logging

    with caplog.at_level(logging.INFO, logger="autogiro.access"):
        await client.get("/metrics")

    assert not [r for r in caplog.records if r.name == "autogiro.access"]
