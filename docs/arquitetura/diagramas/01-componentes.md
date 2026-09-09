# Diagrama de Componentes — AutoGiro

Visão de nuvem, APIs, banco e monitoramento, conforme exigido na documentação
arquitetural da Fase 3.

## Visão geral

```mermaid
flowchart TB
    subgraph cliente["Cliente"]
        APP["Aplicação cliente<br/>(Postman / front-end)"]
    end

    subgraph aws["AWS · free tier permanente"]
        LAMBDA["autogiro-auth<br/>AWS Lambda · Python 3.11 · arm64<br/>Function URL pública"]
        CW["CloudWatch Logs<br/>retenção 7 dias"]
    end

    subgraph kind["Cluster Kubernetes · kind local"]
        subgraph nskong["namespace kong"]
            KONG["Kong Gateway OSS<br/>DB-less · plugin jwt<br/>NodePort 30000 (proxy)<br/>NodePort 30001 (admin)"]
        end

        subgraph nsauto["namespace autogiro"]
            API["autogiro-api<br/>FastAPI · Deployment<br/>HPA 2 a 10 réplicas"]
            HPA["HorizontalPodAutoscaler<br/>CPU 70% · memória 80%"]
        end

        subgraph nssys["kube-system"]
            MS["metrics-server<br/>alimenta o HPA"]
        end

        subgraph nsnr["namespace newrelic"]
            NRI["nri-bundle<br/>infra · logs · eventos"]
        end
    end

    subgraph neon["Neon · PostgreSQL gerenciado"]
        DBPROD[("branch prod")]
        DBHOM[("branch homolog")]
    end

    subgraph nrcloud["New Relic · 100 GB/mês"]
        NR["APM · Logs · Dashboards · Alertas"]
    end

    APP -->|"1. POST CPF"| LAMBDA
    LAMBDA -->|"2. consulta clients.cpf_cnpj"| DBPROD
    LAMBDA -->|"3. devolve JWT HS256"| APP
    LAMBDA -.->|logs| CW

    APP -->|"4. Bearer token<br/>/api/v1/*"| KONG
    KONG -->|"5. valida assinatura<br/>via claim iss"| KONG
    KONG -->|"6. roteia"| API

    API --> DBPROD
    API --> DBHOM
    HPA -.->|escala| API
    MS -.->|métricas de uso| HPA

    API -.->|logs JSON + métricas| NRI
    NRI --> NR

    classDef gratuito fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20
    classDef local fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    class aws,neon,nrcloud gratuito
    class kind local
```

## O contrato entre emissor e validador

O ponto arquitetural central: **a Lambda emite o token e o Kong o valida, sem que nenhum
conheça o outro.** O contrato são apenas o segredo HS256 e a claim `iss`.

```mermaid
flowchart LR
    subgraph emissor["Emissor · AWS"]
        L["autogiro-auth<br/>assina com JWT_SECRET<br/>iss = autogiro-auth"]
    end

    subgraph contrato["Contrato"]
        C["segredo HS256 compartilhado<br/>+<br/>claim iss = autogiro-auth"]
    end

    subgraph validador["Validador · cluster"]
        K["KongConsumer autogiro-auth<br/>credencial jwt:<br/>key = autogiro-auth<br/>secret = JWT_SECRET"]
    end

    L -->|"escreve iss no token"| C
    C -->|"key_claim_name = iss<br/>localiza o segredo"| K
```

Ver [ADR-004](../adrs/ADR-004-emissor-desacoplado-do-validador.md) para a decisão completa.

## Componentes e responsabilidades

| Componente | Repositório | Responsabilidade | Custo |
|---|---|---|---|
| `autogiro-auth` | autogiro-auth | Valida CPF, consulta o cliente, emite JWT | grátis permanente |
| Kong Gateway OSS | autogiro-infra-k8s | Roteia `/api/v1/*` e valida a assinatura do JWT | open source |
| `autogiro-api` | autogiro-app | Regras de negócio da oficina (OS, veículos, peças) | local |
| HPA + metrics-server | infra-k8s / app | Escalabilidade horizontal por CPU e memória | local |
| Neon PostgreSQL | autogiro-infra-db | Persistência, com branches por ambiente | grátis permanente |
| New Relic | autogiro-infra-k8s | APM, logs, dashboards e alertas | grátis permanente |

## Exposição de rotas

O Kong recebe dois Ingress com políticas distintas
([`k8s/ingress.yaml`](../../../k8s/ingress.yaml)):

| Ingress | Caminhos | Plugin JWT |
|---|---|---|
| `autogiro-api` | `/api/v1` | **sim** — `konghq.com/plugins: autogiro-jwt` |
| `autogiro-api-public` | `/health`, `/docs`, `/openapi.json` | não |

Deixar a documentação e os healthchecks fora da proteção é deliberado: probes do Kubernetes
não carregam token, e o Swagger precisa ser alcançável para a avaliação.

## Onde cada requisito do enunciado é atendido

| Requisito | Componente |
|---|---|
| API Gateway | Kong Gateway OSS no cluster |
| Function Serverless para autenticação | AWS Lambda `autogiro-auth` |
| Banco de Dados Gerenciado | Neon PostgreSQL |
| Cluster Kubernetes com escalabilidade | kind + HPA (2 a 10) + metrics-server |
| Terraform para provisionamento | 3 repositórios de infraestrutura |
| Observabilidade | New Relic + Prometheus/Grafana local |
