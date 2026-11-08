import { useEffect, useMemo, useRef, useState } from "react";
import { dolares, horaComSegundos } from "../formato";
import { type Clima, EXPLICACAO_ERRO, traduzir } from "../linguagemLog";
import type { Evento } from "../tipos";
import { cn } from "../util";

type Agrupamento = "tempo" | "pessoa";

const PONTO: Record<Clima, string> = {
  neutro: "bg-fraco",
  pedido: "bg-acento",
  ok: "bg-ok-borda",
  atencao: "bg-risco-borda",
};

function primeiroNome(nome?: string): string | null {
  return nome ? (nome.split(" ")[0] ?? nome) : null;
}

function Linha({ e, nomes, mostrarPessoa, tecnico }: { e: Evento; nomes: Record<string, string>; mostrarPessoa: boolean; tecnico: boolean }) {
  const pessoa = mostrarPessoa && e.funcionario_id ? (primeiroNome(nomes[e.funcionario_id]) ?? e.funcionario_id) : null;
  const detalheTecnico = (
    <span className="mt-1 block font-mono text-xs text-fraco">
      passo {String(e.passo).padStart(2, "0")}
      {e.ferramenta ? ` · ${e.ferramenta}` : ""}
      {e.custo_usd > 0 ? ` · ${dolares(e.custo_usd)}` : ""}
    </span>
  );

  if (e.tipo === "decisao") {
    return (
      <li className="animar-entrar rounded-controle border border-acento/30 bg-acento-suave px-3 py-2.5">
        <div className="flex items-center justify-between gap-3 text-xs text-apoio sm:text-sm">
          <span className="font-semibold text-acento">O Elmo decidiu{pessoa ? ` · ${pessoa}` : ""}</span>
          <span className="tabular-nums">{horaComSegundos(e.ts)}</span>
        </div>
        <p className="mt-1 text-sm text-texto sm:text-base">{e.saida.pensamento ?? e.saida.resumo}</p>
        {tecnico && detalheTecnico}
      </li>
    );
  }

  if (e.tipo === "erro") {
    return (
      <li className="animar-entrar rounded-controle border border-risco-borda/40 bg-risco-fundo px-3 py-2.5">
        <div className="flex items-center justify-between gap-3 text-xs sm:text-sm">
          <span className="font-semibold text-risco">Atenção{pessoa ? ` · ${pessoa}` : ""}</span>
          <span className="tabular-nums text-apoio">{horaComSegundos(e.ts)}</span>
        </div>
        <p className="mt-1 text-sm text-texto sm:text-base">{EXPLICACAO_ERRO[e.ferramenta ?? ""] ?? e.saida.resumo}</p>
        {tecnico && detalheTecnico}
      </li>
    );
  }

  const t = traduzir(e);
  return (
    <li className="animar-entrar grid grid-cols-[0.75rem_1fr_auto] items-start gap-x-3 px-1 py-2.5">
      <span className={cn("mt-2 size-2.5 rounded-full", PONTO[t.clima])} aria-hidden />
      <div className="min-w-0">
        <p className="text-sm font-medium text-texto sm:text-base">
          {t.titulo}
          {pessoa && <span className="ml-2 rounded-selo bg-superficie-2 px-1.5 py-0.5 align-middle text-xs font-normal text-apoio">{pessoa}</span>}
        </p>
        <p className="text-sm text-apoio">{e.saida.resumo}</p>
        {tecnico && detalheTecnico}
      </div>
      <span className="whitespace-nowrap pt-0.5 text-xs tabular-nums text-fraco sm:text-sm">{horaComSegundos(e.ts)}</span>
    </li>
  );
}

export function LogAgente({
  eventos,
  rodando,
  className,
  nomes = {},
  modo,
}: {
  eventos: Evento[];
  rodando: boolean;
  className?: string;
  nomes?: Record<string, string>;
  modo?: string;
}) {
  const rolagem = useRef<HTMLDivElement>(null);
  const [agrupamento, setAgrupamento] = useState<Agrupamento>("tempo");
  const [tecnico, setTecnico] = useState(false);
  const temPessoas = eventos.some((e) => e.funcionario_id);

  const grupos = useMemo(() => {
    const mapa = new Map<string, Evento[]>();
    for (const e of eventos) {
      const chave = e.funcionario_id ?? "geral";
      mapa.set(chave, [...(mapa.get(chave) ?? []), e]);
    }
    return [...mapa.entries()];
  }, [eventos]);

  useEffect(() => {
    const el = rolagem.current;
    if (!el || agrupamento !== "tempo") return;
    const reduzir = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduzir ? "auto" : "smooth" });
  }, [eventos.length, agrupamento]);

  return (
    <section
      className={cn(
        "flex min-h-0 flex-col overflow-hidden rounded-cartao border border-borda bg-superficie bg-[radial-gradient(120%_90%_at_100%_0%,var(--cartao-brilho),transparent_60%)]",
        className,
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-borda px-4 py-3">
        <span className="flex items-center gap-2 text-base font-semibold">
          <span className={cn("size-2 rounded-full", rodando ? "animar-pulsar bg-acento" : "bg-fraco")} />
          {rodando ? "O que o Elmo está fazendo" : "O que o Elmo fez"}
        </span>
        <span className="flex flex-wrap items-center gap-2">
          {temPessoas && (
            <span className="inline-flex rounded-controle border border-borda p-0.5 text-sm font-medium" role="radiogroup" aria-label="Organizar passos">
              {(["tempo", "pessoa"] as Agrupamento[]).map((a) => (
                <button
                  key={a}
                  type="button"
                  role="radio"
                  aria-checked={agrupamento === a}
                  onClick={() => setAgrupamento(a)}
                  className={cn("rounded-selo px-2.5 py-1 transition-colors", agrupamento === a ? "bg-superficie-2 text-texto" : "text-apoio hover:text-texto")}
                >
                  {a === "tempo" ? "Por horário" : "Por pessoa"}
                </button>
              ))}
            </span>
          )}
          <button
            type="button"
            aria-pressed={tecnico}
            onClick={() => setTecnico(!tecnico)}
            className={cn(
              "rounded-controle border px-2.5 py-1 text-sm font-medium transition-colors",
              tecnico ? "border-acento text-acento" : "border-borda text-apoio hover:text-texto",
            )}
          >
            Detalhes técnicos
          </button>
        </span>
      </header>
      {tecnico && modo && <p className="border-b border-borda px-4 py-2 text-sm text-apoio">Modo desta execução: {modo}</p>}
      <div ref={rolagem} className="flex-1 overflow-y-auto px-3 py-2" aria-live="polite">
        {eventos.length === 0 && <p className="px-2 py-8 text-center text-sm text-apoio">Esperando o primeiro passo…</p>}
        {agrupamento === "tempo" || !temPessoas ? (
          <ol className="divide-y divide-borda/60">
            {eventos.map((e) => (
              <Linha key={`${e.auditoria_id}-${e.passo}`} e={e} nomes={nomes} mostrarPessoa tecnico={tecnico} />
            ))}
          </ol>
        ) : (
          grupos.map(([chave, lista]) => (
            <section key={chave} className="mb-4">
              <h3 className="sticky top-0 z-10 flex items-center justify-between bg-superficie px-1 py-2 text-sm font-semibold">
                <span>{chave === "geral" ? "Em geral" : (nomes[chave] ?? "Funcionário")}</span>
                <span className="text-xs font-normal text-apoio">
                  {lista.length} {lista.length === 1 ? "passo" : "passos"}
                </span>
              </h3>
              <ol className="divide-y divide-borda/60">
                {lista.map((e) => (
                  <Linha key={`${e.auditoria_id}-${e.passo}`} e={e} nomes={nomes} mostrarPessoa={false} tecnico={tecnico} />
                ))}
              </ol>
            </section>
          ))
        )}
      </div>
    </section>
  );
}
