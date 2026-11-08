import { useState } from "react";
import { dataCurta, hora, ROTULO_ETAPA } from "../formato";
import type { EntradaHistorico, Etapa, Evento, Pendencia } from "../tipos";
import { cn } from "../util";

type Faixa = "agente" | "tecnico";
type EstadoEtapa = "concluida" | "atual" | "futura" | "pulada";
type EtapaLinha = Exclude<Etapa, "cobrar_atraso">;

const ORDEM: EtapaLinha[] = ["encontrar", "buscar_prova", "pedir_correcao", "corrigir", "comprovar", "conferir"];

const FAIXA: Record<EtapaLinha, Faixa> = {
  encontrar: "agente",
  buscar_prova: "agente",
  pedir_correcao: "agente",
  corrigir: "tecnico",
  comprovar: "tecnico",
  conferir: "agente",
};

const ROTULO_CURTO: Record<EtapaLinha, string> = {
  encontrar: "Encontrar",
  buscar_prova: "Buscar prova",
  pedir_correcao: "Pedir correção",
  corrigir: "Corrigir",
  comprovar: "Comprovar",
  conferir: "Conferir",
};

type EtapaCalculada = { etapa: EtapaLinha; estado: EstadoEtapa; entrada?: EntradaHistorico };

export function calcularEtapas(p: Pendencia): EtapaCalculada[] {
  const feitas = new Map<EtapaLinha, EntradaHistorico>();
  for (const h of p.historico) if (h.etapa !== "cobrar_atraso") feitas.set(h.etapa, h);
  if (p.status === "reaberta") {
    feitas.delete("corrigir");
    feitas.delete("comprovar");
    feitas.delete("conferir");
  }
  const ultimo = ORDEM.reduce((acc, etapa, i) => (feitas.has(etapa) ? i : acc), -1);
  const esperandoRh = p.destino === "rh" && ORDEM[ultimo] === "buscar_prova" && p.status !== "fechada";
  let atualMarcada = false;
  return ORDEM.map((etapa, i) => {
    const entrada = feitas.get(etapa);
    if (esperandoRh && etapa === "buscar_prova") {
      atualMarcada = true;
      return { etapa, estado: "atual", entrada };
    }
    if (entrada) return { etapa, estado: "concluida", entrada };
    if (p.status === "fechada" || i < ultimo) return { etapa, estado: "pulada" };
    if (!atualMarcada) {
      atualMarcada = true;
      return { etapa, estado: "atual" };
    }
    return { etapa, estado: "futura" };
  });
}

function cobrancas(p: Pendencia): EntradaHistorico[] {
  return p.historico.filter((h) => h.etapa === "cobrar_atraso");
}

function Ponto({ faixa, estado, pequeno = false }: { faixa: Faixa; estado: EstadoEtapa; pequeno?: boolean }) {
  const tamanho = pequeno ? "size-2.5" : "size-3.5";
  const corCheia = faixa === "agente" ? "bg-acento border-acento" : "bg-apoio border-apoio";
  const corBorda = faixa === "agente" ? "border-acento" : "border-apoio";
  return (
    <span
      className={cn(
        "block shrink-0 rounded-full border-2",
        tamanho,
        estado === "concluida" && corCheia,
        estado === "atual" && cn(corCheia, "animar-pulsar"),
        estado === "futura" && cn(corBorda, "bg-superficie opacity-60"),
        estado === "pulada" && "scale-75 border-dashed border-fraco bg-transparent opacity-50",
      )}
    />
  );
}

function SeloCobranca({ p }: { p: Pendencia }) {
  const lista = cobrancas(p);
  const ultima = lista[lista.length - 1];
  if (p.escalada)
    return (
      <span className="rounded-selo border border-irregular-borda/40 bg-irregular-fundo px-2 py-0.5 text-xs font-medium text-irregular">
        escalado ao coordenador
      </span>
    );
  if (!ultima) return null;
  return (
    <span className="rounded-selo border border-borda bg-superficie-2 px-2 py-0.5 text-xs font-medium text-apoio">
      cobrado em {dataCurta(ultima.ts)}
    </span>
  );
}

function rotuloAtor(e: EtapaCalculada): string | null {
  if (e.entrada?.ator === "rh") return "RH";
  return null;
}

function Completo({ p }: { p: Pendencia }) {
  const etapas = calcularEtapas(p);
  const [selecionada, setSelecionada] = useState<EtapaLinha | null>(null);
  const detalhe = etapas.find((e) => e.etapa === selecionada);

  const celula = (e: EtapaCalculada, faixa: Faixa) => {
    if (FAIXA[e.etapa] !== faixa) return <div key={e.etapa} className="relative h-full" />;
    const ator = rotuloAtor(e);
    return (
      <button
        key={e.etapa}
        type="button"
        onClick={() => setSelecionada(selecionada === e.etapa ? null : e.etapa)}
        title={e.entrada?.detalhe ?? ROTULO_ETAPA[e.etapa]}
        className={cn(
          "group relative z-10 flex flex-col items-center gap-1.5 rounded-controle px-1 py-2 text-center transition-colors hover:bg-superficie-2",
          selecionada === e.etapa && "bg-superficie-2",
        )}
      >
        <Ponto faixa={faixa} estado={e.estado} />
        <span className={cn("text-xs leading-tight", e.estado === "futura" || e.estado === "pulada" ? "text-fraco" : "text-texto")}>
          {ROTULO_CURTO[e.etapa]}
        </span>
        <span className="font-mono text-xs text-fraco">
          {e.entrada ? dataCurta(e.entrada.ts) : e.estado === "pulada" ? <span className="font-sans">não se aplica</span> : "—"}
          {ator && <span className="ml-1 rounded-selo bg-superficie-2 px-1 text-apoio">{ator}</span>}
        </span>
      </button>
    );
  };

  return (
    <div className="flex flex-col gap-3">
      {p.status === "reaberta" && (
        <span className="self-start rounded-selo border border-risco-borda/40 bg-risco-fundo px-2 py-0.5 text-xs font-medium text-risco">
          reaberta: a conferência não confirmou a correção
        </span>
      )}

      <div className="hidden min-[600px]:block">
        {(["agente", "tecnico"] as Faixa[]).map((faixa) => (
          <div key={faixa} className="grid grid-cols-[72px_repeat(6,minmax(0,1fr))] items-start">
            <div className="flex h-full flex-col justify-start pt-2">
              <span
                className={cn(
                  "text-xs font-medium",
                  faixa === "agente" ? "text-acento" : "text-apoio",
                )}
              >
                {faixa === "agente" ? "Elmo" : "Técnico"}
              </span>
            </div>
            <div className="relative col-span-6 grid grid-cols-6">
              <span
                className={cn(
                  "absolute left-[8%] right-[8%] top-[15px] h-px",
                  faixa === "agente" ? "bg-acento/30" : "bg-apoio/30",
                )}
              />
              {etapas.map((e) => celula(e, faixa))}
            </div>
          </div>
        ))}
        {(p.escalada || cobrancas(p).length > 0) && (
          <div className="mt-1 pl-[72px]">
            <SeloCobranca p={p} />
          </div>
        )}
      </div>

      <ol className="flex flex-col min-[600px]:hidden">
        {etapas.map((e, i) => {
          const faixa = FAIXA[e.etapa];
          const ator = rotuloAtor(e);
          return (
            <li key={e.etapa} className="relative flex gap-3 pb-4 last:pb-0">
              {i < etapas.length - 1 && <span className="absolute left-[6px] top-4 h-full w-px bg-borda" />}
              <span className="pt-1">
                <Ponto faixa={faixa} estado={e.estado} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("text-sm", e.estado === "futura" || e.estado === "pulada" ? "text-fraco" : "text-texto")}>
                    {ROTULO_ETAPA[e.etapa]}
                  </span>
                  <span className={cn("text-xs font-medium", faixa === "agente" ? "text-acento" : "text-apoio")}>
                    {ator ?? (faixa === "agente" ? "Elmo" : "Técnico")}
                  </span>
                  {e.entrada && <span className="font-mono text-xs text-fraco">{dataCurta(e.entrada.ts)}</span>}
                </div>
                {e.entrada && <p className="mt-0.5 text-xs text-apoio">{e.entrada.detalhe}</p>}
                {e.etapa === "corrigir" && (
                  <span className="mt-1 inline-block">
                    <SeloCobranca p={p} />
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {detalhe && (
        <div className="animar-entrar hidden rounded-controle border border-borda bg-superficie-2 px-3 py-2 text-sm min-[600px]:block">
          <span className="font-medium">{ROTULO_ETAPA[detalhe.etapa]}</span>
          {detalhe.entrada ? (
            <span className="text-apoio">
              {" · "}
              {dataCurta(detalhe.entrada.ts)} {hora(detalhe.entrada.ts)} · {detalhe.entrada.detalhe}
            </span>
          ) : (
            <span className="text-fraco"> · {detalhe.estado === "pulada" ? "não se aplica a esta pendência" : "ainda não aconteceu"}</span>
          )}
        </div>
      )}
    </div>
  );
}

function Compacto({ p }: { p: Pendencia }) {
  const etapas = calcularEtapas(p);
  return (
    <span className="inline-flex items-center gap-1" aria-label="Etapas da pendência">
      {etapas.map((e, i) => (
        <span key={e.etapa} className="flex items-center gap-1" title={`${ROTULO_ETAPA[e.etapa]}: ${e.estado}`}>
          <Ponto faixa={FAIXA[e.etapa]} estado={e.estado} pequeno />
          {i < etapas.length - 1 && <span className="h-px w-1.5 bg-borda" />}
        </span>
      ))}
    </span>
  );
}

type EtapaExecucao = "ler" | "encontrar" | "buscar_prova" | "pedir_correcao" | "conferir" | "cobrar_atraso";

const ORDEM_EXECUCAO: EtapaExecucao[] = ["ler", "encontrar", "buscar_prova", "pedir_correcao", "conferir", "cobrar_atraso"];

const ROTULO_EXECUCAO: Record<EtapaExecucao, string> = {
  ler: "Ler",
  encontrar: "Encontrar",
  buscar_prova: "Buscar prova",
  pedir_correcao: "Pedir correção",
  conferir: "Conferir",
  cobrar_atraso: "Cobrar atraso",
};

function etapaDoEvento(e: Evento): EtapaExecucao | null {
  switch (e.ferramenta) {
    case "ler_fonte":
    case "mapear_colunas":
    case "extrair_ficha":
    case "reextrair_campo":
      return "ler";
    case "audita_linha":
    case "auditar_ficha":
    case "conferir_ficha_de_papel":
    case "historico_da_empresa":
    case "consulta_ca":
    case "exigencia_funcao":
    case "buscar_ca_proximo":
      return "encontrar";
    case "criar_pendencia":
      return e.entrada.destino === "rh" ? "buscar_prova" : "pedir_correcao";
    case "fechar_pendencia":
      return "conferir";
    case "cobrar_atraso":
      return "cobrar_atraso";
    default:
      return null;
  }
}

function Execucao({ eventos, rodando }: { eventos: Evento[]; rodando: boolean }) {
  const alcancadas = new Set<EtapaExecucao>();
  let ultima: EtapaExecucao | null = null;
  for (const e of eventos) {
    const etapa = etapaDoEvento(e);
    if (etapa) {
      alcancadas.add(etapa);
      ultima = etapa;
    }
  }
  return (
    <ol className="grid grid-cols-3 gap-y-3 min-[600px]:grid-cols-6">
      {ORDEM_EXECUCAO.map((etapa) => {
        const feita = alcancadas.has(etapa);
        const estado: EstadoEtapa = feita ? (rodando && etapa === ultima ? "atual" : "concluida") : rodando ? "futura" : "pulada";
        return (
          <li key={etapa} className="relative flex flex-col items-center gap-1.5 text-center">
            <Ponto faixa="agente" estado={estado} />
            <span className={cn("text-xs", feita ? "text-texto" : "text-fraco")}>{ROTULO_EXECUCAO[etapa]}</span>
          </li>
        );
      })}
    </ol>
  );
}

type Props =
  | { modo: "completo"; pendencia: Pendencia }
  | { modo: "compacto"; pendencia: Pendencia }
  | { modo: "execucao"; eventos: Evento[]; rodando: boolean };

export function CicloPendencia(props: Props) {
  if (props.modo === "execucao") return <Execucao eventos={props.eventos} rodando={props.rodando} />;
  if (props.modo === "compacto") return <Compacto p={props.pendencia} />;
  return <Completo p={props.pendencia} />;
}
