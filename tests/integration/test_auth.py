"""Autenticação por CPF — o fluxo exigido na Fase 3.

O token é emitido a partir do CPF de um cliente já cadastrado, o mesmo contrato da
Lambda `autogiro-auth`. Não existe mais login com usuário e senha.
"""

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.config import settings
from app.infrastructure.persistence.models.client_model import Client as ClientModel

CPF_VALIDO = "529.982.247-25"
CPF_DIGITOS = "52998224725"
# Dígitos verificadores incorretos.
CPF_INVALIDO = "529.982.247-99"


async def _cadastrar_cliente(db: AsyncSession, cpf_digits: str = CPF_DIGITOS) -> None:
    """Semeia o cliente na base: a autenticação consulta, não cadastra."""
    db.add(ClientModel(name="Maria Oliveira", cpf_cnpj=cpf_digits))
    await db.commit()


@pytest.mark.asyncio
async def test_emite_token_para_cpf_de_cliente_cadastrado(client: AsyncClient, db: AsyncSession):
    await _cadastrar_cliente(db)

    r = await client.post("/api/v1/auth/token", json={"cpf": CPF_VALIDO})

    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert body["access_token"]


@pytest.mark.asyncio
async def test_token_carrega_o_cpf_no_sub_e_o_emissor_no_iss(
    client: AsyncClient, db: AsyncSession
):
    """O contrato com o Kong: `sub` identifica o cliente, `iss` escolhe o segredo."""
    await _cadastrar_cliente(db)

    r = await client.post("/api/v1/auth/token", json={"cpf": CPF_VALIDO})
    payload = jwt.decode(
        r.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )

    assert payload["sub"] == CPF_DIGITOS
    assert payload["iss"] == settings.JWT_ISSUER


@pytest.mark.asyncio
async def test_aceita_cpf_com_e_sem_mascara(client: AsyncClient, db: AsyncSession):
    await _cadastrar_cliente(db)

    com_mascara = await client.post("/api/v1/auth/token", json={"cpf": CPF_VALIDO})
    sem_mascara = await client.post("/api/v1/auth/token", json={"cpf": CPF_DIGITOS})

    assert com_mascara.status_code == 200
    assert sem_mascara.status_code == 200


@pytest.mark.asyncio
async def test_cpf_com_digito_verificador_invalido_retorna_401(
    client: AsyncClient, db: AsyncSession
):
    await _cadastrar_cliente(db)

    r = await client.post("/api/v1/auth/token", json={"cpf": CPF_INVALIDO})

    assert r.status_code == 401


@pytest.mark.asyncio
async def test_cpf_valido_de_cliente_nao_cadastrado_retorna_401(client: AsyncClient):
    """Sem revelar a diferença: CPF inexistente responde igual a CPF inválido."""
    r = await client.post("/api/v1/auth/token", json={"cpf": CPF_VALIDO})

    assert r.status_code == 401


@pytest.mark.asyncio
async def test_cpf_de_digitos_repetidos_retorna_401(client: AsyncClient):
    r = await client.post("/api/v1/auth/token", json={"cpf": "111.111.111-11"})

    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_devolve_o_cliente_do_token(client: AsyncClient, db: AsyncSession):
    await _cadastrar_cliente(db)
    r = await client.post("/api/v1/auth/token", json={"cpf": CPF_VALIDO})
    client.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})

    r = await client.get("/api/v1/auth/me")

    assert r.status_code == 200
    body = r.json()
    assert body["cpf_cnpj"] == CPF_DIGITOS
    assert body["name"] == "Maria Oliveira"


@pytest.mark.asyncio
async def test_me_sem_token_retorna_401(client: AsyncClient):
    r = await client.get("/api/v1/auth/me")

    assert r.status_code == 401


@pytest.mark.asyncio
async def test_token_invalido_retorna_401(client: AsyncClient):
    client.headers.update({"Authorization": "Bearer token.invalido.aqui"})

    r = await client.get("/api/v1/auth/me")

    assert r.status_code == 401


@pytest.mark.asyncio
async def test_token_assinado_com_outro_segredo_retorna_401(
    client: AsyncClient, db: AsyncSession
):
    """Um token bem formado mas assinado com outra chave não passa."""
    await _cadastrar_cliente(db)
    forjado = jwt.encode(
        {"sub": CPF_DIGITOS, "iss": settings.JWT_ISSUER}, "outro-segredo", algorithm="HS256"
    )
    client.headers.update({"Authorization": f"Bearer {forjado}"})

    r = await client.get("/api/v1/auth/me")

    assert r.status_code == 401


@pytest.mark.asyncio
async def test_token_de_cliente_removido_da_base_retorna_401(
    client: AsyncClient, db: AsyncSession
):
    """Assinatura íntegra, mas o cliente não existe mais: acesso negado."""
    forjado = jwt.encode(
        {"sub": CPF_DIGITOS, "iss": settings.JWT_ISSUER},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    client.headers.update({"Authorization": f"Bearer {forjado}"})

    r = await client.get("/api/v1/auth/me")

    assert r.status_code == 401


@pytest.mark.asyncio
async def test_rota_de_negocio_exige_token(client: AsyncClient):
    """As rotas protegidas continuam fechadas sem autenticação."""
    r = await client.get("/api/v1/service-orders")

    assert r.status_code == 401
