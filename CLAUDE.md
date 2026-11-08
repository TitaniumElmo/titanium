# Heitor — contexto do projeto para os Claudes do time

> Este arquivo é lido automaticamente pelo Claude Code. Ele resume o produto, as decisões já tomadas e o contrato entre os módulos. **Antes de propor algo que contradiga uma decisão daqui, pergunte ao time.**

## 1. O que é o Heitor (em uma frase)

**O Heitor encontra os furos nas fichas de EPI de uma construtora e cobra a correção antes do fiscal, do advogado ou do acidente.**

Ele audita as fichas, classifica cada falha, cria pendências para o técnico de segurança, pede documentos ao RH, confere sozinho se a correção foi feita e mede em R$ o passivo que não tem conserto.

- **Quem usa:** o técnico de segurança (SST) da consultoria.
- **Quem compra:** a consultoria de SST, que atende várias construtoras pequenas. Cobrança proposta: assinatura mensal por trabalhador monitorado (preço **não validado**).
- **Quem sente a dor:** a construtora, que paga adicional de insalubridade retroativo quando a ficha não prova a proteção.
- **Beneficiário indireto:** o trabalhador (a auditoria acha quem está sem EPI válido antes do acidente).

**Evento:** Converge Challenge (Porto Digital, Recife), 7 e 8/11/2026. Código a partir das 10h30 de sábado. Submissão até 13h de domingo. Demo Day às 16h, **3 minutos por time**. Os jurados vão **testar** a solução.

**Critérios da banca (pesos iguais):** (1) qualidade do protótipo e aderência ao desafio; (2) viabilidade como startup; (3) criatividade; (4) pitch. A banca também olha confiabilidade, evals, custo/latência e rastro auditável do agente.

---

## 2. Base jurídica (por que o produto existe)

- Na Justiça do Trabalho, **cabe à empresa provar que neutralizou o risco**. A ficha de EPI prova a **entrega**, não a **proteção**.
- **Súmula 80 do TST:** EPI aprovado (com CA) e eficaz exclui o adicional.
- **Súmula 289 do TST:** o simples fornecimento não basta; a empresa precisa garantir uso efetivo (treinamento, troca, fiscalização).
- As duas valem juntas. Quem caracteriza a insalubridade é o **perito** (art. 195 da CLT). **O Heitor nunca diz que há ou não insalubridade**: ele aponta lacunas na prova documental.
- Adicional: 10%, 20% ou 40% do salário mínimo. Cobrável até **5 anos** para trás. ~R$ 19 mil por trabalhador no grau médio, antes dos reflexos.
- **Treinamento:** segundo o especialista consultado, sem prova de treinamento exigido, "fatalmente a empresa será condenada". **Sem registro de treinamento = irregular** (não só risco).
- **Cimento NÃO gera adicional** (Tema 190 do TST, tese vinculante). **Cimento não entra no dataset.** O risco das funções da demo é **ruído** (betoneira, serra, martelete — NR-15, Anexos 1 e 2).
- **Nunca** sugerir preencher, assinar ou alterar ficha antiga com data passada. Isso é fraude documental. O Heitor "corrige o presente, busca a prova que existe e mede o passivo que sobra".

---

## 3. O ciclo do agente

```
Auditar fichas (CAEPI + tabela função → EPI)
        │
   Tipo de achado?
   ├── passivo    → Registrar passivo (exposição em R$ no relatório)
   ├── prova      → Pedir documento ao RH (nota fiscal / lista de treinamento) ──┐
   └── corrigível → Criar pendência (ação + prazo ao técnico)                    │
                        │                                                        │
              [Técnico corrige e devolve a ficha]  ← única etapa humana          │
                        │                                                        │
                    Reauditar (mesmas regras) ◄──────────────────────────────────┘
                        │
                    Confere?
                    ├── sim → Fechar pendência
                    └── não → Reabrir pendência
```

Se o documento pedido ao RH não existir, o achado vira pendência ou passivo.

**Como a correção chega:** o técnico corrige na **planilha da pasta do Drive** e o vigia percebe sozinho (gatilho 1, seção 8): a auditoria nova fecha a pendência cujo problema sumiu. Também dá para responder pela API (`POST /pendencias/{id}/resposta`).

### Os três tipos de achado
| Tipo | Exemplos | Ação |
|---|---|---|
| `corrigivel` | EPI inadequado, EPI vencido, falta de treinamento, falta de assinatura nas próximas entregas | Pendência para o técnico |
| `prova` | Nota fiscal da compra, lista de presença do treinamento, ficha arquivada em outro lugar | Pedido de documento ao RH |
| `passivo` | Entrega antiga sem assinatura, período sem EPI | Registro no relatório com exposição em R$ |

---

## 4. Princípio de arquitetura (não negociável)

**O LLM decide o caminho; as ferramentas (regras determinísticas) decidem a verdade.**

- O LLM roda em laço (LangGraph): escolhe a ferramenta, lê o resultado, decide o próximo passo, até "terminei" ou o limite de passos.
- **O LLM nunca escreve o veredito.** Só as regras (`audita_linha`, `audita_funcionario`, via `auditar_ficha`) produzem `irregular` / `risco` / `ok`. Afirmação de irregularidade que não veio delas não entra no relatório.
- **O que o LLM decide (é por isso que é agente, não workflow):** o que investigar (`consulta_ca`, `historico_da_empresa`, `buscar_ca_proximo`), **se vale conferir a ficha de papel**, a **urgência** de cada correção (prazo de 1–2 dias para quem está sem proteção hoje) e o **texto da ação para o técnico**. Ficha limpa termina em ~2 passos; ficha suspeita é investigada.
- **Objetivo do prompt (preventivo):** no histórico do funcionário (até 5 anos), descobrir o que precisa ser corrigido agora e dizer ao técnico o que fazer, até quando e por quê. O passivo vai para o relatório, não vira tarefa.
- Um episódio por funcionário; até 3 funcionários em paralelo (`HEITOR_PARALELO`).
- **Não é chatbot (decidido em 07/11):** o Heitor reage a acontecimentos, ninguém pergunta nada a ele. Quem percebe o acontecimento é **código comum, sem LLM** (o vigia da pasta, `heitor/api/vigia.py`); o agente só é acordado quando algo mudou. Gatilhos da demo: **1** mudança na pasta (pronto), **2** prazo de pendência vencendo (pronto) e **7** resumo diário (a fazer).

### Guarda-corpos
- Limite de **12 passos por funcionário** e de tempo total.
- Se uma ferramenta ou a API do modelo falhar: tenta de novo uma vez; se falhar de novo, vira pendência de revisão e o fluxo **segue** (nunca trava).
- CA sugerido por `buscar_ca_proximo` é sempre **suposição de baixa confiança**: nunca gera `irregular` sozinho.
- **Nenhuma ferramenta altera ficha.** O agente só lê, pede e confere.
- Todo passo vira um `Evento` no log (ferramenta, entrada, saída, custo). O log é a prova de autonomia na demo.
- Demo previsível: temperatura baixa, dataset fixo, vídeo de backup.
- **Rede de segurança** no fim de cada funcionário: o que o LLM deixou para trás (linha sem auditar, falha sem pendência, foto sem conferir) é feito pelo código e aparece no log como "guarda-corpo". Com ou sem LLM, a auditoria acha **as mesmas falhas**.
- **Nunca mandar retirar, recolher ou deixar de usar um EPI** (texto assim é trocado pela ação da regra). Nunca sugerir assinar/preencher ficha antiga.
- **CA e data lidos nunca são trocados.** CA que não combina com o EPI (base CAEPI) e data impossível (antes da admissão ou no futuro) viram **conferência no papel**, com o provável e o motivo: pode ser erro de leitura ou de registro, e só o papel diz qual.
- Tudo o que é dúvida de uma ficha vira **uma** pendência de conferência para o técnico; a mesma ação repetida vira uma pendência listando as linhas.
- **LLM fora do ar:** timeout de 15 s por provedor; o funcionário segue em modo degradado (política determinística) e o próximo tenta de novo; depois de 2 seguidos, o agente desiste. O resultado traz `modo` (`llm` | `misto` | `deterministico`).

---

## 5. Regras de auditoria

| Regra | Irregular quando | Tipo | Ação |
|---|---|---|---|
| Assinatura | Linha sem assinatura | passivo (entrega antiga) | Relatório + pendência para colher assinatura nas próximas entregas |
| Validade do CA | Ver abaixo | prova | Pedir nota fiscal ao RH |
| EPI adequado à função | EPI exigido ausente ou de categoria errada | corrigível | Pendência: entregar o EPI certo |
| Troca na vida útil | Intervalo entre trocas maior que a vida útil do fabricante | corrigível | Pendência: trocar agora |
| Treinamento | Sem registro | corrigível ou prova | Pedir lista de presença; se não existir, pendência para treinar |

### Regra do CA (compra ou entrega) — **critério adotado**
A Nota Técnica 146/2015 do MTE diz que o CA precisa ser válido na **data da compra**; depois vale a vida útil do produto. O especialista concordou. A ficha normalmente só tem a data de **entrega**. Como a compra sempre acontece antes da entrega:
- CA **válido na data da entrega** → regular nos dois critérios.
- CA **vencido na data da entrega** → indeterminado → `risco`, e o agente pede a nota fiscal ao RH.
- Nota fiscal com data em que o CA valia → regular. Sem nota fiscal → `irregular`, com o critério escrito no relatório.
- "Até 15/10" **inclui** o dia 15 (a confirmar).
- No pitch, dizer **"critério adotado"**, nunca "a lei diz".

### Base CAEPI (MTE)
- **Base oficial do time (decidido em 07/11):** `dados/RelatorioCA_20261107_114519.csv` (pasta do Drive do Gustavo; fora do Git). Carregada por `heitor.dados.caepi`, inteira em memória, sem internet na demo. Regras e conferência CA × EPI usam a mesma base; sem ela, os testes que dependem dela são pulados e a conferência avisa no log que está desligada.
- (Histórico: o export antigo `tgg_export_caepi.txt`, retrato de 16/07/2026, só é lido com `HEITOR_CAEPI=<caminho>`.)
- Campos usados: 1 número do CA (chave), 2 data de validade (o mais importante), 3 situação (só dica), 6 razão social, 8 equipamento (categoria), 9 e 13 (texto livre, só evidência).
- **Ignorar o rótulo VENCIDO/VÁLIDO** (vale para o dia do retrato). Comparar a data da ficha com a data de validade.
- CANCELADO (62 CAs, 154 registros) e SUSPENSO (3 CAs, 6 registros) → pendência de revisão (a base não diz desde quando).
- 123.866 registros, 42.534 CAs únicos; 21.254 têm mais de uma linha e só 22 discordam na validade → pendência "CA com dados conflitantes".
- A base oficial (CSV com aspas) não tem linhas quebradas.
- CA não encontrado → nunca acusar sem prova; tentar `buscar_ca_proximo`, senão pendência.
- Capacetes: classe A virou C, classe B virou E (tratar como equivalentes).
- Comparação de EPI **por categoria** (ex.: "qualquer protetor auditivo"), não por nome exato.

### CAs reais verificados para o dataset
Capacete 29637 · botinas 9182 e 12844 · óculos 10344 · luva de raspa 21245 (vencida entre 29/04/2024 e 24/06/2024 segundo o ConsultaCA; **na base RelatorioCA de 07/11 aparece válida nesse período**) · protetor auditivo 17664 · botina vencida 28499 (desde 02/10/2020).

### Tabela função → EPI (Gustavo; decidido: só ruído)
Só ruído (NR-15, Anexos 1 e 2) por enquanto. Só "EPI exigido ausente" é falha; **EPI a mais não é falha** (a regra "EPI não exigido" foi removida: gerava falso positivo e quase fez o agente mandar retirar EPI).
| Função | Agente nocivo | EPI exigido | Vida útil | Grau |
|---|---|---|---|---|
| Pedreiro | Ruído | Protetor auditivo | a definir | a definir |
| Servente | Ruído | Protetor auditivo | a definir | a definir |
| Carpinteiro | a definir | a definir | a definir | a definir |
| Armador | a definir | a definir | a definir | a definir |

### Exposição em R$ (só para o passivo)
`E = grau × salário_mínimo × min(meses_sem_prova, 60) × empregados_na_mesma_situação`
Sempre chamar de **"exposição potencial máxima, se a perícia confirmar a insalubridade"**. O relatório informa qual salário mínimo foi usado.

---

## 6. Módulos e donos

```
heitor/
  dados/    Gustavo   caepi.py, regras.py, funcoes.py, exposicao.py
  agente/   Sofia     grafo.py, ferramentas.py, extracao.py, relatorio.py
  api/      Pierre    main.py, rotas/, estado.py, execucao.py, ferramentas.py, notificacao.py,
                      vigia.py + fontes.py (gatilho 1: pasta do Drive), fotos.py (foto → funcionário)
  web/      Luciana   interface
```

As ferramentas do agente chamam funções Python diretamente. **Só a interface fala com a API por HTTP.** Até uma função ficar pronta, cada um usa um **stub com a mesma assinatura**.

### Ferramentas do agente (o que o LLM pode chamar)
| Ferramenta | O que faz | Dono da regra por trás |
|---|---|---|
| `auditar_ficha()` | Regras no histórico inteiro do funcionário; devolve as falhas em `corrigir_agora`, `depende_de_prova`, `passivo`, `conferir_no_papel`. **Fonte do veredito.** | Gustavo |
| `conferir_ficha_de_papel()` | Confere na foto se cada entrega da planilha está assinada pelo funcionário; o agente decide quando usar (~25 s) | Sofia |
| `historico_da_empresa(epi)` | CAs que a empresa usa para aquele tipo de EPI | Sofia |
| `consulta_ca(numero, data)` | CA válido na data? | Gustavo |
| `buscar_ca_proximo(numero)` | CAs com número parecido (sempre suposição) | Gustavo |
| `exigencia_funcao()` | Agente nocivo, EPI exigido, vida útil | Gustavo |
| `audita_linha` / `audita_funcionario` | Reauditar uma linha ou a ficha inteira | Gustavo |
| `criar_pendencia(achado_id, acao, prazo_dias)` | Pendência com a ação escrita pelo agente; o destino (técnico/RH) vem do tipo do achado | Pierre |
| `reextrair_campo(linha, campo)` | Relê um campo de foto com baixa confiança | Sofia |
| `terminei(resumo)` | Encerra o funcionário | — |

Fora do LLM (código): `mapear_colunas` e `extrair_ficha` (planilha → `Linha`, Sofia), `conferencia_assinaturas` / `conferencia_ca` / `conferencia_datas` (Sofia), `audita_fora_da_planilha` (Gustavo), `calcula_exposicao` (Gustavo), `gerar_relatorio` (Sofia), `fechar_pendencia` (Pierre).

Pedido de documento ao RH = pendência com `destino: "rh"` (nota fiscal da compra, lista de presença do treinamento). A conferência no papel vai sempre ao técnico.

### Funções que cruzam módulos
- **Gustavo → Sofia:** `consulta_ca`, `buscar_ca_proximo`, `exigencia_funcao`, `audita_linha` (lê `na_ficha`, `assinatura_tipo`, `assinatura_texto`), `audita_funcionario`, `audita_fora_da_planilha`, `calcula_exposicao(achados, funcoes=)`.
- **Pierre → Sofia:** `criar_pendencia`, `fechar_pendencia`, `obter_pendencia`.
- **Sofia → Pierre:** `rodar_auditoria(auditoria_id, linhas, emitir_evento, fotos=)`, `conferir_e_auditar(auditoria_id, linhas_da_planilha, {funcionario_id: foto}, emitir_evento)` e `reauditar(pendencia_id, linhas)`.

---

## 7. Contrato JSON

```json
{
  "Linha": {"funcionario_id": "0302", "nome": "Rafael Souza Costa", "funcao": "servente", "linha": 5,
            "data": "2023-09-12", "epi": "luva de raspa", "qtd": 1, "ca": null, "motivo": "T",
            "assinatura": true, "confianca": {"ca": 0.98, "assinatura": 0.91}, "origem": "ficha_0302.csv"},
  "Achado": {"id": "a-17", "funcionario_id": "0302", "linha": 5, "regra": "ca_ausente", "gravidade": "risco",
             "tipo": "prova", "evidencia": "linha 5, campo CA vazio", "acao_sugerida": "pedir nota fiscal ao RH"},
  "Pendencia": {"id": "p-3", "achado_id": "a-12", "destino": "tecnico",
                "acao": "entregar protetor auditivo e colher assinatura", "prazo": "2026-11-12",
                "status": "aberta", "historico": []},
  "Evento": {"auditoria_id": "au-1", "passo": 4, "ferramenta": "consulta_ca", "entrada": {}, "saida": {},
             "custo_usd": 0.0012, "ts": "2026-11-07T15:02:11"}
}
```

**Valores fechados:**
- `gravidade`: `irregular` | `risco` | `ok`
- `tipo`: `corrigivel` | `prova` | `passivo`
- `destino`: `tecnico` | `rh`
- `status`: `aberta` | `aguardando` | `fechada` | `reaberta`

---

## 8. API (Pierre)

| Método | Rota | O que faz | Usado em |
|---|---|---|---|
| POST | `/auditorias` | `arquivos` (planilhas: a fonte dos dados), `fotos` (fichas de papel) e `funcionarios_das_fotos` (id de cada foto, na mesma ordem; sem ele, vale a matrícula no nome do arquivo, ex.: `0302.jpg`). Com foto, chama `conferir_e_auditar`. Roda em segundo plano | Upload |
| GET | `/auditorias` | Lista, a mais recente primeiro. `disparado_por` é um código (`alteracao_planilha` \| `upload` \| `manual` \| `prazo_vencido` \| `rotina`); o texto vai em `descricao_disparo` (ex.: "mudança na pasta: fichas.csv") | Painel |
| GET | `/auditorias/{id}` | Status, contagem por gravidade, exposição total, `modo`, `modo_por_funcionario`, custo | Painel |
| GET | `/auditorias/{id}/eventos` | **SSE** do log de uma auditoria (`event: evento` e `event: status`) | Log ao vivo |
| GET | `/eventos` | **SSE com tudo o que o Heitor faz**, de todas as auditorias, inclusive as disparadas pelo vigia | Feed da tela principal |
| GET | `/fontes` | O que o vigia observa, última verificação, último disparo, fotos sem dono | Equipe |
| POST | `/fontes/verificar` | Força uma verificação da pasta agora (depuração) | Equipe |
| GET | `/auditorias/{id}/achados` | Achados com tipo, gravidade e evidência | Lista de achados |
| GET | `/auditorias/{id}/relatorio` | Relatório com normas e súmulas | Relatório |
| GET | `/pendencias` | Lista, filtros `auditoria_id`, `destino`, `status` | Painel de pendências |
| GET | `/pendencias/{id}` | Detalhe e histórico | Tela do técnico |
| POST | `/pendencias/{id}/resposta` | Técnico/RH envia ficha corrigida ou documento; dispara reauditoria; devolve novo status | Tela do técnico |
| GET | `/ca/{numero}?data=` | Consulta de CA (depuração e demo) | Equipe |
| POST | `/demo/reset` | Volta ao dataset fixo | Demo |
| GET | `/health` | Saúde do serviço | — |

- Estado em memória: reiniciar o servidor apaga tudo, e o vigia audita a pasta inteira de novo.
- CORS liberado para a interface.
- **Segurança do deploy (link público, os jurados testam):** `POST /demo/reset` só existe com `HEITOR_DEMO=1` e, como `POST /fontes/verificar`, exige o token `HEITOR_TOKEN_ADMIN` (`Authorization: Bearer <token>` ou `X-Heitor-Token`). Sem token configurado, ficam liberadas (desenvolvimento). Subir planilha e responder pendência ficam **abertos**, com limite: até 20 arquivos por envio, 15 MB cada, só CSV/PDF/JPG/PNG/WEBP.

### Gatilho 1: vigia da pasta do Drive (`heitor/api/vigia.py`)
- **Configuração (`.env`):** `HEITOR_DRIVE_PASTA` (id da pasta) e `HEITOR_DRIVE_CREDENCIAIS` (chave JSON de uma conta de serviço, **fora do repositório**; a pasta é compartilhada com ela como **Leitor**). Sem Drive, `HEITOR_FONTE_PASTA` (pasta local). `HEITOR_VIGIA_INTERVALO` (padrão 10 s; 3 s na demo).
- Consulta a pasta periodicamente (sem webhook) e **só age quando o arquivo aparece igual em duas consultas** (não lê edição pela metade). Lê só o que mudou e audita só os funcionários que mudaram. Planilha do Google é comparada pelo **conteúdo exportado**: a versão muda na hora, mas o CSV demora a refletir a edição.
- **Foto na pasta = anexo do funcionário** (matrícula no nome do arquivo), nunca fonte de dados. Foto sem dono aparece em `GET /fontes`.
- **Conciliação** depois da auditoria disparada: o problema sumiu → **fecha** a pendência; continua → fica como está (sem duplicar nem reavisar); a linha antiga foi **apagada** → **não fecha** (apagar não corrige); a regra não rodou → não fecha.
- **Nunca altera a pasta:** só lê.
- **Tempo medido (Drive real):** ~22 s da edição até a auditoria (~15 s são o atraso do Google), mais 15 a 40 s do agente com LLM para 1 ou 2 funcionários.
- O Google Sheets tira o zero da frente das matrículas (`0302` → `302`): formatar a coluna como texto. A ligação de foto ignora zeros à esquerda.
- **"Edição detectada" no feed** (`GET /eventos`, `auditoria_id: "vigia"`): sai assim que a **versão** da planilha muda (~3 s), antes de o Google refletir o conteúdo; uma vez por edição.

### Gatilho 2: cobrança de prazo vencido (`heitor/api/cobranca.py`)
- Pendência aberta ou reaberta com prazo vencido é cobrada: no máximo **1 cobrança por dia**; na **2ª**, escala (prioridade alta e aviso também a `HEITOR_EMAIL_COORDENADOR`).
- Roda a cada ciclo do vigia; **sem vigia** (deploy sem Drive), num relógio próprio a cada `HEITOR_COBRANCA_INTERVALO` s (padrão 60).
- `HEITOR_PRAZO_TESTE=N` adianta o relógio N dias: **só para ensaio, nunca na demo** (faz tudo vencer de uma vez).

### E-mail (`heitor/api/notificacao.py`)
- **Canal decidido: e-mail** (Gmail próprio com senha de app; `.env.example` tem as variáveis). `python -m heitor.api.notificacao --teste` confere o envio.
- **Um e-mail por destinatário por auditoria** (e por rodada de cobrança), com a lista das pendências, não um por pendência: o Gmail **bloqueia** conta nova que manda dezenas de e-mails em poucos minutos (aconteceu duas vezes em 07/11).
- O e-mail leva a **ação da regra** (`acao_sugerida`), nunca o texto escrito pelo LLM (que fica na pendência e na tela).
- `HEITOR_NOME_NO_EMAIL` (ex.: `Elmo`) muda só o nome do produto no texto do e-mail.
- Os testes **nunca** falam com servidor de e-mail (fixture no `tests/conftest.py`).

---

## 9. Escopo da demo

**Fazer (núcleo que não cai):** auditoria → pendência enviada → reauditoria fechando a pendência.
- Construtora fictícia com 3–4 funções (pedreiro, servente, carpinteiro, armador), fichas em planilha/CSV com problemas plantados e **CAs reais**.
- **A foto confere a assinatura; os dados vêm da planilha** (decidido em 07/11: ler número manuscrito errava muito). O agente decide conferir a ficha de papel de quem tem foto; na planilha da demo, o Fábio (0310) e o Wagner (0313).
- Regras novas, **sempre risco, nunca irregular:** `entrega_sem_ficha` (na planilha e não no papel) e `ficha_sem_planilha` (no papel e não na planilha).
- Pendências com ação, motivo e prazo; pedido de nota fiscal/treinamento ao RH por e-mail.
- Na demo, alguém do time adiciona a correção ao vivo e o agente fecha a pendência.
- Exposição em R$ só para o passivo.
- Log do agente na tela: decisões, número de passos, custo de LLM por ficha.
- Botão "usar dados de exemplo" (os jurados vão testar).

**Só se sobrar tempo:** agente adversário que ataca o próprio relatório (Súmulas 80 e 289); fotos difíceis; chat do técnico ("o que falta para o João?").

**Não fazer:** LLM decidindo o que é irregular · alterar ficha antiga · NR-15 completa · medição de exposição real · previdenciário · login/multiempresa/banco elaborado · redação de peça de defesa · OCR de manuscrito.

**O que corta primeiro se atrasar:** agente adversário → foto → pedido de documento ao RH.

---

## 10. Cronograma

| Quando | Marco |
|---|---|
| Sáb 10h30–11h | Kickoff: JSON, repositório, papéis |
| 11h–14h | Cada um na sua parte, com stubs |
| **14h** | **Checkpoint 1:** regras rodam sobre o gabarito; leitura funciona no CSV e numa foto boa |
| 14h–19h | Integrar. Meta: ficha entra, pendência sai |
| 19h–23h | Reauditoria, fechamento de pendência, pedido de documento por e-mail |
| **23h** | **Checkpoint 2:** rodar tudo contra os gabaritos e anotar os números |
| Dom 8h–10h | Correções finais |
| **10h** | **Demo congelada** |
| 10h–12h | Vídeo de backup + ensaiar o pitch 3x com cronômetro |
| 13h | Submissão |
| 16h | Demo Day (3 min) |

---

## 11. Números para o pitch (fontes conferidas)

- Adicional de insalubridade: **assunto mais recorrente nas novas ações da Justiça do Trabalho em 2024** (Relatório Geral da JT 2024, p. 181). Nas varas fica em 3º (p. 51) e nos TRTs em 4º (p. 106) — ser preciso no recorte.
- **DataJud/CNJ** (consultado em 07/11/2026, assunto TPU **13875**, só 1º grau): TRT6 (PE) de 3.694 (2020) para 11.206 (2025); TRT13 (PB) de 1.619 para 6.525. ~62 mil ações em 2020–2025 nos dois. **Triplicaram em 5 anos.** (Obs.: o código 1666 retorna zero; usar 13875, filtrar com `match`, datas em dois formatos.)
- Universo: ~47 mil empresas (47.346) com mais de 30 empregados e grau de risco 3 ou 4, 7,3 milhões de empregados (estimativa da Prolife a partir do IBGE). Só como teto; não bate com "construtora pequena".
- Casos: Bazan (TST, 5ª Turma, 2025, RR-10440-07.2015.5.15.0125: pensão vitalícia + R$ 35 mil, EPI danificado sem fiscalização); três casos do TRT3 trazidos pelo especialista.

### Números do Heitor (medidos em 07/11; sempre citar com a amostra)
- **Ficha de papel conferida contra a planilha** (89 entregas de 11 fichas impressas, gabaritos feitos à mão): nenhuma entrega sem assinatura passou como assinada (**6 de 6** pegas); **69 de 76** assinaturas válidas (91%) confirmadas automaticamente; **6 de 7** ambíguas (visto, "entregue", iniciais, nome de outra pessoa) barradas; **16%** das entregas foram para conferência humana. Entrega "isca" na planilha (que não existe no papel): nunca aceita como assinada.
- **Eval do comportamento do agente** (`tests/eval_agente.py`, 7 funcionários da planilha da demo, 2 com foto): **16 de 16** comportamentos esperados em 3 rodadas seguidas (ficha limpa em 2 passos; prazo de 1 dia decidido pelo LLM para quem está sem proteção; nota fiscal ao RH; investigação de CA inexistente; o próprio LLM decide conferir o papel; nunca manda retirar EPI). ~80–115 s, ~US$ 0,02–0,03.
- **Cobertura:** na planilha da demo (12 funcionários), os achados são **idênticos com e sem LLM** (8 = 8). O LLM decide o que fazer; as regras decidem o que é falha.
- **Tempo e custo:** 12 funcionários em 70–130 s com o LLM (varia com o provedor), ~US$ 0,02 por auditoria. Na demo ao vivo, 2 funcionários: 15–40 s.
- **Modelo de visão:** Qwen2.5-VL-72B, escolhido entre 7 modelos testados em 13 fotos; o detector YOLO de assinaturas foi descartado (marca qualquer letra cursiva).

### Seguro dizer / não dizer
| Dizer | Não dizer |
|---|---|
| "Aponta lacunas na prova documental" | "Detecta insalubridade" |
| "Corrige o presente, busca a prova que existe e mede o passivo que sobra" | "Conserta as fichas antigas" |
| "Exposição potencial máxima" | "Multa" / "a empresa vai pagar" |
| "Critério adotado" (regra do CA) | "A lei diz" |
| "Encontra quem está sem EPI válido antes do acidente" | "Salvamos vidas" |
| "Conforme a durabilidade indicada pelo fabricante" | "Deveria trocar todo mês" |
| "Assinatura compatível com o nome do funcionário" | "Assinado pelo funcionário" (o Heitor não autentica assinatura) |
| Número **com a amostra** ("6 de 6 em 89 entregas de 11 fichas") | Porcentagem solta ("98% de acerto") |

---

## 12. Decisões em aberto

- [x] Canal do aviso ao técnico: **e-mail** (um por destinatário por auditoria).
- [ ] Desafio Tako (DP) ou só trilha geral? O produto é SST/jurídico preventivo.
- [x] Tabela função → EPI: só ruído (NR-15, Anexos 1 e 2); EPI a mais não é falha.
- [x] Base CAEPI: `RelatorioCA_20261107_114519.csv` em `dados/`.
- [x] Foto: confere a assinatura contra a planilha (não é fonte de dados).
- [x] Não é chatbot: gatilhos 1 (pasta do Drive, pronto), 2 (prazo vencendo, pronto) e 7 (resumo diário, a fazer). O 4 (nova base CAEPI) está em avaliação.
- [ ] Deploy: Hugging Face Spaces (grátis, 16 GB) ou Railway (~US$ 5/mês). A API usa ~400 MB com a base CAEPI.
- [ ] Quem gera o conjunto de teste independente (com sujeira).
- [ ] Preço: resposta de 3–4 consultorias de SST (pagariam pela auditoria contínua? quanto por trabalhador?).
- [ ] Langfuse ou log próprio (log próprio já atende).