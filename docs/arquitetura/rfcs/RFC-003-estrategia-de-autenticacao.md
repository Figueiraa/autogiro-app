# RFC-003: Estratégia de autenticação — CPF, Lambda, JWT e Kong

- **Status:** Aprovada
- **Data:** 2026-09-07
- **Autor:** Pedro Figueira

## Resumo

Esta RFC define a estratégia de autenticação do AutoGiro, atendendo a duas exigências do enunciado
da Fase 3: "proteger rotas sensíveis com autenticação via CPF" e implementar uma "Function
Serverless para validar o CPF, consultar a existência e o status do cliente na base, e
gerar/devolver um token JWT".

A solução distribui a responsabilidade entre **três atores desacoplados**, unidos apenas pelo
padrão JWT e por um segredo HS256 compartilhado:

1. **AWS Lambda (`autogiro-auth`)** — valida o CPF pelos dígitos verificadores, consulta o cliente
   na base e **emite** o token.
2. **Kong Gateway** — **valida a assinatura** pelo plugin `jwt` antes de rotear, usando a claim
   `iss` como chave de busca do segredo do `KongConsumer`.
3. **API FastAPI (`autogiro-app`)** — **revalida** a assinatura e resolve o cliente por `cpf_cnpj`.

Nenhum dos três conhece os outros: o emissor pode ser trocado sem tocar no validador, e vice-versa.

## Motivação

O modelo de autenticação da Fase 2 era `username` + senha contra a tabela `users`, que representa a
operação interna da oficina (atendentes e mecânicos). A Fase 3 muda o sujeito autenticado: quem se
autentica é o **cliente da oficina**, identificado pelo **CPF**, registrado em `clients`.

Isso levanta três questões de projeto. **Quem valida o CPF?** O PDF é explícito: uma função
serverless — que é também o desenho natural, já que a validação é stateless e tem carga em rajada
nos picos de login. **Quem valida o token nas rotas protegidas?** A resposta ingênua é "a API", mas
o projeto já tem um API Gateway obrigatório na frente, e rejeitar tokens inválidos na borda evita
que requisições sem credencial cheguem ao cluster. **Como não acoplar emissor e validador?** A
Lambda roda na AWS e o Kong roda no cluster kind local (ver RFC-001); se um precisasse chamar o
outro, a arquitetura híbrida quebraria — exigiria que o cluster local fosse alcançável pela
internet, o que não é.

## Análise das alternativas

### Onde validar o CPF e emitir o token

| Alternativa | Prós | Contras | Veredito |
|---|---|---|---|
| **Lambda dedicada** | Atende ao requisito literal do PDF; stateless; escala sob rajada; free tier permanente (1M req/mês) | Cold start (~1s); segredo replicado | **Adotada** |
| Endpoint na própria API | Um lugar só; sem cold start | Não atende ao requisito de função serverless | Descartada como principal — mantida como espelho (ver Decisão) |
| Identidade gerenciada (Cognito, Auth0) | Rotação de chaves, MFA, fluxos prontos | Não suporta CPF como credencial primária sem custom flow; free tiers com prazo; foge do requisito de escrever a função | Descartada |

### Onde validar a assinatura do token

| Alternativa | Prós | Contras | Veredito |
|---|---|---|---|
| **Kong (plugin `jwt`) + revalidação na API** | Rejeita na borda; a API funciona sem gateway (Docker Compose, testes) | Validação em dois pontos | **Adotada** |
| Só no Kong | Sem duplicação | A API fica indefesa se acessada diretamente ou executada localmente sem gateway | Descartada |
| Só na API | Simples | Requisições sem credencial atravessam o gateway e consomem o cluster | Descartada |

### Algoritmo de assinatura: HS256 vs. RS256

É a decisão mais debatível desta RFC, e vale ser honesto sobre ela:

| Critério | HS256 (adotado) | RS256 |
|---|---|---|
| Modelo de confiança | Segredo **simétrico**: quem valida também pode emitir | Assimétrico: o validador só tem a pública e **não pode** emitir |
| Superfície de exposição | O mesmo segredo vive em três locais: Lambda, `KongConsumer` e API | A chave privada vive somente no emissor |
| Distribuição de chaves | Um secret no GitHub Actions, propagado por Terraform | Exige JWKS público ou distribuição da chave pública |
| Viabilidade no cenário híbrido | Simples: segredo injetado como secret do Kubernetes | O Kong precisaria alcançar um JWKS que a Lambda hospedasse |
| Rotação de chave | Coordenada nos três atores simultaneamente | Independente e menos disruptiva |

**RS256 é a escolha mais correta em termos de segurança** — separa emissão de validação por
construção. Adotamos HS256 mesmo assim por três razões: (a) os três atores estão sob o mesmo
controle administrativo, então um validador comprometido forjando tokens não introduz um adversário
novo; (b) hospedar um JWKS acessível ao cluster local adicionaria um componente público que a
estratégia de custo zero evita; (c) o plugin `jwt` do Kong suporta ambos, então migrar para RS256 é
troca de configuração, não de arquitetura. Fica registrado como dívida técnica consciente.

### Discriminar CPF inválido de CPF não cadastrado

| Alternativa | Resposta | Efeito colateral |
|---|---|---|
| Mensagens distintas (`400` para formato, `404` para inexistente) | Mais informativa para o cliente legítimo | Transforma o endpoint em um **oráculo de enumeração**: um atacante descobre quais CPFs estão cadastrados na base — dado pessoal sensível sob a LGPD |
| **Resposta única `401`** | Menos informativa | Elimina a enumeração |

## Decisão

### Ator 1 — Lambda `autogiro-auth` (emissor)

Recebe `{"cpf": "..."}`, com ou sem máscara, e executa:

1. **Valida o CPF pelos dois dígitos verificadores** (módulo 11, em `src/cpf.py`): normaliza
   removendo tudo que não é dígito, exige exatamente 11 dígitos e **rejeita sequências repetidas**
   (`111.111.111-11` e as outras nove), que passam no cálculo do dígito verificador mas são
   inválidas por convenção da Receita Federal.
2. **Consulta a existência do cliente** em `clients.cpf_cnpj` — coluna com índice único e `CHECK`
   que garante apenas dígitos, sem máscara (ver RFC-002). A conexão `psycopg` é criada fora do
   handler para ser reaproveitada entre invocações no mesmo execution environment.
3. **Assina o JWT em HS256** com o payload:

| Claim | Valor | Consumidor |
|---|---|---|
| `sub` | CPF normalizado | A API, para resolver o cliente |
| `iss` | `"autogiro-auth"` | O Kong, como chave de busca do segredo |
| `exp` / `iat` | Expiração e emissão | O Kong (`claims_to_verify: ["exp"]`) |
| `client_id`, `name` | Identificação do cliente | Conveniência do consumidor |

| Situação | HTTP | Corpo |
|---|---|---|
| CPF ausente | `400` | `"O campo 'cpf' é obrigatório"` |
| CPF com dígitos verificadores inválidos | `401` | `"CPF inválido ou não cadastrado"` |
| CPF válido, mas **não cadastrado** | `401` | `"CPF inválido ou não cadastrado"` — **mensagem idêntica** |
| Falha ao consultar o banco | `503` | `"Serviço temporariamente indisponível"` |
| Sucesso | `200` | `access_token`, `token_type: bearer`, `expires_in` |

Os dois casos de `401` retornam **exatamente a mesma resposta**, deliberadamente: distinguir "CPF
malformado" de "CPF não cadastrado" permitiria a um atacante varrer CPFs válidos e descobrir quais
pertencem a clientes da rede. Os casos são diferenciados apenas nos logs internos.

### Ator 2 — Kong Gateway (validador de borda)

O plugin `jwt` valida a assinatura antes de rotear, configurado com `key_claim_name: "iss"`. No
Kong, uma credencial JWT pertence a um `KongConsumer`, e a claim `iss` do token precisa casar com o
campo `key` da credencial — é assim que o Kong descobre qual segredo usar:

| Recurso | Valor |
|---|---|
| `KongConsumer` | `autogiro-auth` — representa a Lambda como emissora |
| Secret com label `konghq.com/credential: jwt` | `key = autogiro-auth`, `secret = <HS256>`, `algorithm = HS256` |
| `KongPlugin` `autogiro-jwt` | `header_names: ["Authorization"]`, `claims_to_verify: ["exp"]`, `key_claim_name: "iss"` |

O plugin é aplicado via annotation `konghq.com/plugins: autogiro-jwt` no Ingress da aplicação.
Nenhum `anonymous` consumer é configurado: requisição sem token válido recebe `401` na borda. O
Kong valida **pela assinatura**, sem conhecer quem emitiu — é esse desacoplamento que permite unir
a Lambda gratuita da AWS ao Kong open source no cluster local.

### Ator 3 — API FastAPI (revalidação e resolução)

`get_current_client` extrai o Bearer token via `HTTPBearer`, chama `decode_access_token` (que
**revalida a assinatura**) e resolve o cliente por `cpf_cnpj`, normalizando para apenas dígitos. A
revalidação **não é redundância desnecessária**: em execução local — Docker Compose, testes de
integração — **não há Kong na frente**, e sem ela a API estaria completamente aberta nesses
cenários. Assinatura válida cujo `sub` não corresponde a nenhum cliente retorna `401`, não `404`: o
token é criptograficamente íntegro, mas o sujeito não pode ser autenticado.

### Endpoint espelho `POST /api/v1/auth/token`

A API expõe `POST /api/v1/auth/token` com o **mesmo contrato de entrada e saída** da Lambda. A
razão é pragmática e declarada abertamente: permite executar e demonstrar o sistema ponta a ponta
**sem depender da AWS** — Docker Compose local, testes de integração e demonstração em vídeo com o
cluster isolado. A rota compartilha a mesma emissão (`create_access_token`), o mesmo segredo e a
mesma claim `iss`, então os tokens são intercambiáveis: um token emitido pela Lambda é aceito pela
API e vice-versa. A Lambda permanece o caminho canônico do requisito.

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| **HS256: qualquer detentor do segredo pode forjar tokens** | Kong e API poderiam emitir tokens válidos | Todos os atores estão sob o mesmo controle administrativo; segredo distribuído apenas por secrets do GitHub Actions e do Kubernetes, nunca versionado; migração para RS256 é troca de configuração no plugin `jwt`, registrada como dívida técnica |
| Segredo replicado em três lugares | Rotação exige coordenação simultânea | Terraform é a fonte única (`var.jwt_secret`); a rotação é um `apply` coordenado, documentado no README do `autogiro-infra-k8s` |
| Ausência de revogação de token | Um token vazado é válido até expirar | Expiração curta (`ACCESS_TOKEN_EXPIRE_MINUTES`, padrão 60 min); denylist foi descartada por exigir estado compartilhado, incompatível com o custo zero |
| CPF como credencial única, sem segundo fator | O CPF não é secreto | Limitação assumida — é o requisito literal do PDF. Não é adequado a produção real; um sistema de produção exigiria OTP ou senha adicional |
| Enumeração de CPF por diferença de **latência** | Consulta ao banco só ocorre para CPF válido, o que cria diferença de tempo mensurável | Não mitigado na Lambda. A API já usa hash descartável (`_DUMMY_HASH`) para tempo constante no fluxo de senha; o mesmo padrão deve ser estendido ao fluxo por CPF |
| Ausência de rate limiting no endpoint de autenticação | Força bruta sobre o espaço de CPFs | O Kong OSS tem plugin `rate-limiting` disponível e não configurado; recomendado como próximo passo — na Lambda, o limite de concorrência da conta é a única barreira atual |
| Cold start da Lambda (~1s) | Latência na primeira autenticação | Conexão ao banco reaproveitada entre invocações; provisioned concurrency descartada por gerar custo |
| Endpoint espelho amplia a superfície de autenticação | Duas portas de emissão | Contrato, segredo e política de resposta são idênticos, então não há divergência de comportamento; a rota pode ser desabilitada por configuração em produção |

## Referências

- `autogiro-auth/src/handler.py` — Handler da Lambda: fluxo, contrato de respostas e emissão do JWT
- `autogiro-auth/src/cpf.py` — Validação por dígitos verificadores (módulo 11) e rejeição de sequências repetidas
- `autogiro-auth/terraform/` — Lambda, Function URL, IAM role e layer (`psycopg`/`PyJWT`)
- `autogiro-infra-k8s/terraform/kong-jwt.tf` — `KongConsumer`, credencial JWT e `KongPlugin` `autogiro-jwt`
- `autogiro-app/app/interfaces/http/dependencies.py` — `get_current_client` e revalidação da assinatura
- `autogiro-app/app/infrastructure/security/security.py` e
  `app/interfaces/http/controllers/auth_controller.py` — emissão local e endpoint espelho
- Tech Challenge Fase 3 (13SOAT) — requisitos de autenticação por CPF e de função serverless
- Documentação do plugin `jwt` do Kong — `key_claim_name` e credenciais de Consumer
- RFC-001 (escolha da nuvem) e RFC-002 (escolha do banco)
