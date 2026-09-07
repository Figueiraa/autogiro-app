"""Dependências de autenticação das rotas protegidas.

O fluxo da Fase 3 é: a Lambda `autogiro-auth` valida o CPF, confirma que o cliente
existe na base e assina um JWT com `sub = CPF`; o Kong valida a assinatura pela claim
`iss` antes de rotear; a API resolve o cliente pelo `sub`.

Nenhum dos três conhece os outros — o contrato é o segredo HS256 compartilhado. Por
isso a API revalida a assinatura em vez de confiar cegamente no gateway: em execução
local (Docker Compose, testes) não há Kong na frente.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.client import Client
from app.infrastructure.database import get_db
from app.infrastructure.persistence.repositories.client_repository import (
    SqlAlchemyClientRepository,
)
from app.infrastructure.security.security import decode_access_token

# HTTPBearer em vez de OAuth2PasswordBearer: não existe mais endpoint de login com
# usuário e senha — o token é emitido pela Lambda a partir do CPF.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT emitido por autogiro-auth")

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token inválido ou expirado",
    headers={"WWW-Authenticate": "Bearer"},
)


def _only_digits(value: str) -> str:
    """Normaliza o documento: a base armazena CPF/CNPJ apenas com dígitos."""
    return "".join(character for character in value if character.isdigit())


async def get_current_client(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Client:
    """Resolve o cliente autenticado a partir do CPF/CNPJ carregado no `sub`."""
    if credentials is None:
        raise _CREDENTIALS_ERROR

    document = decode_access_token(credentials.credentials)
    if not document:
        raise _CREDENTIALS_ERROR

    repository = SqlAlchemyClientRepository(db)
    client = await repository.get_by_cpf_cnpj(_only_digits(document))
    if client is None:
        # Assinatura válida, mas o cliente não existe mais na base: o token continua
        # criptograficamente íntegro, então a resposta é 401 e não 404.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cliente não encontrado para o documento do token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return client


# Nome mantido para não alterar as dezenas de rotas que apenas exigem um token válido
# (`_=Depends(get_current_user)`). O que muda é o sujeito autenticado: agora é o
# cliente identificado por CPF, não mais um usuário com senha.
get_current_user = get_current_client
