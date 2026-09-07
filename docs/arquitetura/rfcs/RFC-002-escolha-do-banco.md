# RFC-002: Escolha do banco de dados — PostgreSQL gerenciado no Neon

- **Status:** Aprovada
- **Data:** 2026-09-07
- **Autor:** Pedro Figueira

## Resumo

Esta RFC apresenta a **justificativa formal para a escolha do banco de dados** do AutoGiro,
exigida pelo enunciado da Fase 3.

A decisão é **PostgreSQL 17 gerenciado no Neon**. A natureza dos dados do domínio é fortemente
relacional, há necessidade real de integridade referencial e de transações ACID, e a máquina de
estados da ordem de serviço se beneficia diretamente do tipo `ENUM` nativo do PostgreSQL. O Neon
foi escolhido como provedor por oferecer free tier permanente sem cartão de crédito e por expor
**branches de banco de dados** — mecanismo que resolve elegantemente a exigência de ambientes
separados de homologação e produção.

## Motivação

O modelo de dados implementado em `autogiro-infra-db/migrations/001_schema_inicial.sql` tem
**8 tabelas**, **23 índices** e **1 tipo ENUM** com 7 valores. A estrutura das entidades encadeia:

```
clients → vehicles → service_orders → service_order_items → service_types
                                    → service_order_parts  → parts
```

Três características do domínio determinam a escolha:

**1. Os dados são fortemente relacionais.** Um cliente possui veículos; cada veículo possui ordens
de serviço; cada ordem é composta por itens de serviço e por peças aplicadas. O acesso predominante
é por relacionamento e agregação — "tempo médio por status", "volume diário de ordens de serviço",
"peças com estoque baixo" — e não por chave primária. Joins são a regra, não a exceção.

**2. Há necessidade de transações ACID.** Abrir uma ordem de serviço grava a OS, seus itens, suas
peças e **decrementa o estoque** das peças aplicadas. Essas escritas precisam ser atômicas: ou
todas acontecem, ou nenhuma. Sem transação, o estoque diverge do que foi efetivamente consumido —
uma inconsistência que corrompe silenciosamente o inventário da rede de oficinas.

**3. A máquina de estados da OS é um domínio fechado.** O status de uma ordem de serviço pertence a
um conjunto finito e conhecido de 7 valores. Modelá-lo como `VARCHAR` (como na Fase 2) delega a
validação inteiramente à aplicação; modelá-lo como tipo do banco faz o próprio PostgreSQL rejeitar
estados fora do domínio.

## Análise das alternativas

### PostgreSQL vs. MySQL

Ambos são relacionais, ACID e maduros. O MySQL é uma alternativa **viável** — a decisão foi por
margem, não por eliminação:

| Critério | PostgreSQL | MySQL | Peso no AutoGiro |
|---|---|---|---|
| Tipo `ENUM` como tipo de domínio reutilizável | Sim, `CREATE TYPE ... AS ENUM` | Apenas `ENUM` por coluna, não reutilizável | Alto — o status da OS é o núcleo do fluxo |
| `CHECK` constraints expressivas | Suporte completo, inclusive com regex | Suportadas desde 8.0.16, mas mais limitadas historicamente | Alto — validamos formato de CPF/CNPJ com regex |
| Índices parciais (`WHERE`) | Sim | Não suportado | Médio — consultas de dashboard |
| Riqueza de tipos (`TIMESTAMPTZ`, `NUMERIC`, JSONB) | Ampla | Menor | Médio — operação multi-unidade exige fuso |
| Ecossistema Python assíncrono | `asyncpg` e `psycopg` maduros | Menos consolidado para async | Médio |
| Free tier gerenciado permanente sem cartão | Neon | Alternativas equivalentes menos favoráveis | Alto |

### PostgreSQL vs. NoSQL (DynamoDB, MongoDB)

**Descartado.** O argumento não é de preferência, é de aderência ao domínio:

| Aspecto | Consequência de usar NoSQL aqui |
|---|---|
| Denormalização obrigatória | Cliente e veículo teriam de ser duplicados em cada documento de OS, com custo de consistência a cada atualização de cadastro |
| Integridade referencial | Deixaria de existir no banco e passaria a ser responsabilidade integral da aplicação — exatamente a invariante que não queremos perder |
| Transações multi-entidade | O decremento de estoque junto com a criação da OS envolve agregados distintos; em modelos orientados a documento isso exige transações distribuídas ou compensação |
| Consultas de agregação | "Tempo médio por status" e "volume diário de OS" exigiriam índices secundários, tabelas de agregação ou pipelines — trabalho que o SQL resolve declarativamente |
| Ganho de escala | Real, mas irrelevante: o volume de uma rede de oficinas de médio porte não se aproxima do ponto em que sharding horizontal compensa perder ACID |

O NoSQL seria a escolha correta se o acesso fosse por chave, o esquema volátil e a escala
horizontal a restrição dominante. Nenhuma das três condições se aplica.

### Escolha do provedor gerenciado

| Provedor | Free tier | Cartão? | Branches de banco | Veredito |
|---|---|---|---|---|
| **Neon** | **Permanente — 0,5 GB, 100 CU-horas/mês** | **Não** | **Sim** | Adotado |
| AWS RDS PostgreSQL | 12 meses | Sim | Não | Descartado |
| Azure Database for PostgreSQL | 12 meses, depois cobra sem desligar | Sim | Não | Descartado |
| PostgreSQL em container no cluster | Grátis | Não | Não | Descartado — não é *gerenciado*, e o cluster é local |

O diferencial do Neon vai além do preço: ele **versiona o banco como o Git**. Cada branch de dados
tem storage isolado sem custo adicional, o que mapeia diretamente sobre a exigência de deploy
automático das branches de homologação e produção:

| Branch Git | Branch Neon | Gatilho |
|---|---|---|
| `develop` | `homolog` | Push em `develop` |
| `main` | `prod` | Push em `main` |

### Nota sobre o isolamento entre ambientes

O provisionamento real produziu **dois projetos no Neon**, e não um só com duas branches, como
o desenho acima sugere. A causa é o state do Terraform: cada ambiente tem seu próprio workspace
no HCP (`autogiro-infra-db-homolog` e `-prod`), e cada workspace criou seu próprio projeto.

| Workspace | Projeto Neon | Branch usada no deploy |
|---|---|---|
| `autogiro-infra-db-homolog` | `rough-math-76533899` | `homolog` |
| `autogiro-infra-db-prod` | `misty-salad-45431057` | `prod` |

A decisão foi **manter esse desenho**. Ele consome duas das 100 vagas de projeto do free tier
e deixa duas branches ociosas, mas em contrapartida os ambientes ficam isolados no nível mais
alto possível: produção e homologação não compartilham projeto, cota de storage nem
compute-hours. Um erro de configuração em homologação não tem como afetar produção.

A alternativa — um único workspace do HCP, deixando as branches do Neon fazerem toda a
separação — seria mais econômica em recursos, mas colocaria os dois ambientes sob o mesmo
state e a mesma cota.

## Decisão

Adotar **PostgreSQL 17 gerenciado no Neon**, provisionado por Terraform (provider
`kislerdm/neon`) no repositório `autogiro-infra-db`, com migrations SQL idempotentes versionadas.

O schema real materializa as justificativas acima:

**Tipo ENUM nativo com os 7 estados da OS:**

```sql
CREATE TYPE service_order_status AS ENUM (
    'RECEBIDA', 'EM_DIAGNOSTICO', 'AGUARDANDO_APROVACAO',
    'EM_EXECUCAO', 'FINALIZADA', 'ENTREGUE', 'ORCAMENTO_RECUSADO'
);
```

**Constraints declarativas que protegem invariantes independentemente da aplicação:**

| Constraint | Definição | Invariante protegida |
|---|---|---|
| `ck_clients_cpf_cnpj_digitos` | `CHECK (cpf_cnpj ~ '^[0-9]{11}$\|^[0-9]{14}$')` | Aceita 11 dígitos (CPF) ou 14 (CNPJ), **sempre sem máscara** — é exatamente o formato que a Lambda de autenticação consulta (ver RFC-003) |
| `ck_parts_stock` | `CHECK (stock_quantity >= 0)` | Estoque nunca negativo, mesmo sob escrita concorrente |
| `ck_service_orders_completed_after_started` | `CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)` | Coerência temporal do ciclo de vida da OS |
| `ck_service_orders_delivered_after_completed` | `CHECK (delivered_at IS NULL OR completed_at IS NULL OR delivered_at >= completed_at)` | Idem |
| `uq_clients_cpf_cnpj` | `UNIQUE (cpf_cnpj)` | Um cliente por documento; sustenta a busca da Lambda |

**Política de exclusão explícita**, refletindo o valor do histórico:

| Relação | `ON DELETE` | Razão |
|---|---|---|
| `clients` → `vehicles`, `clients`/`vehicles` → `service_orders` | `RESTRICT` | Apagar um cliente com veículos ou ordens destruiria o histórico da oficina |
| `service_orders` → `service_order_items` / `service_order_parts` | `CASCADE` | Itens e peças não têm existência independente da OS |
| `service_types` → `service_order_items`, `parts` → `service_order_parts` | `RESTRICT` | Preserva ordens de serviço históricas |

`service_order_items` e `service_order_parts` são tabelas associativas N:N **com atributos
próprios** (`quantity` e `unit_price`). O preço é **copiado** para a OS em vez de referenciado: o
valor cobrado deve refletir o momento da venda, não o preço atual do catálogo.

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Free tier do Neon limitado a 0,5 GB | Esgotamento de storage | Volume de dados de demonstração é pequeno; monitoramento pelo painel do Neon |
| Cota de 100 CU-horas/mês | Suspensão do compute e banco indisponível | Autosuspend após 5 minutos de inatividade (`suspend_timeout_seconds`) preserva a cota; testes de carga são evitados contra o Neon |
| **Cold start do compute suspenso** | Primeira consulta após inatividade tem latência elevada | Aceitável para este uso; a Lambda reaproveita a conexão entre invocações no mesmo execution environment |
| Acoplamento a um provedor menor que os hyperscalers | Migração forçada se o Neon mudar a política | O banco é **PostgreSQL 17 sem modificações**: as migrations rodam em qualquer PostgreSQL — comprovado pela pipeline, que as aplica em um `postgres:17-alpine` efêmero |
| Uso de recursos exclusivos do PostgreSQL (ENUM, índices parciais) | Impede troca para MySQL | Trade-off aceito deliberadamente: o ganho de integridade supera a portabilidade entre SGBDs, que não é um requisito |
| Alterar valores de um `ENUM` exige DDL | Evoluir a máquina de estados é mais custoso que em `VARCHAR` | É o preço da garantia; `ALTER TYPE ... ADD VALUE` cobre a adição, que é o caso esperado |
| Migrations reaplicadas por engano | Corrupção de schema | Todas são idempotentes (`IF NOT EXISTS`); a pipeline **prova** isso aplicando cada migration duas vezes em um PostgreSQL efêmero |

## Referências

- `autogiro-infra-db/README.md` — Justificativa técnica e modelo ER completo com cardinalidades
- `autogiro-infra-db/migrations/001_schema_inicial.sql` — Tipos, 8 tabelas e constraints
- `autogiro-infra-db/migrations/002_indices.sql` — Índices de performance derivados de consultas reais
- `autogiro-infra-db/terraform/` — Provisionamento do projeto, roles, databases e branches no Neon
- Tech Challenge Fase 3 (13SOAT) — requisito de justificativa formal para a escolha do banco
- Documentação do Neon — free tier, branching e autosuspend
- RFC-001 (escolha da nuvem) e RFC-003 (estratégia de autenticação)
