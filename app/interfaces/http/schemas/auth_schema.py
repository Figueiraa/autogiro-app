from pydantic import BaseModel, Field


class AuthByDocumentRequest(BaseModel):
    """Entrada da autenticação por CPF, no mesmo contrato da Lambda `autogiro-auth`."""

    cpf: str = Field(
        ...,
        description="CPF do cliente, com ou sem máscara.",
        examples=["529.982.247-25"],
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int | None = Field(
        default=None, description="Validade do token em segundos."
    )


class AuthenticatedClientResponse(BaseModel):
    """Cliente identificado pelo token — o `sub` carrega o CPF/CNPJ."""

    id: int
    name: str
    cpf_cnpj: str
    email: str | None = None
    phone: str | None = None

    model_config = {"from_attributes": True}
