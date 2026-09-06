# autogiro-app

> **AutoGiro** · Repositório 4 de 4 — Tech Challenge Fase 3 (13SOAT)

API principal do AutoGiro — plataforma de gestão para redes de oficinas mecânicas.
FastAPI com Clean Architecture, executando em Kubernetes atrás do Kong Gateway.

## Propósito

Gerencia clientes, veículos, peças, tipos de serviço e o ciclo de vida das ordens de serviço
(Recebida → Diagnóstico → Aprovação → Execução → Finalizada → Entregue), publicando métricas,
logs estruturados e traces para a stack de observabilidade.

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11 |
| Framework | FastAPI |
| ORM | SQLAlchemy 2 (assíncrono, asyncpg) |
| Banco | PostgreSQL 17 — [Neon](https://neon.com) gerenciado |
| Testes | pytest · cobertura mínima de 90% |
| Qualidade | ruff · bandit · trivy |
| Container | Docker (multi-stage, usuário não-root) |
| Orquestração | Kubernetes · HPA · Probes |
| Observabilidade | New Relic (APM) · Prometheus (`/metrics`) |
| CI/CD | GitHub Actions · GHCR |

## Arquitetura

```
                       ┌──────────────────┐
   Cliente ──JWT──────►│  Kong Gateway    │ valida a assinatura do token
                       │  plugin `jwt`    │
                       └────────┬─────────┘
                                │ /api/v1/*
                                ▼
        ┌───────────────────────────────────────────┐
        │  autogiro-api (Deployment, 2..10 réplicas)│
        │                                           │
        │  interfaces/  controllers, schemas, deps  │  ← HTTP
        │  application/ use cases, ports, DTOs      │  ← regras de aplicação
        │  domain/      entidades, VOs, exceções    │  ← regras de negócio
        │  infrastructure/ repos, ORM, segurança    │  ← detalhes técnicos
        └───────────────────┬───────────────────────┘
                            │ asyncpg
                            ▼
                   Neon PostgreSQL (gerenciado)
```

A dependência aponta sempre para dentro: `domain` não conhece ninguém; `application` define ports
que `infrastructure` implementa. Detalhe de framework ou de banco não vaza para as regras de negócio.

## Autenticação

As rotas sob `/api/v1` exigem um JWT emitido pelo [autogiro-auth](../autogiro-auth/) mediante CPF.
O Kong valida a assinatura antes de rotear; a aplicação lê o CPF da claim `sub` e resolve o cliente.

```bash
# 1. Obter o token (Lambda)
TOKEN=$(curl -sX POST "$AUTH_ENDPOINT"   -H 'Content-Type: application/json'   -d '{"cpf": "529.982.247-25"}' | jq -r .access_token)

# 2. Consumir a API protegida (via Kong)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/service-orders
```

## Executando localmente

### Com Docker Compose (recomendado)

```bash
cp .env.example .env
docker compose up --build
```

A API sobe em http://localhost:8000 com um PostgreSQL local.

### Sem Docker

```bash
python -m venv venv && source venv/Scripts/activate   # Windows: venv\Scriptsctivate
pip install -r requirements.txt
cp .env.example .env                                   # usa SQLite por padrão
uvicorn app.main:app --reload
```

### Testes

```bash
pytest                      # suíte completa com gate de cobertura de 90%
ruff check app tests        # lint
bandit -r app -ll           # análise de segurança
```

## Deploy

O deploy é automático pela pipeline: `develop` publica em homologação e `main` em produção.
Manualmente:

```bash
docker build -t autogiro-app:latest .
kind load docker-image autogiro-app:latest --name autogiro
kubectl apply -k k8s/
kubectl -n autogiro rollout status deployment/autogiro-api
```

> Pré-requisitos: cluster provisionado por [autogiro-infra-k8s](../autogiro-infra-k8s/) e banco por
> [autogiro-infra-db](../autogiro-infra-db/).

## Documentação da API

| Recurso | URL |
|---|---|
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| OpenAPI JSON | `http://localhost:8000/openapi.json` |
| Coleção Postman | [`docs/autogiro.postman_collection.json`](docs/autogiro.postman_collection.json) |

## Observabilidade

| Endpoint | Finalidade |
|---|---|
| `GET /health` | Health check simples |
| `GET /health/live` | Liveness probe |
| `GET /health/ready` | Readiness probe (verifica o banco) |
| `GET /metrics` | Métricas no formato Prometheus |

Métricas de negócio expostas: `autogiro_service_orders_opened_total`,
`autogiro_service_order_status_transitions_total`, `autogiro_budget_approvals_total`,
`autogiro_notifications_total`.

## Identificadores

Namespace `autogiro` · Deployment `autogiro-api` · Imagem `ghcr.io/figueiraa/autogiro-app`
