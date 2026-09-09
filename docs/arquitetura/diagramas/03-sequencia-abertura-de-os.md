# Diagrama de Sequência — Abertura de Ordem de Serviço

Segundo fluxo exigido pela documentação arquitetural. Cobre a abertura da OS e a evolução do
seu status até a entrega.

## Abertura da OS

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente autenticado
    participant K as Kong Gateway
    participant CT as service_order_controller
    participant UC as OpenServiceOrderUseCase
    participant GW as Gateways<br/>(veículo · serviço · peça)
    participant DB as PostgreSQL
    participant M as Métricas Prometheus

    C->>K: POST /api/v1/service-orders<br/>Bearer <token><br/>{vehicle_id, items[], parts[]}
    K->>CT: encaminha (assinatura válida)

    Note over CT: get_current_client()<br/>resolve o cliente pelo CPF do token

    CT->>UC: execute(OpenServiceOrderInput)

    UC->>GW: get_by_id(vehicle_id)
    GW->>DB: SELECT FROM vehicles
    alt veículo inexistente
        DB-->>GW: nenhuma linha
        UC-->>C: 404 NotFoundError("Veículo")
    end
    DB-->>GW: veículo (traz client_id)

    loop para cada serviço solicitado
        UC->>GW: get_by_id(service_type_id)
        GW->>DB: SELECT FROM service_types
        DB-->>GW: serviço com preço
        Note over UC: total += price * quantity
    end

    loop para cada peça solicitada
        UC->>GW: get_by_id(part_id)
        GW->>DB: SELECT FROM parts
        DB-->>GW: peça com preço e estoque
        alt estoque insuficiente
            UC-->>C: 409 InsufficientStockError<br/>(nome, disponível, solicitado)
        end
        Note over UC: total += unit_price * quantity<br/>agenda decremento do estoque
    end

    UC->>DB: SELECT count(*) FROM service_orders
    DB-->>UC: total existente
    Note over UC: number = OS + AAAAMMDD + sequencial<br/>status inicial = RECEBIDA

    loop decrementos agendados
        UC->>GW: decrement_stock(part_id, quantity)
        GW->>DB: UPDATE parts SET stock_quantity = stock_quantity - $1
    end

    UC->>DB: INSERT service_orders<br/>+ service_order_items<br/>+ service_order_parts
    DB-->>UC: OS persistida

    UC-->>CT: ServiceOrder
    CT->>M: record_service_order_opened()
    CT->>M: record_status_transition("RECEBIDA")
    CT-->>C: 201 Created + corpo da OS
```

**Ordem das operações:** o estoque só é decrementado depois de todas as validações passarem.
Assim uma OS rejeitada por veículo inexistente ou peça em falta não deixa efeito colateral no
inventário.

## Evolução do status

```mermaid
sequenceDiagram
    autonumber
    actor F as Funcionário da oficina
    participant CT as service_order_controller
    participant UC as UpdateServiceOrderStatusUseCase
    participant E as ServiceOrder<br/>(entidade de domínio)
    participant DB as PostgreSQL
    participant N as Notifier
    participant M as Métricas

    F->>CT: PATCH /api/v1/service-orders/{id}/status<br/>{"status": "EM_DIAGNOSTICO"}
    CT->>UC: execute(order_id, novo_status)
    UC->>DB: SELECT FROM service_orders
    DB-->>UC: OS atual

    UC->>E: transition_to(novo_status)
    Note over E: consulta VALID_TRANSITIONS<br/>regra de negócio no domínio

    alt transição não permitida
        E-->>F: 409 InvalidStatusTransitionError
    end

    UC->>DB: UPDATE service_orders SET status = $1
    UC->>N: notify_status_change(email, numero, status)
    Note over N: log estruturado JSON<br/>ou e-mail via SMTP
    N->>M: record_notification(canal, resultado)
    UC-->>CT: OS atualizada
    CT->>M: record_status_transition(status)
    CT-->>F: 200 OK
```

A notificação **nunca derruba o fluxo**: falha de SMTP é registrada e contabilizada como
`autogiro_notifications_total{result="failed"}`, mas não propaga exceção — a OS já foi
atualizada com sucesso quando a notificação dispara.

## Máquina de estados

```mermaid
stateDiagram-v2
    [*] --> RECEBIDA: abertura da OS
    RECEBIDA --> EM_DIAGNOSTICO
    EM_DIAGNOSTICO --> AGUARDANDO_APROVACAO: orçamento pronto
    AGUARDANDO_APROVACAO --> EM_EXECUCAO: cliente aprova
    AGUARDANDO_APROVACAO --> ORCAMENTO_RECUSADO: cliente recusa
    EM_EXECUCAO --> FINALIZADA: serviço concluído
    FINALIZADA --> ENTREGUE: veículo retirado
    ENTREGUE --> [*]
    ORCAMENTO_RECUSADO --> [*]
```

As transições são validadas em dois níveis:

| Nível | Mecanismo |
|---|---|
| Domínio | `VALID_TRANSITIONS` em `service_order_status.py` — rejeita salto inválido com `409` |
| Banco | `CREATE TYPE service_order_status AS ENUM (...)` — o PostgreSQL rejeita valor fora da lista |

Os status terminais (`FINALIZADA`, `ENTREGUE`, `ORCAMENTO_RECUSADO`) não têm saída, e são
usados para ocultar OS encerradas da listagem de trabalho ativo.

Os três estados que o enunciado cita para o dashboard de tempo médio correspondem a
`EM_DIAGNOSTICO` (Diagnóstico), `EM_EXECUCAO` (Execução) e `FINALIZADA` (Finalização).

## Referências de código

| Etapa | Arquivo |
|---|---|
| Abertura da OS | [`use_cases/open_service_order.py`](../../../app/application/use_cases/open_service_order.py) |
| Mudança de status | [`use_cases/update_service_order_status.py`](../../../app/application/use_cases/update_service_order_status.py) |
| Máquina de estados | [`domain/value_objects/service_order_status.py`](../../../app/domain/value_objects/service_order_status.py) |
| Entidade | [`domain/entities/service_order.py`](../../../app/domain/entities/service_order.py) |
| Notificações | [`infrastructure/notifications/notifier.py`](../../../app/infrastructure/notifications/notifier.py) |
| Métricas | [`infrastructure/observability/metrics.py`](../../../app/infrastructure/observability/metrics.py) |
