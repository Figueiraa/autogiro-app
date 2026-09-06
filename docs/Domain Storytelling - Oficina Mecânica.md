# Domain Storytelling — Sistema Integrado de Oficina Mecânica

---

## Contexto

Uma oficina mecânica de médio porte opera hoje com processos manuais: anotações em papel, planilhas descoordenadas e comunicação verbal. Isso gera erros na priorização, perda de histórico, falhas no estoque e ineficiência no fluxo de orçamentos. O objetivo é mapear essas histórias para desenhar um sistema que resolva esses problemas.

---

## Glossário do Domínio

| Termo | Definição |
|---|---|
| OS (Ordem de Serviço) | Documento central que registra o atendimento: cliente, veículo, serviços, peças e status |
| Orçamento | Valor calculado a partir dos serviços e peças da OS, enviado ao cliente para aprovação |
| Status da OS | Fase atual do atendimento: Recebida → Em diagnóstico → Aguardando aprovação → Em execução → Finalizada → Entregue |
| Insumos | Materiais consumíveis utilizados durante a execução (óleo, fluidos, etc.) |

---

## Atores

| Símbolo | Ator | Descrição |
|---|---|---|
| `[CLIENTE]` | Cliente | Proprietário do veículo. Aprova orçamentos e acompanha o status |
| `[RECEPCIONISTA]` | Recepcionista | Primeiro contato com o cliente. Abre, documenta e encerra OSs |
| `[MECÂNICO]` | Mecânico | Executa os serviços e atualiza o progresso da OS |
| `[ADMINISTRADOR]` | Administrador | Gerencia operações, estoque e monitora a performance da oficina |
| `[SISTEMA]` | Sistema | A aplicação que automatiza o fluxo, calcula orçamentos e controla status |

---

## Objetos de Trabalho

| Símbolo | Objeto | Descrição |
|---|---|---|
| `{OS}` | Ordem de Serviço | Documento digital que guia todo o ciclo de atendimento |
| `{CLIENTE}` | Cadastro de Cliente | Dados identificadores: CPF/CNPJ, nome, contato |
| `{VEÍCULO}` | Cadastro de Veículo | Placa, marca, modelo, ano — vinculado ao cliente |
| `{ORÇAMENTO}` | Orçamento | Totalização automática de serviços e peças |
| `{PEÇAS}` | Peças / Insumos | Itens do estoque consumidos na execução |
| `{STATUS}` | Status da OS | Estado atual do atendimento no ciclo de vida |
| `{HISTÓRICO}` | Histórico de Serviços | Registro acumulado de OSs anteriores do veículo |

---

## Subdomínios Identificados

```
┌─────────────────────────────────────────────────────────────┐
│                    CORE DOMAIN                              │
│                                                             │
│   ┌──────────────────────┐   ┌──────────────────────────┐  │
│   │  Atendimento ao      │   │  Execução de Serviços    │  │
│   │  Cliente             │   │                          │  │
│   │  - Cadastro cliente  │   │  - Ciclo de vida da OS   │  │
│   │  - Cadastro veículo  │   │  - Atualização de status │  │
│   │  - Abertura de OS    │   │  - Acompanhamento        │  │
│   │  - Orçamento         │   │    em tempo real         │  │
│   │  - Aprovação         │   │                          │  │
│   └──────────────────────┘   └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  SUPPORTING DOMAINS                         │
│                                                             │
│   ┌──────────────────────┐   ┌──────────────────────────┐  │
│   │  Gestão de Estoque   │   │  Gestão Administrativa   │  │
│   │                      │   │                          │  │
│   │  - Peças e insumos   │   │  - Listagem de OSs       │  │
│   │  - Controle de       │   │  - Tempo médio de        │  │
│   │    disponibilidade   │   │    execução              │  │
│   │  - Baixa automática  │   │  - CRUDs de suporte      │  │
│   └──────────────────────┘   └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Narrativas

> As narrativas seguem a notação:
> `① [ATOR] ──(atividade)──▶ {Objeto}` ou `──▶ [ATOR]`
>
> Números iguais indicam ações paralelas. Anotações aparecem como `« nota »`.

---

### História 1 — AS IS: Abertura Manual de Ordem de Serviço

> **Versão atual da realidade.** Como a oficina opera hoje, sem sistema integrado.

**Atores envolvidos:** `[CLIENTE]`, `[RECEPCIONISTA]`, `[MECÂNICO]`

```
① [CLIENTE] ──(chega com o veículo)──▶ [RECEPCIONISTA]

② [RECEPCIONISTA] ──(anota em papel / planilha)──▶ {dados do cliente e veículo}
   « sem validação de CPF/CNPJ ou placa; erros são comuns »

③ [RECEPCIONISTA] ──(descreve verbalmente os problemas)──▶ [MECÂNICO]

④ [MECÂNICO] ──(verifica fisicamente no estoque)──▶ {peças disponíveis}
   « sem controle digital; frequente falta de peças não percebida »

⑤ [RECEPCIONISTA] ──(elabora manualmente)──▶ {orçamento no papel}
   « cálculos sujeitos a erros; sem histórico »

⑥ [RECEPCIONISTA] ──(liga ou manda mensagem)──▶ [CLIENTE]
   « aprovação verbal, sem registro formal »

⑦ [CLIENTE] ──(aprova verbalmente)──▶ [RECEPCIONISTA]

⑧ [RECEPCIONISTA] ──(avisa verbalmente)──▶ [MECÂNICO]
   « risco de OS perdida na fila ou esquecida »

⑨ [MECÂNICO] ──(executa o serviço)──▶ {veículo}
   « sem acompanhamento de progresso para o cliente »

⑩ [RECEPCIONISTA] ──(registra encerramento manualmente)──▶ {planilha}
   « histórico fragmentado; difícil de consultar no futuro »
```

**Problemas evidenciados nesta história:**
- Nenhum canal formal de aprovação de orçamento
- Sem controle de estoque em tempo real
- Histórico do cliente e veículo se perde com o tempo
- Cliente não consegue acompanhar o status sem ligar
- Erros na priorização quando há múltiplos veículos

---

### História 2 — TO BE: Abertura de Ordem de Serviço com o Sistema

> **Nova realidade.** O Recepcionista usa o sistema para abrir e documentar a OS com todas as informações necessárias.

**Atores envolvidos:** `[RECEPCIONISTA]`, `[CLIENTE]`, `[SISTEMA]`

```
① [CLIENTE] ──(chega com o veículo)──▶ [RECEPCIONISTA]

② [RECEPCIONISTA] ──(busca pelo CPF/CNPJ)──▶ {CLIENTE}
   « se não encontrado, cadastra o novo cliente »

③ [RECEPCIONISTA] ──(seleciona ou cadastra)──▶ {VEÍCULO}
   « placa, marca, modelo, ano — vinculado ao cadastro do cliente »

④ [RECEPCIONISTA] ──(adiciona serviços à OS)──▶ {OS}
   « ex: troca de óleo, alinhamento »

⑤ [RECEPCIONISTA] ──(adiciona peças e insumos)──▶ {OS}
   « sistema verifica disponibilidade no estoque »

⑥ [SISTEMA] ──(calcula automaticamente)──▶ {ORÇAMENTO}
   « totalização de serviços + peças; sem intervenção manual »

⑦ [SISTEMA] ──(envia para aprovação)──▶ [CLIENTE]
   « OS muda para status "Aguardando Aprovação" »

⑧ [CLIENTE] ──(aprova o orçamento)──▶ {OS}
   « aprovação registrada no sistema; gera trilha de auditoria »

⑨ [SISTEMA] ──(atualiza automaticamente)──▶ {STATUS}
   « OS passa para "Em Execução"; notifica mecânicos disponíveis »
```

---

### História 3 — TO BE: Execução e Acompanhamento em Tempo Real

> **Nova realidade.** O Mecânico conduz a execução e o Cliente acompanha o progresso diretamente.

**Atores envolvidos:** `[MECÂNICO]`, `[CLIENTE]`, `[SISTEMA]`

```
① [MECÂNICO] ──(consulta a fila de OSs aprovadas)──▶ {OS}

② [MECÂNICO] ──(inicia o diagnóstico)──▶ {OS}
   « status muda para "Em diagnóstico" »

③ [MECÂNICO] ──(confirma e inicia a execução)──▶ {OS}
   « status muda para "Em execução" »

④ [CLIENTE] ──(consulta via API)──▶ {STATUS}
   « acompanha o progresso sem precisar ligar para a oficina »

⑤ [MECÂNICO] ──(conclui o serviço)──▶ {OS}
   « status muda para "Finalizada" »

⑥ [SISTEMA] ──(registra no histórico)──▶ {HISTÓRICO}
   « serviços executados ficam vinculados ao veículo »

⑦ [RECEPCIONISTA] ──(registra a retirada do veículo)──▶ {OS}
   « status final: "Entregue" »
```

---

### História 4 — TO BE: Gestão Administrativa

> **Nova realidade.** O Administrador monitora a operação e gerencia os recursos da oficina pelo sistema.

**Atores envolvidos:** `[ADMINISTRADOR]`, `[SISTEMA]`

```
① [ADMINISTRADOR] ──(autentica via JWT)──▶ [SISTEMA]
   « acesso restrito às rotas administrativas »

② [ADMINISTRADOR] ──(consulta listagem)──▶ {OS}
   « filtra por status: abertas, em execução, finalizadas »

③ [ADMINISTRADOR] ──(monitora)──▶ {tempo médio de execução}
   « identifica gargalos operacionais »

④ [ADMINISTRADOR] ──(verifica disponibilidade)──▶ {PEÇAS}
   « controle de estoque em tempo real »

⑤ [ADMINISTRADOR] ──(cadastra, atualiza ou remove)──▶ {PEÇAS}
⑤ [ADMINISTRADOR] ──(cadastra, atualiza ou remove)──▶ {CLIENTE}
⑤ [ADMINISTRADOR] ──(cadastra, atualiza ou remove)──▶ {VEÍCULO}
   « operações paralelas de gestão dos cadastros »
```

---

## Ciclo de Vida da OS — Visão Consolidada

```
         [RECEPCIONISTA]          [CLIENTE]            [MECÂNICO]
               │                     │                     │
               ▼                     │                     │
         ┌─────────┐                 │                     │
         │Recebida │                 │                     │
         └────┬────┘                 │                     │
              │                      │                     │
              ▼                      │                     │
      ┌───────────────┐              │                     │
      │Em Diagnóstico │◄─────────────┼─────────────────────┤
      └───────┬───────┘              │                     │
              │                      │                     │
              ▼                      │                     │
   ┌──────────────────────┐          │                     │
   │Aguardando Aprovação  │──────────▶                     │
   └──────────┬───────────┘    aprova orçamento            │
              │                      │                     │
              ▼                      │                     │
       ┌─────────────┐               │                     │
       │Em Execução  │◄──────────────┼─────────────────────┤
       └──────┬──────┘               │              executa serviço
              │                      │                     │
              ▼                      │                     │
        ┌──────────┐                 │                     │
        │Finalizada│◄────────────────┼─────────────────────┘
        └─────┬────┘                 │
              │                      │
              ▼                      │
        ┌──────────┐                 │
        │ Entregue │◄────────────────┘
        └──────────┘          retira veículo
```

---

## AS IS vs. TO BE — Comparativo

| Aspecto | AS IS (Hoje) | TO BE (Sistema) |
|---|---|---|
| Cadastro de clientes | Papel / planilha | Sistema com validação de CPF/CNPJ |
| Cadastro de veículos | Anotação manual | Sistema com validação de placa |
| Geração de orçamento | Manual, sujeito a erros | Automático pelo Sistema |
| Aprovação do cliente | Verbal (telefone) | Digital, com registro formal |
| Acompanhamento da OS | Cliente liga para saber | Consulta direta via API |
| Controle de estoque | Verificação física | Controle digital em tempo real |
| Histórico de serviços | Planilhas fragmentadas | Histórico vinculado ao veículo |
| Acesso administrativo | Sem controle de acesso | Autenticação JWT |

---

## Anotações e Restrições do Domínio

- A OS só avança para **Em Execução** após aprovação formal do cliente.
- O Sistema deve impedir a criação de OS com peças indisponíveis no estoque, ou ao menos alertar o Recepcionista.
- O histórico de serviços é imutável: OSs finalizadas não podem ser alteradas retroativamente.
- A consulta de status pelo Cliente é pública (não requer autenticação); as rotas de gestão são protegidas por JWT.
- Cada OS pertence a exatamente um veículo, e cada veículo pertence a exatamente um cliente.
