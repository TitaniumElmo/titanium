import { Link } from "react-router-dom";
import { reais } from "../formato";
import type { Achado, Pendencia } from "../tipos";
import { cn } from "../util";
import { SeloGravidade, SeloTipo } from "./Selos";

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
  return (
    <article className={cn("rounded-cartao border border-borda bg-superficie p-4", className)}>
      <div className="flex flex-wrap items-center gap-1.5">
        <SeloGravidade gravidade={achado.gravidade} />
        <SeloTipo tipo={achado.tipo} />
        <span className="ml-auto font-mono text-xs text-fraco">{achado.regra}</span>
      </div>
      <h3 className="mt-3 text-sm font-medium">
        {achado.nome}
        <span className="font-normal text-apoio">
          {" "}
          · {achado.funcao} · {achado.linha > 0 ? `linha ${achado.linha}` : achado.regra === "ficha_sem_planilha" ? "só no papel" : "ficha inteira"}
        </span>
      </h3>
      <p className="mt-1 text-code text-apoio">{achado.evidencia}</p>
      {!compacto && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-borda pt-3 text-sm">
          <span>
            <span className="text-fraco">Ação: </span>
            {achado.acao_sugerida}
          </span>
          {achado.exposicao !== undefined && (
            <span className="text-xs tabular-nums text-apoio" title="Exposição potencial máxima, se a perícia confirmar a insalubridade">
              exposição potencial máx. {reais(achado.exposicao)}
            </span>
          )}
          {pendencia && (
            <Link to={`/pendencias?p=${pendencia.id}`} className="text-label text-texto underline-offset-4 hover:underline">
              pendência {pendencia.id} →
            </Link>
          )}
        </div>
      )}
    </article>
  );
}
