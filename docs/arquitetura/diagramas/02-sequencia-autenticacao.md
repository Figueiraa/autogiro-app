# Diagrama de Sequência — Autenticação por CPF

Fluxo exigido pelo enunciado: validar o CPF, consultar o cliente na base, devolver um JWT
e usá-lo para consumir uma rota protegida.

## Caminho de sucesso

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant L as autogiro-auth<br/>(AWS Lambda)
    participant DB as Neon<br/>PostgreSQL
    participant K as Kong Gateway<br/>(plugin jwt)
    participant A as autogiro-api<br/>(FastAPI)

    C->>L: POST Function URL<br/>{"cpf": "529.982.247-25"}

    Note over L: cpf.is_valid()<br/>normaliza e confere os dois<br/>dígitos verificadores (módulo 11)

    L->>DB: SELECT id, name, cpf_cnpj<br/>FROM clients<br/>WHERE cpf_cnpj = $1
    DB-->>L: cliente encontrado

    Note over L: _issue_token()<br/>sub = CPF · client_id · name<br/>iat · exp · iss = "autogiro-auth"<br/>assina HS256 com JWT_SECRET

    L-->>C: 200 {"access_token": "...",<br/>"expires_in": 3600}

    C->>K: GET /api/v1/service-orders<br/>Authorization: Bearer <token>

    Note over K: lê a claim iss do token<br/>procura a credencial cuja key = iss<br/>verifica a assinatura com o secret<br/>confere exp (claims_to_verify)

    K->>A: encaminha a requisição

    Note over A: get_current_client()<br/>revalida a assinatura<br/>(não há Kong em execução local)

    A->>DB: SELECT ... FROM clients<br/>WHERE cpf_cnpj = $1
    DB-->>A: cliente
    A-->>C: 200 lista de ordens de serviço
```

## Caminhos de erro

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant L as autogiro-auth
    participant DB as Neon
    participant K as Kong
    participant A as autogiro-api

    rect rgb(255, 235, 238)
        Note over C,DB: CPF com dígito verificador inválido
        C->>L: POST {"cpf": "529.982.247-99"}
        L-->>C: 401 (não consulta o banco)
    end

    rect rgb(255, 235, 238)
        Note over C,DB: CPF válido, cliente não cadastrado
        C->>L: POST {"cpf": "111.444.777-35"}
        L->>DB: SELECT ... WHERE cpf_cnpj = $1
        DB-->>L: nenhuma linha
        L-->>C: 401 — mesma resposta do caso anterior
    end

    rect rgb(255, 243, 224)
        Note over C,K: Token ausente, expirado ou mal assinado
        C->>K: GET /api/v1/service-orders (sem Bearer)
        K-->>C: 401 — a requisição não chega à API
    end

    rect rgb(255, 243, 224)
        Note over C,A: Assinatura íntegra, cliente removido da base
        C->>K: GET /api/v1/... Bearer <token válido>
        K->>A: encaminha (assinatura confere)
        A->>DB: SELECT ... WHERE cpf_cnpj = $1
        DB-->>A: nenhuma linha
        A-->>C: 401 — token válido, sujeito inexistente
    end
```

### Por que CPF inválido e CPF não cadastrado respondem igual

Se o CPF malformado retornasse `400` e o não cadastrado `404`, qualquer pessoa poderia
descobrir **quais CPFs são clientes da oficina** testando documentos válidos e observando a
diferença. Como o CPF é um dado pessoal, os dois casos devolvem `401` sem distinção.

O mesmo raciocínio se aplica ao quarto caso: uma assinatura válida cujo sujeito não existe
mais recebe `401`, e não `404` — o problema é de autenticação, não de recurso ausente.

## Execução sem a AWS

A API expõe `POST /api/v1/auth/token` com o mesmo contrato da Lambda, para rodar e demonstrar
o sistema localmente (Docker Compose, testes de integração). O token produzido é
**intercambiável**: mesmo segredo HS256, mesma claim `iss`.

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant A as autogiro-api
    participant DB as PostgreSQL

    C->>A: POST /api/v1/auth/token<br/>{"cpf": "529.982.247-25"}
    Note over A: AuthenticateByDocumentUseCase<br/>mesma validação, mesmo payload
    A->>DB: SELECT ... WHERE cpf_cnpj = $1
    DB-->>A: cliente
    A-->>C: 200 {"access_token": "..."}
```

Isso foi verificado na prática: um token gerado pelo código da Lambda foi aceito pela API,
que resolveu o cliente pelo CPF e liberou a rota protegida.

## Referências de código

| Etapa | Arquivo |
|---|---|
| Validação do CPF (Lambda) | [`autogiro-auth/src/cpf.py`](../../../../autogiro-auth/src/cpf.py) |
| Emissão do token | [`autogiro-auth/src/handler.py`](../../../../autogiro-auth/src/handler.py) |
| Consumer e plugin do Kong | [`autogiro-infra-k8s/terraform/kong-jwt.tf`](../../../../autogiro-infra-k8s/terraform/kong-jwt.tf) |
| Resolução do cliente na API | [`app/interfaces/http/dependencies.py`](../../../app/interfaces/http/dependencies.py) |
| Validação do CPF (domínio da API) | [`app/domain/value_objects/cpf.py`](../../../app/domain/value_objects/cpf.py) |

Decisão completa em [ADR-004](../adrs/ADR-004-emissor-desacoplado-do-validador.md) e
[RFC-003](../rfcs/RFC-003-estrategia-de-autenticacao.md).
