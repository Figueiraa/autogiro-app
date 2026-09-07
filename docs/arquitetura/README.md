# Documentação da Arquitetura — AutoGiro

Documentação arquitetural do Tech Challenge Fase 3 (13SOAT). Cada documento registra uma
decisão real do projeto, com os números e trechos de código que a sustentam.

## Diagramas

| Documento | Conteúdo |
|---|---|
| [01 · Componentes](diagramas/01-componentes.md) | Visão de nuvem, APIs, banco e monitoramento, e o contrato entre emissor e validador do JWT |
| [02 · Sequência — autenticação por CPF](diagramas/02-sequencia-autenticacao.md) | Caminho de sucesso, os quatro caminhos de erro e a execução sem a AWS |
| [03 · Sequência — abertura de OS](diagramas/03-sequencia-abertura-de-os.md) | Abertura da ordem de serviço, evolução de status e a máquina de estados |

O modelo ER e a justificativa dos relacionamentos estão no repositório do banco:
[`autogiro-infra-db/README.md`](../../../autogiro-infra-db/README.md).

## RFCs — decisões técnicas em aberto para discussão

| RFC | Assunto | Status |
|---|---|---|
| [RFC-001](rfcs/RFC-001-escolha-da-nuvem.md) | Escolha da nuvem e a estratégia híbrida de custo zero | Aprovada |
| [RFC-002](rfcs/RFC-002-escolha-do-banco.md) | PostgreSQL gerenciado no Neon, com justificativa formal | Aprovada |
| [RFC-003](rfcs/RFC-003-estrategia-de-autenticacao.md) | Autenticação por CPF com Lambda, JWT e Kong | Aprovada |

## ADRs — decisões arquiteturais permanentes

| ADR | Decisão | Status |
|---|---|---|
| [ADR-001](adrs/ADR-001-comunicacao-rest-sincrona.md) | Comunicação REST síncrona via API Gateway | Aceita |
| [ADR-002](adrs/ADR-002-hpa-escalabilidade.md) | HPA para escalabilidade horizontal | Aceita |
| [ADR-003](adrs/ADR-003-quatro-repositorios.md) | Separação em quatro repositórios | Aceita |
| [ADR-004](adrs/ADR-004-emissor-desacoplado-do-validador.md) | Emissor (Lambda) desacoplado do validador (Kong) via JWT | Aceita |

## Qual documento responde a quê

| Pergunta | Documento |
|---|---|
| Por que o cluster é local e não gerenciado na nuvem? | RFC-001 |
| Quanto custaria fazer tudo na nuvem? | RFC-001 (tabelas de custo verificado) |
| Por que PostgreSQL e não MySQL ou NoSQL? | RFC-002 |
| Como funciona a autenticação por CPF? | RFC-003 e diagrama 02 |
| Por que a Lambda não conhece o Kong? | ADR-004 |
| Como o sistema escala? | ADR-002 |
| Por que quatro repositórios em vez de um monorepo? | ADR-003 |
| Por que REST e não mensageria? | ADR-001 |

## Convenções

- **RFC** propõe e discute uma decisão técnica, comparando alternativas com dados.
- **ADR** registra uma decisão arquitetural já tomada e suas consequências, incluindo as
  negativas.
- Nenhum documento afirma número que não tenha sido verificado na fonte. Onde há
  aproximação, ela está marcada com `~`.
