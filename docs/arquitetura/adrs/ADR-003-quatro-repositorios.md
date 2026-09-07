# ADR-003: Separação da plataforma em quatro repositórios

- **Status:** Aceita
- **Data:** 2026-09-07
- **Decisores:** Pedro Figueira

## Contexto

O enunciado do Tech Challenge Fase 3 exige que a entrega esteja distribuída em quatro
repositórios distintos. A restrição é, portanto, dada — mas a forma de recortar os quatro
limites e de resolver o acoplamento entre eles é decisão de arquitetura, e é o que este
ADR registra.

Os artefatos do projeto têm naturezas muito diferentes: código de aplicação, código de
função serverless, infraestrutura de cluster e infraestrutura de banco de dados. Cada um
tem ferramenta de build, gate de qualidade e cadência de mudança próprios.

## Decisão

Recortar a plataforma nestes quatro repositórios, com um critério único: **um repositório
por unidade de deploy independente**.

| Repositório | Conteúdo | Ferramenta de deploy |
|---|---|---|
| `autogiro-infra-db` | Terraform (provider `neon`), migrations SQL, modelo ER | `terraform apply` |
| `autogiro-infra-k8s` | Terraform: cluster kind, Kong, metrics-server, agente New Relic, Consumer e plugin JWT | `terraform apply` |
| `autogiro-auth` | Lambda Python de autenticação por CPF + Terraform (provider `aws`) | `terraform apply` |
| `autogiro-app` | API FastAPI + manifests em `k8s/` | build GHCR + `kubectl apply` |

### Ordem de deploy

```
infra-db  →  infra-k8s  →  auth  →  app
```

O encadeamento decorre das dependências reais de dados:

1. **`infra-db`** não depende de ninguém: cria o projeto e as branches no Neon.
2. **`infra-k8s`** cria o cluster, o Kong e o metrics-server; independe do banco.
3. **`auth`** precisa da connection string do Neon para consultar `clients`
   (`autogiro-auth/src/handler.py`, `os.environ["DATABASE_URL"]`).
4. **`app`** precisa do cluster (destino do `kubectl apply`) e do banco (`DATABASE_URL`
   no secret).

### Como o acoplamento entre repositórios é resolvido

**Por outputs do Terraform lidos na pipeline e cadastrados como secrets do GitHub — não
por state compartilhado.** Nenhum repositório lê o state de outro (sem `terraform_remote_state`,
sem bucket comum): a pipeline do repositório produtor extrai o output e o publica como
secret no repositório consumidor, que passa a tratá-lo como entrada opaca.

Assim a connection string do Neon chega a `autogiro-auth` e a `autogiro-app`, e o segredo
HS256 é cadastrado nos dois lados do fluxo de JWT (`autogiro-auth` e a variável
`jwt_secret` de `autogiro-infra-k8s/terraform/kong-jwt.tf`, declarada
`sensitive = true`).

## Consequências

### Positivas

- **Ciclos de vida independentes.** É o benefício central. A infraestrutura muda
  raramente: o cluster kind, a versão do chart do Kong (`2.46.0`), a do metrics-server
  (`3.12.2`) e a do `nri-bundle` (`5.0.100`) são alterados em janelas específicas. A
  aplicação muda todo dia. Repositório único forçaria as duas cadências a compartilhar a
  mesma pipeline, o mesmo versionamento e a mesma revisão.
- **Pipelines menores e mais rápidas.** Cada pipeline roda só o que faz sentido para seu
  artefato: `fmt`/`validate`/`tflint`/`plan`/`checkov` nos repositórios de Terraform;
  `ruff`/`bandit`/`pytest`/`trivy`/build da imagem em `autogiro-app`;
  `ruff`/`bandit`/`pytest`/empacotamento do zip em `autogiro-auth`. Não há job de
  Terraform disparando a cada commit de aplicação, nem build de imagem a cada mudança de
  variável de infraestrutura.
- **Blast radius reduzido.** Um `terraform apply` malformado no repositório de cluster não
  tem como afetar o banco no Neon nem a Lambda, porque as credenciais e os providers de
  cada repositório são disjuntos: o repositório de banco só tem credencial Neon, o de
  Lambda só tem credencial AWS. O erro fica contido no escopo do repositório onde foi
  introduzido.
- **Permissões mínimas por repositório.** Cada conjunto de secrets é o menor possível para
  aquela unidade de deploy, em vez de um repositório único com todas as credenciais da
  plataforma.
- **Histórico legível.** O log de `autogiro-infra-k8s` conta a evolução do cluster; o de
  `autogiro-app` conta a evolução do domínio. Em monorepo essas duas narrativas ficariam
  entrelaçadas.

### Negativas

- **Custo de coordenação entre repositórios.** Uma mudança que atravessa fronteiras exige
  mais de um PR e mais de um merge, na ordem correta. O exemplo concreto é a rotação do
  segredo HS256: precisa ser aplicada em `autogiro-auth` e em `autogiro-infra-k8s`, e
  entre um apply e o outro os tokens emitidos com o segredo antigo falham a validação no
  Kong.
- **Não existe commit atômico entre repositórios.** Nenhum mecanismo garante que quatro
  repositórios estejam em versões mutuamente compatíveis num dado instante — a ordem de
  deploy documentada é a garantia, e ela é processual, não técnica.
- **Contratos implícitos passam a existir.** A claim `iss` com valor `autogiro-auth`
  (emitida em `handler.py`, esperada como `key` da credencial em `kong-jwt.tf`) é um
  contrato entre dois repositórios que nenhum compilador ou teste de integração local
  verifica. Ver ADR-004.
- **Onboarding mais lento.** Quem chega precisa clonar quatro repositórios e entender a
  ordem antes de subir o ambiente completo.
- **Duplicação de configuração de pipeline.** Steps de lint e de setup de Python se
  repetem entre os repositórios Python, sem um lugar único para deduplicar.

## Alternativas consideradas

| Alternativa | Avaliação |
|---|---|
| **Monorepo único** | Commit atômico e refatoração cruzada trivial. Descartado: o enunciado exige quatro repositórios, e o monorepo faria a pipeline de infraestrutura disparar a cada mudança de aplicação, além de concentrar todas as credenciais em um só lugar. |
| **Dois repositórios (`app` + `infra`)** | Recorte mais grosso, também incompatível com o exigido. Juntaria banco e cluster — dois artefatos com providers, credenciais e cadências distintas — no mesmo blast radius. |
| **State remoto compartilhado com `terraform_remote_state`** | Resolveria a propagação de outputs automaticamente, mas criaria dependência de leitura direta do state entre repositórios: o consumidor passaria a exigir acesso ao state (e aos valores sensíveis) do produtor, além de um backend remoto — que na estratégia de custo zero seria mais um recurso a provisionar. Preferiu-se propagação explícita via secrets. |
| **Submódulos Git para compartilhar Terraform** | Reintroduz acoplamento de versão no momento do clone e é notoriamente frágil em CI, sem resolver o problema de propagação de valores. |
