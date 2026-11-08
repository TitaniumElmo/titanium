import type { ReactNode } from "react";
import { ROTULO_PERIODO, useEstado, type Periodo } from "../estado";
import { IconePredio } from "../util";

function SeletorPeriodo() {
  const { periodo, setPeriodo } = useEstado();
  return (
    <label className="relative inline-flex">
      <span className="sr-only">Período</span>
      <select
        value={periodo}
        onChange={(e) => setPeriodo(e.target.value as Periodo)}
        className="h-9 appearance-none rounded-controle border border-borda bg-superficie pl-3 pr-8 text-sm text-texto hover:border-fraco"
      >
        {(Object.keys(ROTULO_PERIODO) as Periodo[]).map((p) => (
          <option key={p} value={p}>
            {ROTULO_PERIODO[p]}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fraco">▼</span>
    </label>
  );
}

export function Pagina({
  titulo,
  descricao,
  comPeriodo = false,
  acoes,
  children,
}: {
  titulo: string;
  descricao?: string;
  comPeriodo?: boolean;
  acoes?: ReactNode;
  children: ReactNode;
}) {
  const { empresa } = useEstado();
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-h2 sm:text-h1">{titulo}</h1>
          {descricao && <p className="mt-1 text-sm text-apoio">{descricao}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex h-9 items-center gap-2 rounded-controle border border-borda bg-superficie px-3 text-sm text-apoio">
            <IconePredio className="size-4 shrink-0" />
            <span className="truncate">{empresa ?? "Nenhuma empresa conectada"}</span>
          </span>
          {comPeriodo && <SeletorPeriodo />}
          {acoes}
        </div>
      </header>
      {children}
    </div>
  );
}
