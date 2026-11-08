# Elmo

**O Elmo encontra os furos nas fichas de EPI de uma construtora e cobra a correção antes do fiscal, do advogado ou do acidente.**

Um agente de IA audita, de forma preventiva, as fichas de entrega de EPI (equipamento de proteção individual). Ele cruza cada entrega com a base oficial de CAs do Ministério do Trabalho e com o que a função exige, cria tarefas com prazo para o técnico de segurança, pede documentos ao RH, percebe sozinho quando a planilha é corrigida e fecha a tarefa. O passivo que não tem conserto vira um valor em R$.

Feito no Converge Challenge (Porto Digital, Recife, 7 e 8/11/2026). No código, o projeto ainda se chama `heitor` (pacote `heitor/`, variáveis `HEITOR_*`).

> O Elmo aponta lacunas na **prova documental**. Ele não afirma se há insalubridade: quem a caracteriza é a perícia (art. 195 da CLT).

## Por que existe

Na Justiça do Trabalho, cabe à empresa provar que protegeu o trabalhador. A ficha de EPI prova a entrega, não a proteção: falta assinatura, o CA venceu, a troca atrasou, o EPI exigido nunca foi entregue. Quando a ficha não prova, a construtora paga o adicional de insalubridade retroativo, por até 5 anos (Súmulas 80 e 289 do TST). Insalubridade foi o assunto mais recorrente nas novas ações da Justiça do Trabalho em 2024.

## Como funciona

```
Gatilho (vigia do Drive, upload, prazo vencido; código, sem LLM)
   → Leitura (planilha; foto e PDF da ficha de papel pelo modelo de visão)
   → Agente, um episódio por funcionário (LangGraph): o LLM escolhe as ferramentas
   → Rede de segurança (o código faz o que o LLM deixou para trás)
   → Saídas: pendências com prazo, relatório com a base legal, exposição em R$, log de cada passo
   → Técnico corrige na planilha → nova auditoria → a pendência fecha se o problema sumiu
```

**O LLM decide o caminho; as regras decidem a verdade.** O LLM escolhe o que investigar, se vale conferir a ficha de papel, a urgência de cada correção e o texto da ação. Só as regras determinísticas dizem o que é falha. Com ou sem LLM, a auditoria acha as mesmas falhas.

O que o Elmo nunca faz, garantido por código e testes: sugerir assinar, preencher ou alterar ficha antiga (fraude documental); mandar retirar um EPI; trocar um CA ou uma data lida; alterar a ficha ou a pasta; travar quando o LLM cai.

## Rodar localmente

Requisitos: Python 3.12 e uma chave do [Featherless](https://featherless.ai) (os modelos rodam lá).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # preencha FEATHERLESS_API_KEY; o resto é opcional
uvicorn heitor.api.main:app --reload --port 8000   # documentação em http://localhost:8000/docs
```

- **Base de CAs do MTE:** coloque o relatório do CAEPI (`RelatorioCA_*.csv`, ~144 MB) em `dados/`. Fica fora do Git. Sem ela, a API sobe, mas a auditoria não consegue checar os CAs (a ficha vira pendência de revisão manual) e os testes que dependem dela são pulados.
- **Dados de exemplo:** `POST /auditorias` com `exemplo=true` roda a auditoria numa construtora fictícia.
- **Sem LLM:** `HEITOR_LLM=off` roda só com as regras (mesmas falhas, sem as decisões do agente).
- **Vigia de pasta:** `HEITOR_DRIVE_PASTA` + `HEITOR_DRIVE_CREDENCIAIS` (Google Drive, conta de serviço com acesso de Leitor) ou `HEITOR_FONTE_PASTA` (pasta local).
- **E-mail:** sem `SMTP_HOST`, os avisos só aparecem no log.
- **Deploy público:** preencha `HEITOR_TOKEN_ADMIN`; `POST /demo/reset` só existe com `HEITOR_DEMO=1`.

A interface (React + Vite) está em `heitor/web/` na branch `frontend`: `cd heitor/web && npm install && npm run dev`.

## Testes

```bash
bash scripts/antes_do_pr.sh        # testes + E2E do roteiro da demo (roda antes de todo PR)
bash scripts/antes_do_pr.sh --ia   # inclui o E2E com IA (foto real, custa centavos)
python -m tests.eval_agente        # comportamento do agente com o LLM (~2 min, ~US$ 0,03)
```

Números medidos (sempre com a amostra):

| O que | Resultado | Amostra |
| --- | --- | --- |
| Entrega sem assinatura passando como assinada | nenhuma (6 de 6 pegas) | 89 entregas de 11 fichas de papel, gabarito à mão |
| Assinaturas válidas confirmadas automaticamente | 69 de 76 | idem |
| Comportamentos esperados do agente | 16 de 16 | 7 funcionários da demo, 2 com foto |
| Mesmas falhas com e sem LLM | 8 = 8 | 12 funcionários da demo |
| Custo de IA | ~US$ 0,004 por funcionário + ~US$ 0,005 por foto | auditorias da demo |

## Estrutura

| Pasta | Dono | O que tem |
| --- | --- | --- |
| `heitor/agente/` | Sofia | O agente (LangGraph), ferramentas, leitura de planilha, foto e PDF, conferências, guarda-corpos, relatório |
| `heitor/dados/` | Gustavo | Regras de auditoria, base CAEPI, tabela função → EPI, exposição em R$ |
| `heitor/api/` | Pierre | API (FastAPI), vigia da pasta, conciliação, cobrança de prazo, e-mail, segurança |
| `heitor/web/` | Luciana | Interface (branch `frontend`) |
| `heitor/contrato.py` | todos | O contrato de dados entre os módulos (Pydantic) |

Decisões de projeto, regras e contrato completos: [`CLAUDE.md`](CLAUDE.md).

## Limitações

- A construtora e os funcionários da demo são **fictícios**; os CAs, a base do MTE e as normas são reais.
- A tabela função → EPI cobre só o **ruído** (NR-15, Anexos 1 e 2). Os EPIs de acidente existem atrás de `HEITOR_PGR=completo`, desligado por padrão.
- A foto da ficha de papel confere a assinatura e o campo de treinamento; ela não é fonte de dados (número manuscrito errava muito).
- Estado em memória: reiniciar o servidor apaga as auditorias.
- O preço do produto ainda não foi validado com clientes.
