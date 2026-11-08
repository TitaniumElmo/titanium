import type { ReactNode } from "react";
import { ROTULO_GATILHO } from "../formato";
import { type Coluna, type Filtros, ROTULO_EVENTO, type TipoEvento } from "../historico";
import type { Gatilho } from "../tipos";
import { cn } from "../util";

const FUNDO_PRETO = "border-borda bg-superficie bg-[radial-gradient(120%_90%_at_100%_0%,var(--cartao-brilho),transparent_60%)]";
const FUNDO_URGENTE = "border-borda bg-gradient-to-b from-cartao-urgente-topo via-cartao-urgente-meio to-cartao-urgente-base";

export function CartaoNumero({
  rotulo,
  valor,
  detalhe,
  urgente = false,
  icone,
}: {
  rotulo: string;
  valor: string | number;
  detalhe: string;
  urgente?: boolean;
  icone: ReactNode;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-2 rounded-cartao border p-4 sm:gap-3 sm:p-5", urgente ? FUNDO_URGENTE : FUNDO_PRETO)}>
      <span className={cn("text-xs font-semibold uppercase tracking-sobrescrito sm:text-sm", urgente ? "text-irregular" : "text-apoio")}>{rotulo}</span>
      <span
        className={cn(
          "inline-flex w-fit items-center gap-2 rounded-full px-3 py-1.5 sm:gap-2.5 sm:px-4 sm:py-2",
          urgente ? "bg-selo-claro text-selo-claro-texto" : "bg-superficie-2 text-texto",
        )}
      >
        <span className="size-4 shrink-0 sm:size-5" aria-hidden>
          {icone}
        </span>
        <span className="whitespace-nowrap text-2xl font-semibold tabular-nums sm:text-3xl sm:leading-none">{valor}</span>
      </span>
      <span className="text-sm leading-snug text-apoio sm:text-base">{detalhe}</span>
    </div>
  );
}

export function GraficoAtividade({ colunas }: { colunas: Coluna[] }) {
  const maior = Math.max(1, ...colunas.flatMap((c) => [c.abertas, c.fechadas]));
  const resumo = `Pendências abertas e fechadas por período: ${colunas.map((c) => `${c.rotulo}, ${c.abertas} abertas e ${c.fechadas} fechadas`).join("; ")}`;
  return (
    <section className={cn("flex flex-col gap-3 rounded-cartao border p-4 sm:p-5", FUNDO_PRETO)} aria-label="Pendências abertas e fechadas">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-label">Abertas × fechadas</h2>
        <span className="flex items-center gap-4 text-sm text-apoio">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-[3px] bg-risco-borda" /> abertas
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-[3px] bg-ok-borda" /> fechadas
          </span>
        </span>
      </div>
      <div role="img" aria-label={resumo} className="flex h-36 items-end gap-1.5 border-b border-borda sm:gap-2">
        {colunas.map((c) => (
          <div key={c.rotulo} className="flex h-full min-w-0 flex-1 items-end justify-center gap-0.5 sm:gap-1" title={`${c.rotulo}: ${c.abertas} abertas, ${c.fechadas} fechadas`}>
            <span className="w-full max-w-5 rounded-t-[4px] bg-risco-borda" style={{ height: `${(c.abertas / maior) * 100}%`, minHeight: c.abertas ? 4 : 0 }} />
            <span className="w-full max-w-5 rounded-t-[4px] bg-ok-borda" style={{ height: `${(c.fechadas / maior) * 100}%`, minHeight: c.fechadas ? 4 : 0 }} />
          </div>
        ))}
      </div>
      <div className="flex gap-1.5 text-xs tabular-nums text-apoio sm:gap-2" aria-hidden>
        {colunas.map((c) => (
          <span key={c.rotulo} className="min-w-0 flex-1 truncate text-center">
            {c.rotulo}
          </span>
        ))}
      </div>
      <table className="sr-only">
        <caption>Pendências abertas e fechadas</caption>
        <thead>
          <tr>
            <th>Período</th>
            <th>Abertas</th>
            <th>Fechadas</th>
          </tr>
        </thead>
        <tbody>
          {colunas.map((c) => (
            <tr key={c.rotulo}>
              <td>{c.rotulo}</td>
              <td>{c.abertas}</td>
              <td>{c.fechadas}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Seletor({ rotulo, valor, onChange, opcoes }: { rotulo: string; valor: string; onChange: (v: string) => void; opcoes: { valor: string; texto: string }[] }) {
  return (
    <label className="relative inline-flex">
      <span className="sr-only">{rotulo}</span>
      <select
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 max-w-[14rem] appearance-none truncate rounded-controle border border-borda bg-superficie pl-3 pr-8 text-sm text-texto hover:border-fraco"
      >
        <option value="">{rotulo}</option>
        {opcoes.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.texto}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fraco">▼</span>
    </label>
  );
}

export function BarraFiltros({
  filtros,
  onChange,
  funcionarios,
  gatilhos,
  ativos,
  onExportar,
}: {
  filtros: Filtros;
  onChange: (f: Filtros) => void;
  funcionarios: { valor: string; texto: string }[];
  gatilhos: Gatilho[];
  ativos: boolean;
  onExportar: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Seletor rotulo="Funcionário" valor={filtros.funcionario} onChange={(v) => onChange({ ...filtros, funcionario: v })} opcoes={funcionarios} />
      <Seletor
        rotulo="Gatilho"
        valor={filtros.gatilho}
        onChange={(v) => onChange({ ...filtros, gatilho: v as Gatilho | "" })}
        opcoes={gatilhos.map((g) => ({ valor: g, texto: ROTULO_GATILHO[g] }))}
      />
      <Seletor
        rotulo="Tipo de evento"
        valor={filtros.evento}
        onChange={(v) => onChange({ ...filtros, evento: v as TipoEvento | "" })}
        opcoes={(Object.keys(ROTULO_EVENTO) as TipoEvento[]).map((t) => ({ valor: t, texto: ROTULO_EVENTO[t] }))}
      />
      {ativos && (
        <button type="button" onClick={() => onChange({ funcionario: "", gatilho: "", evento: "" })} className="h-9 px-2 text-sm text-apoio hover:text-texto">
          limpar
        </button>
      )}
      <button
        type="button"
        onClick={onExportar}
        className="ml-auto inline-flex h-9 items-center gap-2 rounded-controle border border-borda bg-superficie px-3 text-sm text-texto hover:border-fraco"
      >
        <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 4v11M7 11l5 5 5-5M5 20h14" />
        </svg>
        Exportar CSV
      </button>
    </div>
  );
}
