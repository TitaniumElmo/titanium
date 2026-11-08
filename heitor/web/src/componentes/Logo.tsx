import { COLUNAS, gradeCapacete, LINHAS, type Tom } from "../capacete";
import { NOME_AGENTE, SUBTITULO } from "../marca";
import { cn } from "../util";

const COR_DO_TOM: Record<Tom, string> = {
  base: "var(--acento)",
  crista: "var(--intro-crista)",
  aba: "var(--intro-sombra)",
  luz: "var(--intro-luz)",
};

function caminhosPorTom(): [Tom, string][] {
  const grupos = new Map<Tom, string>();
  for (const p of gradeCapacete()) {
    const y = LINHAS - 1 - p.linha;
    grupos.set(p.tom, `${grupos.get(p.tom) ?? ""}M${p.coluna} ${y}h1v1h-1z`);
  }
  return [...grupos.entries()];
}

const CAMINHOS = caminhosPorTom();

export function LogoSimbolo({ className }: { className?: string }) {
  return (
    <svg viewBox={`0 0 ${COLUNAS} ${LINHAS}`} shapeRendering="crispEdges" aria-hidden className={className}>
      {CAMINHOS.map(([tom, d]) => (
        <path key={tom} d={d} fill={COR_DO_TOM[tom]} />
      ))}
    </svg>
  );
}

export function LogoCompleta({ className, comSubtitulo = true }: { className?: string; comSubtitulo?: boolean }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <LogoSimbolo className="h-[23px] w-10 shrink-0" />
      <span className="flex flex-col leading-none">
        <span className="marca text-2xl leading-none text-texto">{NOME_AGENTE}</span>
        {comSubtitulo && (
          <span className="mt-1 text-caption font-medium tracking-sobrescrito text-fraco">{SUBTITULO}</span>
        )}
      </span>
    </span>
  );
}
