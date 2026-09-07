"""Autenticação do cliente por CPF.

Espelha o comportamento da Lambda `autogiro-auth`: valida o documento, confirma que o
cliente existe na base e emite o JWT. Existe na API para que o sistema seja
demonstrável e testável sem depender da AWS (Docker Compose, testes de integração),
mantendo um único contrato de token.
"""

from app.application.ports.client_repository import ClientRepositoryPort
from app.application.ports.security import TokenIssuerPort
from app.domain.entities.client import Client
from app.domain.exceptions.domain_exceptions import UnauthorizedError
from app.domain.value_objects import cpf as cpf_rules


class AuthenticateByDocumentUseCase:
    def __init__(self, repository: ClientRepositoryPort, token_issuer: TokenIssuerPort):
        self._repo = repository
        self._tokens = token_issuer

    async def execute(self, document: str) -> tuple[str, Client]:
        """Devolve o token e o cliente autenticado.

        Levanta `UnauthorizedError` tanto para CPF malformado quanto para cliente
        inexistente: distinguir os dois casos permitiria descobrir quais CPFs estão
        cadastrados na oficina.
        """
        if not cpf_rules.is_valid(document):
            raise UnauthorizedError()

        client = await self._repo.get_by_cpf_cnpj(cpf_rules.normalize(document))
        if client is None:
            raise UnauthorizedError()

        return self._tokens.create_access_token(client.cpf_cnpj), client
