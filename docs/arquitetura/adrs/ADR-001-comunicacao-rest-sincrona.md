# ADR-001: Comunicação REST síncrona via API Gateway

- **Status:** Aceita
- **Data:** 2026-09-07
- **Decisores:** Pedro Figueira

## Contexto

O AutoGiro é composto por dois componentes executáveis que expõem interface de rede:

| Componente | Repositório | Natureza |
|---|---|---|
| `autogiro-api` (FastAPI) | `autogiro-app` | API principal, deployada no cluster kind |
| `autogiro-auth` | `autogiro-auth` | Function serverless (AWS Lambda) de autenticação por CPF |

Não há um terceiro serviço de domínio. As operações do sistema são, em sua maioria,
CRUD sobre ordens de serviço, clientes, veículos e consulta/baixa de estoque — fluxos
em que o chamador precisa da resposta para continuar: quem abre uma OS precisa do
identificador gerado, quem consulta o estoque precisa saber se a peça existe antes de
prosseguir.

O Kong Gateway OSS já está no cluster (`autogiro-infra-k8s/terraform/main.tf`,
`helm_release.kong`, modo DB-less) atuando como Ingress Controller e API Gateway. O
roteamento é declarado nos Ingresses da aplicação (`autogiro-app/k8s/ingress.yaml`):
`/api/v1` com o plugin `autogiro-jwt` e as rotas públicas (`/health`, `/docs`,
`/openapi.json`) em um Ingress separado, sem autenticação.

Avaliou-se introduzir mensageria (fila/broker) para desacoplar as chamadas, conforme
padrão comum em arquiteturas distribuídas. Duas restrições pesaram contra: o volume e a
natureza das operações não pedem processamento assíncrono, e a restrição de custo zero
somada à necessidade de operar um broker (fila, DLQ, retentativas, idempotência,
observabilidade do consumidor) criaria complexidade operacional sem contrapartida
funcional.

## Decisão

Toda comunicação entre componentes e com o cliente externo é **REST síncrona sobre
HTTP**, com o Kong como único ponto de entrada do cluster.

- O cliente autentica na Lambda (Function URL) e recebe um JWT.
- As chamadas de negócio vão para o Kong, que valida o JWT via plugin `jwt` e roteia
  para o `Service` `autogiro-api` na porta 80.
- Nenhum broker de mensagens é provisionado.

Não haverá tópicos, filas ou eventos de domínio publicados nesta fase.

## Consequências

### Positivas

- **Latência previsível e mensurável.** Cada requisição tem um caminho único
  (Kong → Service → pod), o que torna direto instrumentar p50/p95/p99 por rota no New
  Relic (requisito de observabilidade) sem correlacionar produtor e consumidor.
- **Sem consistência eventual.** O estado lido após uma escrita é o estado gravado. Não
  existe janela em que a OS foi aberta mas ainda não aparece na consulta, o que elimina
  toda uma classe de bug de leitura desatualizada e de compensação manual.
- **Depuração linear.** O erro aparece na resposta HTTP do próprio chamador, com status
  code semântico — a Lambda devolve 400, 401 e 503 conforme o caso
  (`autogiro-auth/src/handler.py`), a API devolve 401 em token inválido
  (`app/interfaces/http/dependencies.py`).
- **Superfície de infraestrutura menor.** Nenhum componente adicional para provisionar,
  monitorar ou manter dentro do orçamento zero.
- **Autorização centralizada no gateway.** Uma única política (`KongPlugin autogiro-jwt`)
  protege todas as rotas `/api/v1`, sem precisar replicar verificação por serviço.

### Negativas

- **Acoplamento temporal.** O chamador só conclui se o chamado estiver disponível: se a
  API está indisponível, a requisição falha na hora, sem buffer que absorva a
  indisponibilidade. Uma fila permitiria aceitar agora e processar depois.
- **Sem absorção de picos.** Rajadas de tráfego se traduzem diretamente em carga nos
  pods. A mitigação é o HPA (ver ADR-002), não o enfileiramento.
- **Sem retentativa automática.** Falhas transitórias precisam ser tratadas pelo
  cliente. A Lambda mitiga parcialmente reaproveitando a conexão com o Neon entre
  invocações e reconectando quando ela está fechada, mas não há retry no transporte.
- **Operações longas ficariam bloqueantes.** Se no futuro surgir um fluxo demorado
  (relatório consolidado da rede, importação em lote), ele não caberá neste modelo sem
  revisão desta decisão.

## Alternativas consideradas

| Alternativa | Por que foi descartada |
|---|---|
| **Mensageria (fila/broker) entre os componentes** | Não há assincronia natural nas operações: as duas são request/response com resposta necessária. O broker adicionaria fila, DLQ, tratamento de duplicidade e observabilidade do consumidor para um sistema com dois componentes e volume baixo — complexidade operacional sem ganho. |
| **gRPC entre os componentes** | Ganho de desempenho irrelevante nesta escala e perda de interoperabilidade: o Kong precisaria de configuração específica e o Swagger/OpenAPI da API, entregável do projeto, deixaria de descrever a interface. |
| **Chamada direta ao Service, sem gateway** | Eliminaria o ponto de aplicação da política de JWT e o requisito explícito de API Gateway do Tech Challenge. |
| **Event sourcing no domínio de OS** | O histórico de mudanças de status é atendido por modelagem relacional no Neon; adotar event sourcing traria complexidade de projeção e reconstrução de estado sem demanda que a justifique. |

A decisão é reversível de forma incremental: como o Kong é o único ponto de entrada,
introduzir um caminho assíncrono no futuro significa adicionar uma rota e um consumidor,
sem reescrever o que existe.
