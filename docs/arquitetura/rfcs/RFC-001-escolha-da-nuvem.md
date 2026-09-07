# RFC-001: Escolha da nuvem e estratégia de infraestrutura

- **Status:** Aprovada
- **Data:** 2026-09-07
- **Autor:** Pedro Figueira

## Resumo

Esta RFC formaliza a escolha de provedores de nuvem do AutoGiro sob uma restrição inegociável:
**custo zero permanente**, sem orçamento para nuvem paga e preferencialmente sem cadastro de cartão
de crédito.

A decisão é uma **estratégia híbrida**: usar nuvem pública real e gratuita onde existe free tier
permanente — banco de dados (Neon), função serverless (AWS Lambda) e observabilidade (New Relic) —
e executar o **cluster Kubernetes localmente com kind**, provisionado por Terraform exatamente como
seria na nuvem. O API Gateway é o **Kong Gateway OSS**, rodando dentro do próprio cluster. Custo
mensal resultante: **R$ 0,00**.

## Motivação

O enunciado da Fase 3 exige infraestrutura em nuvem, API Gateway, função serverless, banco
gerenciado e observabilidade. Ao mesmo tempo, três passagens do PDF deixam margem explícita para a
escolha do provedor:

| Passagem do PDF | Consequência |
|---|---|
| "Infraestrutura obrigatória (livre escolha de nuvem)" | O provedor é decisão do time |
| "Implementar um API Gateway (exemplo: AWS API Gateway, Kong, Traefik ou outro)" | Kong e Traefik são citados nominalmente e são open source |
| "Links para os deploys ativos (se aplicável)" | O link ativo é condicional; o entregável obrigatório é o repositório com código, CI/CD e README |
| "ferramentas como Datadog ou New Relic (escolha livre)" | New Relic é citado nominalmente |

O problema é que "nuvem" e "gratuito" raramente coincidem de forma permanente: free tiers de 12
meses são armadilhas para um projeto que deve sobreviver à entrega, e Kubernetes gerenciado
gratuito não existe de forma confiável. Cada componente foi verificado individualmente contra o
preço público do provedor antes de ser adotado.

## Análise das alternativas

### AWS — apenas a Lambda é aproveitável

| Serviço | Free tier | Veredito |
|---|---|---|
| **Lambda** | **1M requisições/mês, permanente** | Adotado |
| API Gateway | 12 meses apenas | Descartado — usamos Kong |
| EKS (control plane) | Nenhum | Descartado — ~US$ 73/mês |
| NAT Gateway | Nenhum | Descartado — ~US$ 32/mês |
| RDS PostgreSQL | 12 meses apenas | Descartado — usamos Neon |

A Lambda é o **único serviço da AWS gratuito para sempre** dentro do escopo do projeto: 1M
requisições/mês está ordens de grandeza acima do uso previsto. O API Gateway foi descartado porque
seu free tier expira em 12 meses. EKS e NAT Gateway juntos somariam ~US$ 105/mês.

### Azure — o tier Developer do APIM demonstrado em aula é pago

O Azure API Management no tier **Developer** foi demonstrado na disciplina. A verificação contra a
API oficial de preços da Microsoft mostrou:

| Tier do APIM | Preço | Veredito |
|---|---|---|
| **Developer** | **US$ 0,0658/h = US$ 48,96/mês** | Descartado — pago e **sem SLA** |
| **Consumption** | **1M chamadas/mês grátis, permanente** | Viável, mas não escolhido |
| Basic / Standard / Premium | US$ 150 / 700 / 2.849 por mês | Descartado |

O tier Developer não está no free tier de 12 meses nem na lista de serviços permanentemente
gratuitos. Em aula ele provavelmente não gerou cobrança visível por ter sido consumido sobre o
crédito de US$ 200 da conta ou uma subscription institucional. Detalhe agravante: o Developer
**também não tem SLA** — a própria Microsoft o posiciona para avaliação e uso não produtivo.

O tier **Consumption** seria genuinamente gratuito e é uma alternativa legítima. Optou-se por Kong
porque roda no próprio cluster, não exige conta de nuvem nem cartão, não tem limite de chamadas, é
citado nominalmente no PDF e foi coberto por três aulas da disciplina (Conhecendo o Kong, Criando
Serviços e Rotas, Consumers) — sendo a aula de Consumers exatamente o mecanismo usado na RFC-003.
**AKS** foi descartado porque, apesar do control plane gratuito permanente, cada nó B2s custa
~US$ 31/mês.

### Oracle Cloud — descartada por risco, não por preço

Era o único provedor com Kubernetes gerenciado gratuito (OKE Basic) e o candidato mais forte à
proposta. Foi descartado por mudança unilateral de política:

| Evento | Data | Impacto |
|---|---|---|
| Corte do free tier ARM pela metade (4 OCPU/24 GB → 2 OCPU/12 GB), sem anúncio público | 15/06/2026 | Capacidade insuficiente para o cluster planejado |
| Início da **terminação de instâncias** acima do novo limite, com aviso de que *pode não ser possível recriar* os recursos | 18/08/2026 | Perda potencial e irreversível do cluster |
| Escassez crônica de capacidade ARM ("out of host capacity") | Contínuo | Recriação não garantida |

O risco de perder o cluster na véspera da entrega — sem possibilidade de recriação — é inaceitável
para um projeto com data fixa. O trade-off aqui foi consciente: trocamos a URL pública que a Oracle
ofereceria por previsibilidade.

### Banco de dados gerenciado

| Opção | Free tier | Cartão? | Veredito |
|---|---|---|---|
| **Neon PostgreSQL** | **Permanente, 0,5 GB, 100 CU-horas/mês** | **Não** | Adotado |
| AWS RDS | 12 meses | Sim | Descartado |
| Azure Database for PostgreSQL | 12 meses, depois cobra sem desligar | Sim | Descartado |

O detalhamento da escolha está na **RFC-002**.

### Observabilidade

| Opção | Free tier | Cartão? | Veredito |
|---|---|---|---|
| **New Relic** | **100 GB/mês permanente, APM incluso, 1 usuário** | **Não** | Adotado |
| Datadog | Retenção de métricas de **1 dia**, **exclui APM e Log Management** | Sim | Descartado |

O Datadog teve seis aulas na disciplina, mas seu free tier exclui exatamente o que o PDF pede: APM
e gestão de logs, com retenção de métricas de apenas um dia. O New Relic teve as mesmas seis aulas,
é citado nominalmente no PDF e oferece 100 GB/mês permanentes com APM incluso e sem cartão.

### Cluster Kubernetes — o único componente local

| Opção | Custo real | Veredito |
|---|---|---|
| **kind local via Terraform** | Grátis | Adotado |
| AWS EKS | ~US$ 73/mês (control plane) + nós | Descartado |
| Azure AKS | Control plane grátis + ~US$ 31/mês por nó | Descartado |
| Oracle OKE Basic | Grátis, porém instável (ver acima) | Descartado por risco |

## Decisão

Adotar a **estratégia híbrida**, com a seguinte composição:

| Componente | Escolha | Free tier | Cartão? |
|---|---|---|---|
| Cluster Kubernetes | kind (local) via Terraform | Grátis | Não |
| API Gateway | Kong Gateway OSS (no cluster) | Grátis, open source | Não |
| Function Serverless | AWS Lambda (Python) | Permanente, 1M req/mês | Sim¹ |
| Banco gerenciado | Neon PostgreSQL | Permanente, 0,5 GB | **Não** |
| Observabilidade | New Relic | Permanente, 100 GB/mês | **Não** |
| CI/CD | GitHub Actions | 2.000 min/mês | Não |
| Registry de imagens | GitHub Container Registry | Grátis para repos públicos | Não |
| Terraform state | HCP Terraform (execução local) | Grátis | Não |

¹ A AWS exige cartão no cadastro para verificação de identidade, mas a Lambda **não gera cobrança**
neste uso: o free tier é permanente e o consumo previsto é três ordens de grandeza abaixo do limite.

**O que a estratégia híbrida entrega de verdade:** banco gerenciado real com link ativo,
serverless real com Function URL pública, e observabilidade real com dashboards populados por dados
de produção. Apenas o cluster é local — e é provisionado por Terraform com os mesmos recursos
(Deployment, Service, HPA, Ingress, metrics-server) que teria em nuvem gerenciada.

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| **O cluster local não tem URL pública** | A avaliação pode cobrar um deploy ativo do cluster | Este é o trade-off central e assumido desta RFC. Mitigações: (a) banco, serverless e observabilidade têm links públicos reais e demonstráveis; (b) o PDF condiciona o link com "se aplicável"; (c) esta RFC documenta a análise de custo que motivou a decisão; (d) o vídeo de demonstração exercita o cluster ponta a ponta |
| Neon free tier: 0,5 GB e 100 CU-horas/mês | Suspensão do compute ao atingir a cota | Volume de demonstração é pequeno; autosuspend após 5 min de inatividade preserva a cota; evitar loops de carga nos testes |
| New Relic: retenção de ~8 dias no free tier | Dados podem expirar antes da avaliação | Gravar o vídeo com a janela de dados ativa; dashboards versionados como código via provider `newrelic` |
| AWS pede cartão no cadastro | Cobrança acidental por outro serviço | AWS Budget com alerta em US$ 1; nenhum outro serviço AWS é provisionado pelo Terraform |
| Cold start da Lambda (~1s) | Latência na primeira autenticação | Aceitável para um fluxo de login; provisioned concurrency foi descartada por gerar custo |
| Self-hosted runner exige a máquina ligada para o CD do cluster | Deploy do cluster não é totalmente automático | `make deploy` documentado como via manual equivalente; o pipeline valida `plan`, lint, testes e build da imagem independentemente |
| Mudança unilateral de free tier por qualquer provedor | Perda de um componente | Os componentes são desacoplados (banco, auth e observabilidade são substituíveis isoladamente); o caso Oracle demonstra que este risco é concreto, não hipotético |

## Referências

- `PLANEJAMENTO.md`, seção 0 — Análise de custo com os valores verificados
- `CONTEXTO.md` — Tabelas de decisões tomadas e descartadas
- Tech Challenge Fase 3 (13SOAT) — enunciado em PDF: infraestrutura, API Gateway, serverless e observabilidade
- API oficial de preços da Microsoft — tiers do Azure API Management
- Free tier permanente da AWS (Lambda), do Neon (storage e CU-horas), do New Relic (100 GB/mês com
  APM) e do Datadog (retenção e exclusão de APM/Logs)
- Comunicado da Oracle Cloud sobre a alteração do Always Free ARM (15/06/2026 e 18/08/2026)
- `autogiro-infra-k8s/terraform/` — provisionamento do cluster kind e do Kong
- RFC-002 (escolha do banco) e RFC-003 (estratégia de autenticação)
