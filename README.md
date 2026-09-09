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
| Testes | pytest · **226 testes, 96% de cobertura** (gate mínimo: 90%) |
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

As rotas sob `/api/v1` exigem um JWT emitido pelo [autogiro-auth](https://github.com/Figueiraa/autogiro-auth) mediante CPF.
O Kong valida a assinatura antes de rotear; a aplicação lê o CPF da claim `sub` e resolve o cliente.

```bash
# 1. Obter o token (Lambda)
TOKEN=$(curl -sX POST "$AUTH_ENDPOINT"   -H 'Content-Type: application/json'   -d '{"cpf": "529.982.247-25"}' | jq -r .access_token)

# 2. Consumir a API protegida (via Kong)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/service-orders
```

### Sem a Lambda (execução local)

A API expõe o mesmo contrato em `POST /api/v1/auth/token`, para rodar e demonstrar o
sistema sem depender da AWS. O token produzido é **intercambiável** com o da Lambda:
ambos usam o segredo HS256 compartilhado e a mesma claim `iss`.

```bash
TOKEN=$(curl -sX POST http://localhost:8000/api/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"cpf": "529.982.247-25"}' | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me
```

> O cliente precisa estar cadastrado: a autenticação **consulta** a base, não cadastra.
> CPF inválido e CPF não cadastrado respondem igual (401), para não revelar quais
> documentos existem na oficina.

| Rota | Método | Descrição |
|---|---|---|
| `/api/v1/auth/token` | POST | Emite o JWT a partir do CPF |
| `/api/v1/auth/me` | GET | Devolve o cliente identificado pelo token |

## Executando localmente

### Com Docker Compose (recomendado)

```bash
cp .env.example .env
docker compose up --build
```

A API sobe em http://localhost:8000 com um PostgreSQL local.

### Sem Docker

```bash
python -m venv venv && source venv/Scripts/activate   # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # usa SQLite por padrão
uvicorn app.main:app --reload
```

### Testes

```bash
pytest                      # 226 testes, gate de cobertura de 90%
ruff check app tests        # lint
bandit -r app -ll           # análise de segurança
```

## Deploy

O deploy é automático pela pipeline: `develop` publica em homologação e `main` em produção.
Manualmente:

```bash
# O cluster é EKS: a imagem precisa estar num registry que os nós alcancem.
docker build -t ghcr.io/figueiraa/autogiro-app:local .
docker push ghcr.io/figueiraa/autogiro-app:local

kubectl -n autogiro set image deployment/autogiro-api \
  api=ghcr.io/figueiraa/autogiro-app:local
kubectl -n autogiro rollout status deployment/autogiro-api
```

> Na primeira instalação, antes de existir o Deployment, use `kubectl apply -k k8s/` —
> lembrando que o Secret vem dos secrets do GitHub Actions, não do `k8s/secret.yaml`
> versionado (que só documenta o formato).

> Pré-requisitos: cluster provisionado por [autogiro-infra-k8s](https://github.com/Figueiraa/autogiro-infra-k8s) e banco por
> [autogiro-infra-db](https://github.com/Figueiraa/autogiro-infra-db).

## Documentação da API

| Recurso | URL |
|---|---|
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| OpenAPI JSON | `http://localhost:8000/openapi.json` |
| Coleção Postman | [`docs/autogiro.postman_collection.json`](docs/autogiro.postman_collection.json) |

## Documentação da arquitetura

Índice completo em [`docs/arquitetura/`](docs/arquitetura/README.md).

| Tipo | Documentos |
|---|---|
| Diagramas | [componentes](docs/arquitetura/diagramas/01-componentes.md) · [sequência da autenticação](docs/arquitetura/diagramas/02-sequencia-autenticacao.md) · [sequência da abertura de OS](docs/arquitetura/diagramas/03-sequencia-abertura-de-os.md) |
| RFCs | [001 nuvem](docs/arquitetura/rfcs/RFC-001-escolha-da-nuvem.md) · [002 banco](docs/arquitetura/rfcs/RFC-002-escolha-do-banco.md) · [003 autenticação](docs/arquitetura/rfcs/RFC-003-estrategia-de-autenticacao.md) |
| ADRs | [001 REST](docs/arquitetura/adrs/ADR-001-comunicacao-rest-sincrona.md) · [002 HPA](docs/arquitetura/adrs/ADR-002-hpa-escalabilidade.md) · [003 repositórios](docs/arquitetura/adrs/ADR-003-quatro-repositorios.md) · [004 emissor/validador](docs/arquitetura/adrs/ADR-004-emissor-desacoplado-do-validador.md) |

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

### Stack local (Docker Compose)

O `docker compose up` sobe também Prometheus e Grafana, com dashboards e alertas
provisionados automaticamente a partir de [`monitoring/`](monitoring/):

| Serviço | URL | Credenciais |
|---|---|---|
| Grafana | http://localhost:3000 | `admin` / `admin` |
| Prometheus | http://localhost:9090 | — |

**Dashboard `AutoGiro API — Observabilidade`** (15 painéis): saúde e SLO pelo método RED,
latência p50/p95/p99 por endpoint, e os indicadores de negócio da oficina — OS abertas
em 24h, orçamentos aprovados e recusados, transições de status e falhas de notificação.

**6 regras de alerta** em [`monitoring/prometheus/rules/alerts.yml`](monitoring/prometheus/rules/alerts.yml):
API indisponível, taxa de erro 5xx acima de 5%, latência p95 fora do SLO, exceções não
tratadas, falha no envio de notificações e ausência de OS em horário comercial.

## Identificadores

Namespace `autogiro` · Deployment `autogiro-api` · Imagem `ghcr.io/figueiraa/autogiro-app`
