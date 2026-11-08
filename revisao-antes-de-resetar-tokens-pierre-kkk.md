# Revisão e estado do back (Pierre), atualizado em 07/11/2026 à noite

Anotação para retomar o trabalho depois de limpar a conversa com o Claude. Junta:
- o estado do repositório;
- o que foi decidido;
- o que já foi resolvido da revisão;
- o que falta fazer.

- Revisão do código (documento para o time): https://claude.ai/artifact/LkVYMH7KhHY71Ku5L3nB4b. Foi escrita **antes** dos merges; esta anotação é mais recente.
- Gatilhos (documento): https://claude.ai/artifact/VsPZsL72YPNCnN5HDfscLf

---

## 0. Pendências por pessoa (revisão de 08/11, madrugada; `main` em `7aa3125`, PRs até o #15)

Estado da `main`: `scripts/antes_do_pr.sh` → 181 passed com a base. Sem a base, 7 testes do PGR falham até o **PR #22** entrar. Concorrência: 18 auditorias, 6 simultâneas, sem erro. Princípios 1, 2, 4, 5, 6, 7 e 8 do CLAUDE.md verificados; **o 3 (fraude) tem furo**: ver Sofia.

### Pierre (API, deploy)
- [ ] **Antes do deploy:** token nas rotas que alteram dados; `POST /demo/reset` só com `HEITOR_DEMO=1`; limite de upload (15 MB; só CSV/JPG/PNG/WEBP).
- [ ] **Deploy:** escolher Hugging Face Spaces (grátis, 16 GB, código visível) ou Railway (~US$ 5/mês). Levar a base CAEPI (144 MB, fora do Git) e os segredos (Featherless, chave do Drive, Gmail). A API usa ~400 MB.
- [ ] Mergear o **#22** (testes do PGR sem a base) ou pedir ao Gustavo.
- [ ] **Gatilho 7:** resumo diário (o e-mail agrupado já existe; dá para reaproveitar).
- [ ] Aquecer o LLM quando o servidor sobe (a primeira chamada leva ~20 s).
- [ ] Demo: `HEITOR_VIGIA_INTERVALO=3`; `construtora_ficticia.csv` na pasta do Drive, com a coluna de matrícula formatada como texto.
- [ ] Opcional: custo da leitura de foto no log; guardar o estado em arquivo.

### Sofia (agente, relatório)
- [ ] **Filtro de fraude não pega fraude** (`heitor/agente/ferramentas.py`, `_FRAUDE`), **bloqueia a demo**. Não barrou nenhuma de 5 frases fraudulentas, por exemplo "Colher a assinatura do Rafael na ficha antiga" e "Preencher o CA que falta na entrega de setembro/2023". A expressão procura "assinar" (o LLM escreve "assinatura") e exige "antiga/passada" (o LLM cita datas). O texto do LLM vai para a **tela**. → Cobrir os radicais `assin*`, `preench*`, `alter*`, `complet*`, `regulariz*` perto de `antig*`, `passad*`, `retroativ*`, `anterior*`, de uma data ou de "entrega de…"; testar com as 5 frases e com as 2 legítimas ("colher a assinatura nas próximas entregas", "entregar hoje e colher a assinatura").
- [ ] Caminho do servidor na evidência (`_falha_vira_revisao` põe a exceção no achado: "base CAEPI não encontrada em /Users/…"). → Só o tipo do erro; o detalhe vai para o log.
- [ ] `requirements.txt`: tirar `pandas` e `langfuse` (sem uso). `onnxruntime` e `numpy` só servem ao `tests/avaliar_yolo.py`.
- [ ] Linha malformada (tudo na coluna A) vira acusação. → Marcar como "linha incompleta, revisar".
- [ ] Planilha e fotos da demo (`construtora_ficticia.csv`, `fotos_teste/`) num lugar que o time e o deploy alcancem.

### Gustavo (regras, base, PGR)
- [ ] Revisar e mergear o **#22** (só marca 2 testes do PGR para pular sem a base).
- [ ] `HEITOR_PRAZO_TESTE` esquecido no servidor faz todas as pendências vencerem de uma vez. → Aviso no log quando a variável estiver ligada.
- [ ] Regra para linha sem data (hoje passa sem achado; a validade do CA não é checada).
- [ ] Responder a pergunta do #19: com o PGR ligado, o intervalo entre entregas de EPI de **acidente** também vira `troca_passado`?

### Luciana (tela)
- [ ] Ainda não há branch de frontend no GitHub. Subir o que tiver, mesmo incompleto.
- [ ] O que mudou na API para a tela:
  - `disparado_por` agora é um código (`alteracao_planilha`, `upload`, `manual`, `prazo_vencido`, `rotina`), e o texto vai em `descricao_disparo`;
  - o feed é `GET /eventos`, e os eventos `edicao_detectada` vêm com `auditoria_id: "vigia"`;
  - a pendência tem `prioridade`, `cobrancas`, `escalada`, `funcionario_nome` e `historico[].etapa/ator`;
  - cada evento de ferramenta traz `saida.resumo` (uma linha em português).
- [ ] Precisa do link do deploy para testar fora da máquina do Pierre.

### Time (decisões)
- [ ] Plataforma do deploy.
- [ ] Treinamento: entra na demo (com qual fonte?) ou sai do pitch?
- [ ] Assinatura vazia em planilha digitada: irregular ou risco?
- [ ] Demo ao vivo com quantos funcionários (com LLM, 15 a 40 s para 1 ou 2).
- [ ] `HEITOR_PRAZO_TESTE` **nunca** ligado na demo.

---

## 1. Onde as coisas estão

| Item | Estado |
|---|---|
| `main` | `de08d44`, com **todos os PRs mergeados** (#1 a #9) e nenhum aberto |
| Testes | `scripts/antes_do_pr.sh` → 114 passed, 1 skipped (o E2E com IA). Sem a base CAEPI: 65 passed, 50 skipped, nenhuma falha |
| Branches `pierre/gatilhos` e `pierre/fix-agente-autonomo` | já estão na `main`; podem ser apagadas |
| Base CAEPI | `dados/RelatorioCA_20261107_143153.csv` é um atalho para o arquivo no Downloads (144 MB, **fora do Git**) |
| Chave do Drive | `~/.config/heitor/drive.json` (conta de serviço `converge-challenge@…`, projeto Google Cloud "Elmo", Leitor na pasta "Elmo - Construtora Demo") |
| `.env` | tem `HEITOR_DRIVE_PASTA`, `HEITOR_DRIVE_CREDENCIAIS` e `HEITOR_VIGIA_INTERVALO`; SMTP vazio |

Ordem em que os PRs entraram: #1, #2, #3, #4, #8, #7 (no #6), #5, #6 (destino trocado de `visao` para `main`) e #9.

Para rodar:
```bash
source .venv/bin/activate
pip install -r requirements.txt                     # entrou o google-auth
bash scripts/antes_do_pr.sh                         # antes de qualquer PR (--ia inclui o E2E com IA e foto)
uvicorn heitor.api.main:app --reload --port 8000    # docs em /docs; /health mostra stubs e o vigia
```

---

## 2. Decisões tomadas

- **Chatbot está fora de cogitação.** O Heitor reage a acontecimentos; a tela principal é o feed do que ele fez (`GET /eventos`).
- **Gatilhos da demo: 1, 2 e 7.**
  - 1: mudança na pasta (**pronto**).
  - 2: prazo de pendência vencendo (falta).
  - 7: resumo diário (falta).
  - O 4 (nova base CAEPI) está em avaliação: a base não tem histórico.
- **Fonte das fichas:** pasta do Google Drive, lida por uma conta de serviço só com Leitor. O **vigia é código comum, sem LLM**; o agente só é acordado quando algo muda.
- **O vigia consulta a pasta periodicamente** (sem webhook do Google).
- **A foto não é fonte de dados** (decisão do time). Data, EPI e CA vêm da planilha; a foto só confere as assinaturas (`conferir_e_auditar` do agente). Por isso foi descartada a leitura da matrícula no cabeçalho da foto.
- **Base CAEPI oficial:** `RelatorioCA_*.csv` em `dados/`, a mesma para as regras e para a conferência CA × EPI.
- **Regras novas, sempre risco:** `entrega_sem_ficha` e `ficha_sem_planilha`. Também `leitura_incerta`.
- **Tabela função → EPI:** só ruído, protetor auditivo com 180 dias, nas 4 funções (PR #9).
- **Pitch:** só o caso Bazan e a Súmula 289. Dizer "assinatura compatível com o nome do funcionário", nunca "assinado pelo funcionário".
- **Sem banco de dados no hackathon.** O estado fica em memória (`heitor/api/estado.py`).
- **Pendência do RH (nota fiscal):** a versão com conferência pela data da compra foi **descartada a pedido**. A pendência do tipo `prova` continua sem caminho automático para fechar.
- **Demo (Sofia):** planilha `construtora_ficticia.csv`, com 12 funcionários. Contraste entre o 0401 (ficha limpa, 2 passos) e o 0406 (CA suspenso, pendência com prazo de 1 dia). Rodar os 12 antes e mostrar 2 ao vivo. **Essa planilha não está no Git.**

---

## 3. O que a API faz hoje (minha parte)

- **Rotas:** todas as da seção 8 do CLAUDE.md, mais:
  - `GET /auditorias` (lista, com `disparado_por`);
  - `GET /eventos` (SSE com tudo o que o Heitor faz);
  - `GET /fontes`;
  - `POST /fontes/verificar`.
- **Upload com foto:** `POST /auditorias` aceita `arquivos` (planilhas), `fotos` e `funcionarios_das_fotos`. Sem o id, vale a matrícula no nome do arquivo, ignorando zeros à esquerda. A Sofia testou com foto real (Wagner, `funcionarios_das_fotos=0313`): 10 de 10 assinaturas conferidas, sem erro.
- **Vigia do Drive** (`heitor/api/vigia.py`, `heitor/api/fontes.py`):
  - só age quando o arquivo aparece igual em duas consultas;
  - audita só os funcionários que mudaram;
  - foto na pasta vira anexo do funcionário (pelo nome do arquivo), e foto sem dono aparece em `GET /fontes`;
  - planilha do Google é comparada pelo **conteúdo exportado**, porque a exportação demora a refletir a edição.
- **Conciliação** depois de cada auditoria disparada pelo vigia:

| Situação | Pendência |
|---|---|
| O problema não aparece mais | fecha sozinha |
| O problema continua | fica como está |
| A linha antiga foi apagada | **não fecha** |
| A regra não rodou | não fecha |

  Ela reconhece `audita_linha`, `audita_funcionario` e `auditar_ficha` (o agente novo). Confirmado com o agente real.
- **Resumo da auditoria:** traz `modo`, `modo_por_funcionario`, `custo_usd` (do agente) e `custo_total_usd` (somado dos eventos).

### Testado com o Drive real
- A correção na planilha **fechou a pendência sozinha**, e a entrega nova com CA vencido abriu a pendência para o RH.
- **Tempo de reação:** ~22 s até a auditoria (~15 s de atraso do Google + 6 s de confirmação). **Com o LLM ligado** (o vigia usa o mesmo caminho do upload), somam-se 15 a 40 s do agente: **de 40 a 60 s** até a pendência sair.
- O Google Sheets tira o zero das matrículas (`0302` → `302`): formatar a coluna como texto. A ligação de foto já ignora zeros à esquerda.
- Colar uma linha inteira no Sheets só funciona separada por TAB. Truque: `printf '301\tJoão…' | pbcopy` e Cmd+V na coluna A.

---

## 4. Revisão: o que foi resolvido e o que continua

### Resolvido nos PRs #6 a #9
- **Concorrência:** a auditoria inteira caía com funcionários em paralelo (`dictionary changed size during iteration`; 19 de 44 no estresse). Cada funcionário tem agora os próprios achados (PR #7, com teste de regressão).
- **Base CAEPI duplicada:** a conferência CA × EPI lia `data/tgg_export_caepi.txt`, que só existia numa máquina. Agora usa a base oficial e avisa no log quando não há base. O arquivo antigo só com `HEITOR_CAEPI`.
- **Exposição em R$ estimada (12 meses fixos):** o agente agora passa datas e funções ao `calcula_exposicao` (#6).
- **Falsos positivos:** acabaram o "capacete não é exigido para carpinteiro" e as trocas atrasadas da luva de 30 dias (#9).
- **Regras fora do contrato:** `entrega_sem_ficha`, `ficha_sem_planilha` e `leitura_incerta` entraram no contrato (#8).
- **Vigia sem fechar pendência com o agente novo:** corrigido (#8).
- **`test_integracao` e teste de CA sem a base:** agora são pulados.

### Segurança e privacidade (continuam)
1. **API sem autenticação.** Qualquer pessoa com o link vê nomes e matrículas e apaga tudo pelo `POST /demo/reset`. → Token nas rotas que alteram dados; reset só com `HEITOR_DEMO=1`. **(Pierre, antes do deploy)**
2. **Upload sem limite de tamanho** (`heitor/api/uploads.py`). → 15 MB, só CSV/JPG/PNG/WEBP. **(Pierre, antes do deploy)**
3. **O texto da ação é escrito pelo LLM e vai no e-mail.** Uma célula da planilha com instruções pode pôr um link num e-mail enviado em nome do Heitor. → No e-mail, usar a `acao_sugerida` da regra; o texto do LLM fica só na tela. **(Pierre, junto com o e-mail)**
4. **`load_dotenv(override=True)`** em `heitor/agente/llm.py:24` sobrescreve variáveis já definidas (nos testes e no deploy). **(Sofia)**
5. **A mensagem da exceção vai para a evidência do achado** (`heitor/agente/ferramentas.py`, `_falha_vira_revisao`) e mostra caminhos do servidor no relatório. **(Sofia, baixa)**

### Regras e dados (continuam)
1. **Linha sem data passa sem achado** (a validade do CA não é checada). **(Gustavo)**
2. **Treinamento não é verificado**, embora o CLAUDE.md diga "sem registro = irregular". **(Decisão do time)**
3. **Linha malformada vira acusação** (visto no teste com o Drive): uma colagem não dividida em colunas virou um funcionário `301,João…`, com "assinatura ausente (irregular)". → A leitura da planilha deveria marcar a linha como "incompleta, revisar". **(Sofia)**
4. **`ca_nao_encontrado`** também é usado quando o CA existe mas é de outro equipamento (#9). O rótulo fica impreciso. **(Gustavo, baixa)**
5. **Planilha e fotos da demo fora do Git** (`construtora_ficticia.csv`, `fotos_teste/`). **(Sofia)**

### Demo e deploy (continuam)
1. **Base CAEPI fora do repositório** (144 MB): o servidor do deploy precisa dela. **(Pierre)**
2. **Estado em memória:** reiniciar apaga tudo, e o vigia audita a pasta inteira de novo. Aceitável na demo; não reiniciar depois de preparar.
3. **Dependências pesadas:** `pandas` e `langfuse` não são usados em nada; `onnxruntime` e `numpy` só no script `tests/avaliar_yolo.py`. Pesam no deploy. **(Sofia)**
4. **Custo da leitura de foto:** com o agente novo, a conferência do papel roda dentro do agente e deve entrar no custo dele. Conferir.

---

## 5. Deploy: o que já foi levantado

- **Memória medida:** 81 MB sem a base e ~404 MB com a base CAEPI carregada. Planos de 512 MB ficam no limite.
- **Opções:**
  - **Hugging Face Spaces (Docker):** grátis, 2 vCPU e 16 GB. Hiberna depois de 48 h sem uso. Num Space público o código fica visível, igual a um GitHub público; as chaves vão em segredos. A base de 144 MB pode ir no próprio Space. **Recomendado.**
  - **Railway, plano Hobby:** ~US$ 5/mês. O crédito de teste do Pierre acabou. Não usar outra conta para repetir o crédito.
  - Render grátis: não (512 MB e hiberna a cada 15 min).
- **Falta:** escolher a plataforma; depois, `Dockerfile`, segredos (Featherless, chave do Drive) e a base dentro da imagem.

---

## 6. E-mail (cronograma: 19h às 23h, "pedido de documento por e-mail")

- O código está pronto (`heitor/api/notificacao.py`): avisa o técnico ou o RH quando a pendência é criada ou reaberta. Sem SMTP no `.env`, só registra no log.
- **Falta:**
  - decidir **e-mail ou Telegram** (em aberto no CLAUDE.md);
  - um Gmail com senha de app (exige verificação em duas etapas);
  - preencher `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `HEITOR_EMAIL_TECNICO` e `HEITOR_EMAIL_RH`;
  - mandar no e-mail a ação da regra, não a do LLM (Segurança 3).

---

## 7. Próximos passos meus (Pierre), em ordem

1. **Deploy:** escolher a plataforma, colocar token e reset só em modo demo, limite de upload e base CAEPI no servidor.
2. **E-mail:** canal, conta e ação da regra no corpo do e-mail.
3. **Aviso "edição detectada" no feed** assim que a versão da planilha muda (a tela reage em ~3 s, em vez de ~20 s).
4. **Aquecer o LLM** quando o servidor sobe.
5. **Gatilho 2:** prazo vencendo, com o botão "avançar 7 dias".
6. **Gatilho 7:** resumo diário.
7. **Números para o checkpoint das 23h:** reação do vigia, tempo da auditoria com LLM, custo e pendências fechadas sozinhas.
8. Pôr a `construtora_ficticia.csv` na pasta do Drive, com a coluna de matrícula como texto.
