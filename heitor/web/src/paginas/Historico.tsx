import { useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAgora, useMundo, useProximaLeitura } from "../api";
import { BotaoLink, EstadoVazio } from "../componentes/base";
import { Pagina } from "../componentes/Pagina";
import { SeloGatilho } from "../componentes/Selos";
import { hora, mesmoDia, rotuloDia, ROTULO_STATUS } from "../formato";
import { NOME_AGENTE } from "../marca";
import type { ItemAtividade } from "../tipos";
import { cn, IconeAtividade } from "../util";

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
    if (item.gatilho === "prazo_vencido") return p.escalada ? "escalada" : "cobrada";
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
          <SeloGatilho gatilho={item.gatilho} />
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
                className="rounded-selo border border-borda bg-superficie-2 px-2 py-0.5 font-mono text-xs text-apoio hover:text-texto"
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

  const grupos: { dia: string; itens: ItemAtividade[] }[] = [];
  for (const item of mundo.atividade) {
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && mesmoDia(ultimo.dia, item.ts)) ultimo.itens.push(item);
    else grupos.push({ dia: item.ts, itens: [item] });
  }

  return (
    <Pagina titulo="Histórico" descricao={`Tudo o que o ${NOME_AGENTE} fez e o que o levou a agir. Ninguém precisa pedir: ele age quando algo muda.`}>
      <FaixaStatus />
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
