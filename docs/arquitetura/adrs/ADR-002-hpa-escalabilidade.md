# ADR-002: Escalabilidade horizontal com HPA por CPU e memória

- **Status:** Aceita
- **Data:** 2026-09-07
- **Decisores:** Pedro Figueira

## Contexto

A rede de oficinas expandiu para múltiplas unidades e a carga sobre a API deixou de ser
constante: há picos previsíveis (abertura de OS no início do turno) e picos não
previsíveis. Escalar manualmente o `Deployment` a cada variação não é operável, e
dimensionar para o pico e deixar fixo desperdiça recursos de um cluster local.

A comunicação é REST síncrona (ver ADR-001), portanto não existe fila absorvendo rajadas:
a única defesa contra pico de tráfego é aumentar o número de réplicas que atendem
concorrentemente.

O cluster é kind, provisionado por Terraform em `autogiro-infra-k8s/terraform/main.tf`.

## Decisão

Usar o **HorizontalPodAutoscaler** da API `autoscaling/v2`, declarado em
`autogiro-app/k8s/hpa.yaml`, apontando para o `Deployment` `autogiro-api` no namespace
`autogiro`, com os seguintes parâmetros:

| Parâmetro | Valor | Racional |
|---|---|---|
| `minReplicas` | `2` | Piso de disponibilidade: nunca uma única réplica, para que atualização e queda de pod não derrubem a API. |
| `maxReplicas` | `10` | Teto que limita o consumo do cluster e evita que um pico de tráfego (ou um loop de carga em teste) consuma toda a máquina. |
| `cpu` · `Utilization` | `averageUtilization: 70` | Escala antes da saturação, deixando margem para o novo pod subir e ficar `Ready`. |
| `memory` · `Utilization` | `averageUtilization: 80` | Limiar mais alto que o de CPU: memória em processo Python não é liberada tão elasticamente, então o gatilho precoce geraria escala desnecessária. |
| `behavior.scaleUp.stabilizationWindowSeconds` | `30` | Reage rápido ao pico — a janela curta é intencional na direção de subida. |
| `behavior.scaleDown.stabilizationWindowSeconds` | `120` | Desce devagar, evitando *flapping* (subir e descer em ciclos) quando a carga oscila. |

As duas métricas coexistem: o HPA calcula a réplica desejada para cada uma e usa **a
maior** das recomendações, então basta uma delas cruzar o alvo para escalar.

## Consequências

### Positivas

- **Requests e limits são pré-requisito atendido.** O alvo é `type: Utilization`, isto é,
  um percentual **do `requests`** do container — não do consumo absoluto nem da capacidade
  do nó. Sem `resources.requests` o HPA não tem denominador e reporta `<unknown>` na
  métrica, ficando inerte. O `autogiro-app/k8s/deployment.yaml` declara
  `requests: cpu: 100m / memory: 256Mi` e `limits: cpu: 500m / memory: 512Mi`. O alvo de
  70% de CPU significa, portanto, 70m de CPU média por pod; o de 80% de memória significa
  ~205Mi. Os `limits` complementam: definem o teto por pod (e a classe de QoS), impedindo
  que um pod degradado consuma o nó em vez de disparar a escala.
- **O metrics-server está provisionado como dependência explícita.** O HPA lê a
  `metrics.k8s.io`, servida pelo metrics-server, que o kind não traz por padrão. Ele é
  instalado por Helm no `main.tf` (`helm_release.metrics_server`, chart `metrics-server`,
  versão `3.12.2`, namespace `kube-system`), com a flag `--kubelet-insecure-tls` porque em
  kind os kubelets usam certificados self-signed. O próprio `hpa.yaml` registra a
  dependência em comentário, e o `main.tf` a documenta como "pré-requisito do HPA: sem ele
  o autoscaler não lê CPU nem memória".
- **Há espaço real de distribuição.** O `kind_config` declara dois nós: um
  `control-plane` (com o rótulo `ingress-ready=true` exigido pelo Kong e os
  `extra_port_mappings` 30000/30001) e um nó **`worker` adicional**, cujo comentário no
  Terraform é explícito: "dá ao HPA espaço real para distribuir réplicas". Sem o worker, a
  escala aconteceria toda dentro de um único nó e a demonstração de distribuição perderia
  sentido.
- **As probes tornam a escala segura.** A `readinessProbe` em `/health/ready`
  (`initialDelaySeconds: 5`, `periodSeconds: 5`), que executa um `SELECT 1`, garante que o
  pod novo só receba tráfego do Service depois de ter conectividade com o banco — a escala
  não injeta réplicas que respondem erro.
- **Métricas de escala observáveis.** O `nri-bundle` do New Relic está instalado com
  `infrastructure.enabled` e `kubeEvents.enabled`, o que expõe CPU/memória dos pods e os
  eventos de scheduling e OOMKill — permite verificar se o HPA agiu e por quê.

### Negativas

- **Escala por recurso, não por demanda de negócio.** CPU e memória são proxies. Uma
  lentidão causada por espera no banco (Neon) não aumenta CPU e não dispara escala; nesse
  caso adicionar réplicas também não resolveria, mas o sintoma fica invisível ao
  autoscaler. Métricas customizadas (RPS, latência) exigiriam adapter de métricas
  externas, fora do escopo de custo zero.
- **Latência de reação.** Mesmo com `scaleUp` de 30s, existe o ciclo de coleta do
  metrics-server, o agendamento do pod, o pull da imagem e a `initialDelaySeconds` da
  readiness. O primeiro pico é absorvido pelas réplicas existentes, não pelas novas.
- **Teto de 10 réplicas é um limite duro.** Acima disso a degradação é aceita em vez de
  escalada; em cluster local, os 10 pods a `500m` de limite já competem pelos recursos do
  host antes de o teto ser alcançado.
- **`scaleDown` de 120s custa recursos.** Após o pico, réplicas ociosas permanecem por ao
  menos dois minutos. É o preço deliberado de não oscilar.
- **Réplicas fixas no `Deployment` e no HPA convivem.** O `deployment.yaml` declara
  `replicas: 2` e o HPA tem `minReplicas: 2`. Um `kubectl apply` do Deployment após uma
  escala reverte a contagem momentaneamente até o HPA reconciliar.

## Alternativas consideradas

| Alternativa | Avaliação |
|---|---|
| **Réplicas fixas dimensionadas para o pico** | Simples e determinístico, mas desperdiça recursos do cluster local no vale e não demonstra elasticidade — que é requisito do Tech Challenge. |
| **VPA (Vertical Pod Autoscaler)** | Ajusta requests/limits do pod em vez do número de pods. Não resolve concorrência de requisições, exige reinício do pod para aplicar e não substitui o HPA no cenário de tráfego. |
| **HPA apenas por CPU** | Seria mais simples, mas deixa descoberto o cenário de pressão de memória (payloads grandes, conexões acumuladas), que em processo Python aparece antes na memória do que na CPU. |
| **KEDA com métricas de evento** | Ferramenta adequada para escala orientada a fila; sem broker no projeto (ver ADR-001) não há sinal para consumir, e agrega um componente a manter. |
| **Cluster Autoscaler** | Não se aplica: os nós do kind são contêineres declarados estaticamente no Terraform, não um grupo elástico de máquinas. |
