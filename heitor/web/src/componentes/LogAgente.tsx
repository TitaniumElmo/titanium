import { useEffect, useMemo, useRef, useState } from "react";
import { dolares, horaComSegundos } from "../formato";
import type { Evento } from "../tipos";
import { cn } from "../util";

type Agrupamento = "tempo" | "funcionario";

const ROTULO_ERRO: Record<string, string> = {
  modelo_indisponivel: "modo degradado",
  resposta_invalida: "resposta inválida do modelo",
  pendencia_recusada: "pendência recusada",
};

function LinhaEvento({ e, nomes, mostrarFuncionario }: { e: Evento; nomes: Record<string, string>; mostrarFuncionario: boolean }) {
  const funcionario = mostrarFuncionario && e.funcionario_id ? (
    <span
      className="mr-2 inline-block rounded-selo border border-log-borda px-1 font-mono text-xs text-log-apoio"
      title={nomes[e.funcionario_id] ?? e.funcionario_id}
    >
      {e.funcionario_id}
    </span>
  ) : null;

  let corpo;
  if (e.tipo === "decisao") {
    corpo = (
      <span className="min-w-0">
        {funcionario}
        <span className="font-sans text-xs font-medium text-log-apoio">💭 decisão</span>
        <span className="block text-log-texto">{e.saida.pensamento ?? e.saida.resumo}</span>
      </span>
    );
  } else if (e.tipo === "erro") {
    corpo = (
      <span className="min-w-0">
        {funcionario}
        <span className="font-sans text-xs font-semibold text-log-alerta">⚠️ {ROTULO_ERRO[e.ferramenta ?? ""] ?? "erro"}</span>
        <span className="block text-log-alerta">{e.saida.resumo}</span>
      </span>
    );
  } else {
    corpo = (
      <span className="min-w-0">
        {funcionario}
        <span aria-hidden>🔧 </span>
        <span className="text-acento">{e.ferramenta}</span>
        <span className="text-log-apoio"> · {e.saida.resumo}</span>
      </span>
    );
  }

  return (
    <li
      className={cn(
        "animar-entrar grid grid-cols-[2rem_1fr_auto] gap-x-2 rounded-controle px-2 py-1 hover:bg-log-superficie",
        e.tipo === "decisao" && "bg-log-decisao-fundo",
        e.tipo === "erro" && "bg-log-alerta-fundo",
      )}
    >
      <span className="text-log-fraco">{String(e.passo).padStart(2, "0")}</span>
      {corpo}
      <span className="whitespace-nowrap text-right text-log-fraco">
        {horaComSegundos(e.ts)}
        {e.custo_usd > 0 && <span className="hidden sm:inline"> · {dolares(e.custo_usd)}</span>}
      </span>
    </li>
  );
}

export function LogAgente({
  eventos,
  rodando,
  className,
  nomes = {},
}: {
  eventos: Evento[];
  rodando: boolean;
  className?: string;
  nomes?: Record<string, string>;
}) {
  const rolagem = useRef<HTMLDivElement>(null);
  const [agrupamento, setAgrupamento] = useState<Agrupamento>("tempo");
  const custo = eventos.reduce((soma, e) => soma + e.custo_usd, 0);
  const decisoes = eventos.filter((e) => e.tipo === "decisao").length;
  const degradado = eventos.some((e) => e.tipo === "erro" && e.ferramenta === "modelo_indisponivel");
  const temFuncionarios = eventos.some((e) => e.funcionario_id);

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
        "flex min-h-0 flex-col overflow-hidden rounded-cartao border border-log-borda bg-log-fundo text-log-texto",
        className,
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-log-borda bg-log-superficie px-4 py-2.5">
        <span className="flex items-center gap-2 text-label text-log-apoio">
          <span className={cn("size-2 rounded-full", rodando ? "animar-pulsar bg-acento" : "bg-log-fraco")} />
          log do agente
          {degradado && (
            <span className="rounded-selo bg-log-alerta-fundo px-1.5 text-xs font-semibold text-log-alerta">⚠️ modo degradado</span>
          )}
        </span>
        <span className="flex items-center gap-3">
          {temFuncionarios && (
            <span className="inline-flex rounded-selo border border-log-borda p-0.5 text-xs font-medium" role="radiogroup" aria-label="Agrupar log">
              {(["tempo", "funcionario"] as Agrupamento[]).map((a) => (
                <button
                  key={a}
                  type="button"
                  role="radio"
                  aria-checked={agrupamento === a}
                  onClick={() => setAgrupamento(a)}
                  className={cn(
                    "rounded-selo px-2 py-0.5 transition-colors",
                    agrupamento === a ? "bg-log-fundo text-log-texto" : "text-log-fraco hover:text-log-apoio",
                  )}
                >
                  {a === "tempo" ? "Linha do tempo" : "Por funcionário"}
                </button>
              ))}
            </span>
          )}
          <span className="font-mono text-xs text-log-apoio">
            {eventos.length} passos · {decisoes} 💭 · {dolares(custo)}
          </span>
        </span>
      </header>
      <div ref={rolagem} className="flex-1 overflow-y-auto px-2 py-2 text-code" aria-live="polite">
        {eventos.length === 0 && <p className="px-2 py-6 text-center text-log-fraco">aguardando o primeiro passo…</p>}
        {agrupamento === "tempo" || !temFuncionarios ? (
          <ol>
            {eventos.map((e) => (
              <LinhaEvento key={`${e.auditoria_id}-${e.passo}`} e={e} nomes={nomes} mostrarFuncionario />
            ))}
          </ol>
        ) : (
          grupos.map(([chave, lista]) => (
            <section key={chave} className="mb-3">
              <h3 className="sticky top-0 z-10 flex items-center justify-between bg-log-fundo px-2 py-1 font-sans text-xs font-medium text-log-apoio">
                <span>
                  {chave === "geral" ? "Execução" : `${chave} · ${nomes[chave] ?? "funcionário"}`}
                </span>
                <span className="font-mono text-log-fraco">
                  {lista.length} {lista.length === 1 ? "passo" : "passos"}
                  {lista.some((e) => e.tipo === "erro") && <span className="text-log-alerta"> · ⚠️ degradado</span>}
                </span>
              </h3>
              <ol>
                {lista.map((e) => (
                  <LinhaEvento key={`${e.auditoria_id}-${e.passo}`} e={e} nomes={nomes} mostrarFuncionario={false} />
                ))}
              </ol>
            </section>
          ))
        )}
      </div>
    </section>
  );
}
