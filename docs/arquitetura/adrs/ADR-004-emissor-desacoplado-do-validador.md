# ADR-004: Emissor (Lambda) desacoplado do validador (Kong) via JWT

- **Status:** Aceita
- **Data:** 2026-09-07
- **Decisores:** Pedro Figueira

## Contexto

A restrição de custo zero levou a uma stack híbrida: a análise de custo mostrou que **a
Lambda é o único serviço da AWS aproveitável** (1M requisições/mês, free tier permanente),
enquanto o API Gateway da AWS tem free tier de apenas 12 meses. O gateway escolhido foi o
**Kong Gateway OSS**, que roda no próprio cluster, é open source e não limita chamadas.

Isso cria um problema de integração: o componente que **emite** a credencial de acesso
está na AWS e o que a **valida** está num cluster local. Pertencem a repositórios
diferentes (ver ADR-003), têm ciclos de deploy diferentes e não compartilham rede, runtime
ou plano de controle. Uma integração em que um consultasse o outro — introspecção,
endpoint de validação, plugin proprietário — recriaria o acoplamento que a escolha híbrida
busca evitar e colocaria uma dependência de rede no caminho de cada requisição.

## Decisão

**A Lambda emite o JWT; o Kong valida o JWT. Nenhum dos dois conhece a existência do
outro.** O contrato entre eles é composto por exatamente dois elementos:

1. O **segredo HS256** compartilhado.
2. A **claim `iss`**, com o valor `autogiro-auth`.

### Do lado emissor — `autogiro-auth/src/handler.py`

A função `_issue_token` monta o payload com `sub` (CPF normalizado), `client_id`, `name`,
`iat`, `exp` e `iss: "autogiro-auth"`, e assina com
`jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")`. O handler não conhece
o endereço do Kong nem o cluster, e não chama nada além do banco.

### Do lado validador — `autogiro-infra-k8s/terraform/kong-jwt.tf`

O mecanismo é o do Kong ensinado na aula de **Consumers**:

- Um **`KongConsumer`** chamado `autogiro-auth` representa a Lambda como emissora.
- Suas **credenciais** são um `Secret` do Kubernetes (`autogiro-jwt-credential`) rotulado
  `konghq.com/credential: jwt`, com três campos: `key = var.jwt_issuer` (default
  `autogiro-auth`), `secret = var.jwt_secret` e `algorithm = "HS256"`.
- Um **`KongPlugin`** chamado `autogiro-jwt` configura `plugin = "jwt"` com
  `header_names = ["Authorization"]`, `claims_to_verify = ["exp"]` e — o ponto central —
  **`key_claim_name = "iss"`**.

É essa última configuração que fecha o desacoplamento: ao receber um token, o Kong lê a
claim `iss`, procura entre as credenciais JWT cadastradas aquela cujo campo **`key`** casa
com esse valor e usa o `secret` dessa credencial para verificar a assinatura. **A claim
`iss` é a chave de busca do segredo.** O Kong não precisa saber que existe uma Lambda —
sabe que existe um Consumer cuja `key` é `autogiro-auth`.

O plugin é aplicado pela annotation `konghq.com/plugins: autogiro-jwt` no Ingress de
`/api/v1` (`autogiro-app/k8s/ingress.yaml`). O `anonymous` é deixado sem definição: como
registra o comentário no `kong-jwt.tf`, um consumer anônimo faria a requisição sem token
seguir adiante, o oposto do desejado — sem ele, a resposta é 401.

### Defesa em profundidade na aplicação

A API **revalida** a assinatura em `app/interfaces/http/dependencies.py`, via
`decode_access_token`, em vez de confiar cegamente no gateway: o motivo está no próprio
módulo — em execução local (Docker Compose, testes) não há Kong na frente. O `HTTPBearer`
substituiu o `OAuth2PasswordBearer` porque não existe mais login com usuário e senha.

## Consequências

### Positivas

- **Permite combinar a Lambda gratuita da AWS com o Kong open source.** É a consequência
  que justifica a decisão: dois componentes de fornecedores e planos de controle distintos
  cooperam unidos só pelo padrão JWT, viabilizando a stack de custo zero sem perda
  funcional.
- **Validação local, sem chamada de rede.** O Kong verifica a assinatura com o segredo que
  já tem em mãos: nenhuma introspecção, nenhuma latência adicional na requisição, e a
  validação não cai se a AWS estiver inacessível.
- **Emissor substituível.** Trocar a Lambda por outro emissor (outra nuvem, um serviço no
  cluster, um script de teste) não exige mudança no Kong, desde que assine com o mesmo
  segredo e emita `iss: autogiro-auth`. O inverso vale: trocar o Kong por outro gateway
  compatível com JWT não afeta a Lambda.
- **Política declarada em um lugar e testável.** Consumer, credencial e plugin são
  recursos do Kubernetes criados por Terraform, versionados e auditáveis; adicionar um
  segundo emissor é adicionar um Consumer com outra `key`. E como o contrato é só o segredo
  e a claim, um token válido pode ser gerado em teste sem levantar Lambda nem Kong.

### Negativas

- **Segredo compartilhado, e não par de chaves.** HS256 é simétrico: a **mesma** chave
  assina e verifica, o que obriga os dois lados a guardar o mesmo segredo — `JWT_SECRET` na
  Lambda e a variável `jwt_secret` de `kong-jwt.tf` (`sensitive = true`, gravada num
  `Secret` do Kubernetes). Como estão em repositórios diferentes, o valor é cadastrado duas
  vezes como secret do GitHub.
- **RS256 seria melhor, mas exigiria distribuição de chave pública ou JWKS.** Com um par
  assimétrico, só a Lambda teria a chave privada e o Kong apenas a pública — quem valida
  perderia a capacidade de emitir. O custo é operacional: publicar e manter um endpoint
  JWKS ou distribuir e rotacionar o certificado até o Kong, processo que hoje não existe.
  O HS256 é um trade-off consciente; RS256 é a evolução natural desta decisão.
- **Quem valida também pode emitir.** Consequência direta da simetria: comprometer o
  `Secret` no cluster permite forjar tokens, não apenas verificá-los. E a rotação é
  coordenada e não atômica — exige apply nos dois repositórios, e na janela entre eles os
  tokens com o segredo antigo são rejeitados.
- **Contrato não verificado automaticamente.** Se a Lambda emitir outro `iss`, ou se o
  `jwt_issuer` do Terraform divergir, o Kong não encontra credencial e responde 401 — a
  falha aparece em runtime, não no build.

## Alternativas consideradas

| Alternativa | Avaliação |
|---|---|
| **RS256 / par de chaves com JWKS** | Tecnicamente superior: separa a capacidade de emitir da de validar. Descartada nesta fase pelo custo operacional de publicar e rotacionar a chave pública até o Kong, sem processo estabelecido — e por não trazer ganho funcional para a entrega. Registrada como a evolução recomendada. |
| **AWS API Gateway com authorizer da própria Lambda** | Manteria emissor e validador no mesmo fornecedor, com integração nativa. Descartada porque o free tier do API Gateway dura apenas 12 meses, o que viola a restrição de custo zero permanente. |
| **Kong com introspecção do token na Lambda** | Traria validação centralizada no emissor, ao custo de uma chamada de rede à AWS em cada requisição: latência somada ao cold start (~1s) e o gateway passando a depender da disponibilidade da AWS. |
| **Kong OIDC / OAuth2 com provedor de identidade** | Padrão mais completo (fluxos, refresh, revogação). Descartada por exigir provedor de identidade externo e por o plugin OIDC não estar na edição open source do Kong. |
