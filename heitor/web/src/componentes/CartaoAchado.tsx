import { Link } from "react-router-dom";
import { reais, ROTULO_STATUS, rotuloRegra } from "../formato";
import type { Achado, Pendencia } from "../tipos";
import { cn } from "../util";
import { SeloGravidade, SeloTipo } from "./Selos";

const FUNDO_PRETO = "border-borda bg-superficie bg-[radial-gradient(120%_90%_at_100%_0%,var(--cartao-brilho),transparent_60%)]";
const FUNDO_URGENTE = "border-borda bg-gradient-to-b from-cartao-urgente-topo via-cartao-urgente-meio to-cartao-urgente-base";

function Destino({ achado, pendencia }: { achado: Achado; pendencia?: Pendencia }) {
  const classe = "group flex items-center justify-between gap-3 text-sm font-medium sm:text-base";
  const seta = (
    <svg aria-hidden viewBox="0 0 24 24" className="size-5 shrink-0 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
  if (achado.tipo === "passivo") {
    return (
      <Link to="/relatorio" className={classe}>
        <span>Sem tarefa · vai para o relatório</span>
        {seta}
      </Link>
    );
  }
  const destino = achado.tipo === "prova" ? "pedido ao RH" : "pendência para o técnico";
  if (!pendencia) return <span className={cn(classe, "text-apoio")}>Vira {destino}</span>;
  return (
    <Link to={`/pendencias?p=${pendencia.id}`} className={classe}>
      <span>
        {achado.tipo === "prova" ? "Pedido ao RH" : "Pendência"} <span className="font-mono">{pendencia.id}</span> · {ROTULO_STATUS[pendencia.status].toLowerCase()}
      </span>
      {seta}
    </Link>
  );
}

export function CartaoAchado({
  achado,
  pendencia,
  compacto = false,
  className,
}: {
  achado: Achado;
  pendencia?: Pendencia;
  compacto?: boolean;
  className?: string;
}) {
  const urgente = !compacto && achado.gravidade === "irregular" && achado.tipo === "corrigivel" && pendencia?.status !== "fechada";
  return (
    <article className={cn("flex flex-col overflow-hidden rounded-cartao border", compacto ? "border-borda bg-superficie" : urgente ? FUNDO_URGENTE : FUNDO_PRETO, className)}>
      <div className={cn("flex flex-1 flex-col", compacto ? "p-4" : "p-4 sm:p-5")}>
        <div className="flex flex-wrap items-center gap-1.5">
          <SeloGravidade gravidade={achado.gravidade} />
          <SeloTipo tipo={achado.tipo} />
          <span className="ml-auto text-xs font-medium text-apoio sm:text-sm" title={achado.regra}>
            {rotuloRegra(achado.regra)}
          </span>
        </div>
        <h3 className={cn("mt-3 font-medium", compacto ? "text-sm" : "text-base")}>
          {achado.nome}
          <span className="font-normal text-apoio">
            {" "}
            · {achado.funcao} · {achado.linha > 0 ? `linha ${achado.linha}` : achado.regra === "ficha_sem_planilha" ? "só no papel" : "ficha inteira"}
          </span>
        </h3>
        <p className="mt-1 text-code text-apoio">{achado.evidencia}</p>
        {!compacto && (
          <div className="mt-3 flex flex-col gap-1 text-sm sm:text-base">
            <span>
              <span className="text-fraco">Ação: </span>
              {achado.acao_sugerida}
            </span>
            {achado.exposicao !== undefined && (
              <span className="text-sm tabular-nums text-apoio" title="Exposição potencial máxima, se a perícia confirmar a insalubridade">
                exposição potencial máx. {reais(achado.exposicao)}
              </span>
            )}
          </div>
        )}
      </div>
      {!compacto && (
        <div className="border-t border-borda bg-superficie-2/60 px-4 py-3 text-texto sm:px-5 sm:py-3.5">
          <Destino achado={achado} pendencia={pendencia} />
        </div>
      )}
    </article>
  );
}
