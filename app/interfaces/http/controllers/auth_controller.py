"""Autenticação por CPF.

Em produção o token é emitido pela Lambda `autogiro-auth` e validado pelo Kong antes
de a requisição chegar aqui. Este controller expõe o mesmo contrato dentro da API para
execução local e para os testes de integração — o token produzido é intercambiável com
o da Lambda, já que ambos usam o segredo HS256 compartilhado e a mesma claim `iss`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.authenticate_by_document import AuthenticateByDocumentUseCase
from app.domain.entities.client import Client
from app.infrastructure.config import settings
from app.infrastructure.database import get_db
from app.infrastructure.persistence.repositories.client_repository import (
    SqlAlchemyClientRepository,
)
from app.infrastructure.security.security import TokenIssuer
from app.interfaces.http.dependencies import get_current_client
from app.interfaces.http.schemas.auth_schema import (
    AuthByDocumentRequest,
    AuthenticatedClientResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Autentica o cliente por CPF e devolve um JWT",
    responses={401: {"description": "CPF inválido ou cliente não cadastrado"}},
)
async def issue_token(data: AuthByDocumentRequest, db: AsyncSession = Depends(get_db)):
    """Valida o CPF, confirma o cliente na base e emite o token de acesso."""
    use_case = AuthenticateByDocumentUseCase(SqlAlchemyClientRepository(db), TokenIssuer())
    token, _client = await use_case.execute(data.cpf)
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=AuthenticatedClientResponse,
    summary="Cliente identificado pelo token",
)
async def me(current_client: Client = Depends(get_current_client)):
    return current_client
