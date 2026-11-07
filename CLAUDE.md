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
- **O LLM nunca escreve o veredito.** Só `audita_linha` produz `irregular` / `risco` / `ok`. Afirmação de irregularidade que não veio dessa ferramenta não entra no relatório.
- Um episódio por funcionário (o contexto não cresce sem controle).

### Guarda-corpos
- Limite de **12 passos por funcionário** e de tempo total.
- Se uma ferramenta ou a API do modelo falhar: tenta de novo uma vez; se falhar de novo, vira pendência de revisão e o fluxo **segue** (nunca trava).
- CA sugerido por `buscar_ca_proximo` é sempre **suposição de baixa confiança**: nunca gera `irregular` sozinho.
- **Nenhuma ferramenta altera ficha.** O agente só lê, pede e confere.
- Todo passo vira um `Evento` no log (ferramenta, entrada, saída, custo). O log é a prova de autonomia na demo.
- Demo previsível: temperatura baixa, dataset fixo, vídeo de backup.

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
- Arquivo `tgg_export_caepi.txt`, retrato de **16/07/2026**, 124.937 registros, 19 campos separados por `|`, UTF-8. Carrega inteira em memória, sem internet na demo.
- Campos usados: 1 número do CA (chave), 2 data de validade (o mais importante), 3 situação (só dica), 6 razão social, 8 equipamento (categoria), 9 e 13 (texto livre, só evidência).
- **Ignorar o rótulo VENCIDO/VÁLIDO** (vale para o dia do retrato). Comparar a data da ficha com a data de validade.
- CANCELADO (190) e SUSPENSO (6) → pendência de revisão (a base não diz desde quando).
- 21.011 números repetidos; só 22 discordam → se discordam, pendência "CA com dados conflitantes".
- 34 linhas com `|` sobrando em texto livre → ler os campos pela posição a partir da esquerda.
- CA não encontrado → nunca acusar sem prova; tentar `buscar_ca_proximo`, senão pendência.
- Capacetes: classe A virou C, classe B virou E (tratar como equivalentes).
- Comparação de EPI **por categoria** (ex.: "qualquer protetor auditivo"), não por nome exato.

### CAs reais verificados para o dataset
Capacete 29637 · botinas 9182 e 12844 · óculos 10344 · luva de raspa 21245 (vencida entre 29/04/2024 e 24/06/2024) · protetor auditivo 17664 · botina vencida 28499 (desde 02/10/2020).

### Tabela função → EPI (a preencher pelo Gustavo)
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
  api/      Pierre    main.py, rotas/, estado.py, notificacao.py
  web/      Luciana   interface
```

As ferramentas do agente chamam funções Python diretamente. **Só a interface fala com a API por HTTP.** Até uma função ficar pronta, cada um usa um **stub com a mesma assinatura**.

### Ferramentas do agente
| Ferramenta | O que faz | Dono |
|---|---|---|
| `ler_fonte(fonte)` | Lê a planilha/pasta e devolve só linhas novas ou alteradas (hash por linha) | Pierre |
| `mapear_colunas(cabecalho, amostra)` | Descobre qual coluna é data, EPI, CA, assinatura, funcionário, com confiança | Sofia |
| `extrair_ficha(arquivo)` | Lê CSV ou foto e devolve as linhas com confiança por campo | Sofia |
| `reextrair_campo(arquivo, linha, campo)` | Nova tentativa num campo de baixa confiança | Sofia |
| `consulta_ca(numero, data)` | CA válido na data? (base CAEPI em memória) | Gustavo |
| `buscar_ca_proximo(numero)` | CAs com número parecido (sempre suposição) | Gustavo |
| `exigencia_funcao(funcao)` | Agente nocivo, EPI exigido, vida útil, grau | Gustavo |
| `audita_linha(linha, funcao) -> list[Achado]` | Aplica as regras; **único que produz veredito** | Gustavo |
| `calcula_exposicao(achados)` | Exposição potencial máxima do passivo | Gustavo |
| `criar_pendencia(achado, destino, acao, prazo)` | Grava a pendência e avisa (e-mail) o técnico ou o RH | Pierre |
| `fechar_pendencia(pendencia, resultado)` | Fecha se a reauditoria confirmou, reabre se não | Pierre |
| `gerar_relatorio(achados)` | Explica cada falha com a norma/súmula | Sofia |

Pedido de documento ao RH = pendência com `destino: "rh"` (não há ferramenta separada).

### Funções que cruzam módulos
- **Gustavo → Sofia:** `consulta_ca`, `buscar_ca_proximo`, `exigencia_funcao`, `audita_linha`, `calcula_exposicao`.
- **Pierre → Sofia:** `criar_pendencia(achado, destino, acao, prazo)`.
- **Sofia → Pierre:** `rodar_auditoria(auditoria_id, linhas, emitir_evento)` e `reauditar(pendencia_id, linhas)`.

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
| POST | `/auditorias` | Recebe fichas (CSV ou foto); cria a auditoria e roda o agente em segundo plano | Upload |
| GET | `/auditorias/{id}` | Status, contagem por gravidade, exposição total | Painel |
| GET | `/auditorias/{id}/eventos` | **SSE** do log do agente (ferramenta, resultado, custo por passo) | Log ao vivo |
| GET | `/auditorias/{id}/achados` | Achados com tipo, gravidade e evidência | Lista de achados |
| GET | `/auditorias/{id}/relatorio` | Relatório com normas e súmulas | Relatório |
| GET | `/pendencias` | Lista, filtros `auditoria_id`, `destino`, `status` | Painel de pendências |
| GET | `/pendencias/{id}` | Detalhe e histórico | Tela do técnico |
| POST | `/pendencias/{id}/resposta` | Técnico/RH envia ficha corrigida ou documento; dispara reauditoria; devolve novo status | Tela do técnico |
| GET | `/ca/{numero}?data=` | Consulta de CA (depuração e demo) | Equipe |
| POST | `/demo/reset` | Volta ao dataset fixo | Demo |
| GET | `/health` | Saúde do serviço | — |

- Estado em memória (ou SQLite se precisar sobreviver a reinício).
- CORS liberado para a interface.
- **Como a correção chega:** primeiro pelo endpoint `POST /pendencias/{id}/resposta` (garantia para a demo). Se sobrar tempo, também pela leitura periódica da planilha (`ler_fonte` com hash por linha), sem tela de envio.

---

## 9. Escopo da demo

**Fazer (núcleo que não cai):** auditoria → pendência enviada → reauditoria fechando a pendência.
- Construtora fictícia com 3–4 funções (pedreiro, servente, carpinteiro, armador), fichas em planilha/CSV com problemas plantados e **CAs reais**.
- Uma foto limpa do formulário impresso (um momento da demo).
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

### Seguro dizer / não dizer
| Dizer | Não dizer |
|---|---|
| "Aponta lacunas na prova documental" | "Detecta insalubridade" |
| "Corrige o presente, busca a prova que existe e mede o passivo que sobra" | "Conserta as fichas antigas" |
| "Exposição potencial máxima" | "Multa" / "a empresa vai pagar" |
| "Critério adotado" (regra do CA) | "A lei diz" |
| "Encontra quem está sem EPI válido antes do acidente" | "Salvamos vidas" |
| "Conforme a durabilidade indicada pelo fabricante" | "Deveria trocar todo mês" |

---

## 12. Decisões em aberto

- [ ] Canal do aviso ao técnico: e-mail **ou** Telegram (só um).
- [ ] Desafio Tako (DP) ou só trilha geral? O produto é SST/jurídico preventivo.
- [ ] Tabela função → EPI das 4 funções.
- [ ] Quem gera o conjunto de teste independente (com sujeira).
- [ ] Preço: resposta de 3–4 consultorias de SST (pagariam pela auditoria contínua? quanto por trabalhador?).
- [ ] Langfuse ou log próprio (log próprio já atende).