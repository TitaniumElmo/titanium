# Deploy da API no Railway

A API roda num container (`Dockerfile`). A base CAEPI (144 MB, fora do Git) é baixada compactada, na montagem da imagem, do dataset público `ElmoAgent/caepi` no Hugging Face.

**Tamanho medido** (teste de carga em 08/11):
- RAM: ~440 MB parada com a base, ~480 MB com 15 usuários simultâneos. **Precisa de 1 GB** (512 MB não serve).
- CPU: **1 vCPU basta**. A API é um processo só, e o estado fica em memória, então mais núcleos não ajudam.
- Custo estimado: ~US$ 0,20/dia no plano Hobby (cobrança por uso).

## Ligar (primeira vez)

```bash
brew install railway          # terminal do Railway
railway login                 # abre o navegador
cd titanium
railway init                  # cria o projeto (nome: heitor)
railway up                    # envia o código e monta a imagem (~3 a 5 min)
railway domain                # gera o link público https://<algo>.up.railway.app
```

Depois, no painel do Railway → serviço → **Variables**, cadastrar as variáveis abaixo. O serviço reinicia sozinho a cada mudança.

| Variável | Valor | Obrigatória? |
|---|---|---|
| `FEATHERLESS_API_KEY` | chave do LLM | sim (sem ela, o agente roda sem LLM) |
| `HEITOR_TOKEN_ADMIN` | senha longa nova: `openssl rand -hex 24` | **sim** (protege reset e depuração) |
| `HEITOR_DEMO` | `1` só se o time quiser usar o reset; senão, não criar | não |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Gmail do Elmo (senha de app) | para e-mail |
| `HEITOR_EMAIL_TECNICO`, `HEITOR_EMAIL_RH`, `HEITOR_EMAIL_COORDENADOR` | destinatários | para e-mail |
| `HEITOR_NOME_NO_EMAIL` | `Elmo` | não |
| `HEITOR_DRIVE_PASTA` | id da pasta do Drive | para o vigia |
| `HEITOR_DRIVE_CREDENCIAIS_JSON` | **conteúdo inteiro** do `drive.json` da conta de serviço | para o vigia |
| `HEITOR_VIGIA_INTERVALO` | `3` | não (padrão 10) |

**Nunca** cadastrar `HEITOR_PRAZO_TESTE` (faz tudo vencer de uma vez) nem `HEITOR_STUBS`.

## Conferir

```bash
URL=https://<seu-dominio>.up.railway.app
curl $URL/health                        # integracao: nada "stub"; vigia: a pasta do Drive
curl -X POST $URL/demo/reset            # 404 (sem HEITOR_DEMO) ou 401 (sem token): é o esperado
curl -X POST $URL/auditorias -F exemplo=true    # 202: auditoria de exemplo
```

E abrir `$URL/docs` no navegador.

## Atualizar depois de um merge na main

```bash
git switch main && git pull
railway up
```

## Cuidados

- **Uma réplica só, sem hibernar:** o estado fica em memória. Não ativar "App Sleeping" nem aumentar as réplicas.
- **Reiniciar apaga as auditorias,** e o vigia audita a pasta inteira de novo. Não reiniciar depois de preparar a demo.
- **Vigia duplicado:** com o deploy no ar, **não** rode o servidor local com o mesmo `HEITOR_DRIVE_PASTA`. Os dois auditariam a mesma planilha e mandariam e-mails em dobro. Na máquina local, deixe `HEITOR_DRIVE_PASTA` vazio.
- **Base CAEPI nova:** subir o `.gz` no dataset `ElmoAgent/caepi` e trocar o nome no `ARG CAEPI_URL` do `Dockerfile`.
