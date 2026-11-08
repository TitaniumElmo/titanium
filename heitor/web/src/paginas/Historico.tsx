import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAgora, useMundo, useProximaLeitura } from "../api";
import { BotaoLink, EstadoVazio } from "../componentes/base";
import { Pagina } from "../componentes/Pagina";
import { BarraFiltros, CartaoNumero, GraficoAtividade } from "../componentes/ResumoHistorico";
import { SeloGatilho } from "../componentes/Selos";
import { useEstado } from "../estado";
import { ROTULO_GATILHO, hora, mesmoDia, rotuloDia, ROTULO_STATUS } from "../formato";
import { colunasDoGrafico, exportarCsv, filtrar, funcionariosDoItem, noPeriodo, resumir, rotuloDuracao, SEM_FILTROS, type Filtros } from "../historico";
import { NOME_AGENTE } from "../marca";
import type { Gatilho, ItemAtividade } from "../tipos";
import { cn, IconeAlerta, IconeAtividade, IconeCalendario, IconeLista } from "../util";

function FaixaStatus() {
  const mundo = useMundo();
  const segundos = useProximaLeitura();
  const instante = useAgora(5000);
  const abertas = mundo.pendencias.filter((p) => p.status !== "fechada").length;
  const cobrancasHoje = mundo.pendencias.reduce(
    (soma, p) => soma + p.historico.filter((h) => h.etapa === "cobrar_atraso" && mesmoDia(h.ts, instante)).length,
    0,
  );
  const execucao = mundo.auditorias.find((a) => a.id === mundo.execucao_atual);

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-cartao border border-borda bg-superficie px-4 py-3 text-sm">
      <span className="flex items-center gap-2">
        <span className={cn("size-2 rounded-full", execucao ? "animar-pulsar bg-acento" : "bg-ok-borda")} />
        {execucao ? (
          <span>
            {NOME_AGENTE} trabalhando agora ·{" "}
            <Link to={`/agente?execucao=${execucao.id}`} className="text-acento underline-offset-4 hover:underline">
              ver ao vivo
            </Link>
          </span>
        ) : (
          <span>{NOME_AGENTE} vigiando 1 planilha</span>
        )}
      </span>
      <span className="text-apoio">
        próxima leitura em <span className="font-medium tabular-nums text-texto">{segundos ?? "—"} s</span>
      </span>
      <Link to="/pendencias" className="text-apoio hover:text-texto">
        <span className="font-medium tabular-nums text-texto">{abertas}</span> pendências abertas
      </Link>
      <span className="text-apoio">
        <span className="font-medium tabular-nums text-texto">{cobrancasHoje}</span> {cobrancasHoje === 1 ? "cobrança enviada" : "cobranças enviadas"} hoje
      </span>
    </div>
  );
}

function ItemFeed({ item, novo }: { item: ItemAtividade; novo: boolean }) {
  const navegar = useNavigate();
  const mundo = useMundo();
  const rotuloChip = (id: string) => {
    const p = mundo.pendencias.find((x) => x.id === id);
    if (!p) return "aberta";
    if (item.disparado_por === "prazo_vencido") return p.escalada ? "escalada" : "cobrada";
    return ROTULO_STATUS[p.status].toLowerCase();
  };
  const abrir = () => navegar(`/agente?execucao=${item.auditoria_id}`);
  return (
    <li
      onClick={abrir}
      className={cn(
        "group relative grid cursor-pointer grid-cols-[3.5rem_1fr] gap-3 rounded-cartao border border-borda bg-superficie p-4 transition-colors hover:border-fraco sm:grid-cols-[4rem_1fr]",
        novo && "animar-entrar",
      )}
    >
      <span className="pt-0.5 font-mono text-xs text-apoio">{hora(item.ts)}</span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <SeloGatilho gatilho={item.disparado_por} />
          {novo && (
            <span className="flex items-center gap-1 text-xs font-medium text-acento">
              <span className="size-1.5 rounded-full bg-acento" />
              novo
            </span>
          )}
        </div>
        <Link
          to={`/agente?execucao=${item.auditoria_id}`}
          onClick={(e) => e.stopPropagation()}
          className="mt-2 block text-body text-texto"
        >
          {item.resumo}
        </Link>
        {(item.pendencias_abertas.length > 0 || item.pendencias_fechadas.length > 0) && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {item.pendencias_abertas.map((id) => (
              <Link
                key={`a-${id}`}
                to={`/pendencias?p=${id}`}
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  "rounded-selo border px-2 py-0.5 font-mono text-xs",
                  ["reaberta", "escalada"].includes(rotuloChip(id))
                    ? "border-irregular-borda/40 bg-irregular-fundo font-semibold text-irregular"
                    : "border-borda bg-superficie-2 text-apoio hover:text-texto",
                )}
              >
                {id} {rotuloChip(id)}
              </Link>
            ))}
            {item.pendencias_fechadas.map((id) => (
              <Link
                key={`f-${id}`}
                to={`/pendencias?p=${id}`}
                onClick={(e) => e.stopPropagation()}
                className="rounded-selo border border-ok-borda/40 bg-ok-fundo px-2 py-0.5 font-mono text-xs text-ok"
              >
                {id} fechada ✓
              </Link>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

export function Historico() {
  const mundo = useMundo();
  const instante = useAgora(60_000);
  const { periodo } = useEstado();
  const [filtros, setFiltros] = useState<Filtros>(SEM_FILTROS);
  const vistos = useRef<Set<string> | null>(null);
  if (vistos.current === null) vistos.current = new Set(mundo.atividade.map((i) => i.id));

  if (!mundo.fonte) {
    return (
      <Pagina titulo="Histórico">
        <EstadoVazio
          icone={IconeAtividade}
          titulo={`O ${NOME_AGENTE} ainda não tem o que vigiar`}
          descricao={`Conecte a planilha de controle de EPI. A partir daí, o ${NOME_AGENTE} lê sozinho, audita cada entrega e registra aqui o que fez e por quê.`}
          acao={
            <BotaoLink para="/fontes" variante="primario">
              Conectar planilha
            </BotaoLink>
          }
        />
      </Pagina>
    );
  }

  const doPeriodo = noPeriodo(mundo.atividade, periodo, instante);
  const visiveis = filtrar(doPeriodo, filtros, mundo.pendencias);
  const resumo = resumir(doPeriodo, mundo.pendencias, periodo, instante);
  const colunas = colunasDoGrafico(visiveis, periodo, instante);
  const funcionariosDoPeriodo = [...new Set(doPeriodo.flatMap((i) => [...funcionariosDoItem(i, mundo.pendencias)]))].map((id) => ({
    valor: id,
    texto: mundo.funcionarios.find((f) => f.funcionario_id === id)?.nome ?? id,
  }));
  const gatilhos = [...new Set(doPeriodo.map((i) => i.disparado_por))] as Gatilho[];
  const filtrando = Boolean(filtros.funcionario || filtros.gatilho || filtros.evento);
  const exportar = () => {
    const blob = new Blob([exportarCsv(visiveis, (g) => ROTULO_GATILHO[g])], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "historico-elmo.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const grupos: { dia: string; itens: ItemAtividade[] }[] = [];
  for (const item of visiveis) {
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && mesmoDia(ultimo.dia, item.ts)) ultimo.itens.push(item);
    else grupos.push({ dia: item.ts, itens: [item] });
  }

  return (
    <Pagina
      titulo="Histórico"
      comPeriodo
      descricao={`Tudo o que o ${NOME_AGENTE} fez e o que o levou a agir. Ninguém precisa pedir: ele age quando algo muda.`}
    >
      <FaixaStatus />
      <section aria-label="Resumo do período" className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
        <CartaoNumero rotulo="Ações do Elmo" valor={resumo.acoes} detalhe="no período escolhido" icone={<IconeAtividade className="size-full" />} />
        <CartaoNumero
          rotulo="Pendências"
          valor={resumo.fechadas}
          detalhe={`fechadas · ${resumo.abertas} ${resumo.abertas === 1 ? "aberta" : "abertas"} agora`}
          icone={<IconeLista className="size-full" />}
        />
        <CartaoNumero
          rotulo="Reabertas"
          valor={resumo.reabertas}
          detalhe="correção não confirmada"
          urgente={resumo.reabertas > 0}
          icone={<IconeAlerta className="size-full" />}
        />
        <CartaoNumero rotulo="Tempo para fechar" valor={rotuloDuracao(resumo.tempoMedioMs)} detalhe="média das pendências fechadas" icone={<IconeCalendario className="size-full" />} />
      </section>
      <GraficoAtividade colunas={colunas} />
      <BarraFiltros filtros={filtros} onChange={setFiltros} funcionarios={funcionariosDoPeriodo} gatilhos={gatilhos} ativos={filtrando} onExportar={exportar} />
      {grupos.length === 0 && (
        <p className="rounded-cartao border border-dashed border-borda px-4 py-8 text-center text-sm text-apoio">
          Nada no período com esses filtros.
        </p>
      )}
      {grupos.map((g) => (
        <section key={g.dia} className="flex flex-col gap-2">
          <h2 className="text-label text-apoio">{rotuloDia(g.dia, instante)}</h2>
          <ol className="flex flex-col gap-2">
            {g.itens.map((item) => (
              <ItemFeed key={item.id} item={item} novo={!vistos.current?.has(item.id)} />
            ))}
          </ol>
        </section>
      ))}
    </Pagina>
  );
}
