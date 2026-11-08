import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAgora, useMundo } from "../api";
import { EstadoVazio, Segmentos } from "../componentes/base";
import { CartaoAchado } from "../componentes/CartaoAchado";
import { CartaoAba } from "../componentes/ResumoHistorico";
import { CicloPendencia } from "../componentes/CicloPendencia";
import { Pagina } from "../componentes/Pagina";
import { SeloDestino, SeloEscalado, SeloGatilho, SeloStatus, SeloUrgente } from "../componentes/Selos";
import { ehUrgente } from "../derivados";
import { data, dataCurta, hora, isoDia, ROTULO_ETAPA, ROTULO_GATILHO, ROTULO_STATUS, rotuloRegra } from "../formato";
import { NOME_AGENTE } from "../marca";
import type { Destino, Pendencia, StatusPendencia } from "../tipos";
import { cn, IconeAlerta, IconeAtividade, IconeCalendario, IconeFechar, IconeLista } from "../util";

function useRecemFechadas(pendencias: Pendencia[]): Map<string, StatusPendencia> {
  const anterior = useRef<Map<string, StatusPendencia>>(new Map(pendencias.map((p) => [p.id, p.status])));
  const [recentes, setRecentes] = useState<Map<string, StatusPendencia>>(new Map());

  useEffect(() => {
    const novas: [string, StatusPendencia][] = [];
    for (const p of pendencias) {
      const antes = anterior.current.get(p.id);
      if (antes && antes !== "fechada" && p.status === "fechada") novas.push([p.id, antes]);
    }
    anterior.current = new Map(pendencias.map((p) => [p.id, p.status]));
    if (!novas.length) return;
    setRecentes((atual) => new Map([...atual, ...novas]));
    const id = window.setTimeout(() => {
      setRecentes((atual) => {
        const copia = new Map(atual);
        novas.forEach(([pid]) => copia.delete(pid));
        return copia;
      });
    }, 2600);
    return () => window.clearTimeout(id);
  }, [pendencias]);

  return recentes;
}

function Prazo({ prazo, fechada, hoje }: { prazo: string; fechada: boolean; hoje: string }) {
  const vencido = !fechada && prazo < hoje;
  return (
    <span className={cn("font-mono text-xs", vencido ? "text-irregular" : "text-apoio")}>
      {vencido ? "venceu " : "até "}
      {dataCurta(prazo)}
    </span>
  );
}

function LinhaPendencia({
  p,
  hoje,
  recemFechada,
  aoAbrir,
}: {
  p: Pendencia;
  hoje: string;
  recemFechada: boolean;
  aoAbrir: () => void;
}) {
  const mundo = useMundo();
  const achado = mundo.achados.find((a) => a.id === p.achado_id);
  return (
    <li>
      <button
        type="button"
        onClick={aoAbrir}
        className={cn(
          "grid w-full gap-3 rounded-cartao border border-borda bg-superficie bg-[radial-gradient(120%_90%_at_100%_0%,var(--cartao-brilho),transparent_60%)] p-4 text-left transition-colors hover:border-fraco sm:p-5 md:grid-cols-[1fr_auto] md:items-center",
          (p.prioridade === "alta" || ehUrgente(p, hoje)) && "border-l-4 border-l-irregular-borda hover:border-l-irregular-borda",
          recemFechada && "animar-fechada",
        )}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-fraco">{p.id}</span>
            <span className="text-label">{p.funcionario_nome}</span>
            <SeloDestino destino={p.destino} />
            {ehUrgente(p, hoje) && <SeloUrgente />}
            {p.escalada && <SeloEscalado />}
            {recemFechada && (
              <span className="rounded-selo border border-ok-borda/40 bg-ok-fundo px-2 py-0.5 text-xs font-medium text-ok">fechada ✓</span>
            )}
          </div>
          <p className="mt-1 line-clamp-2 text-sm text-texto sm:text-base" title={p.acao}>{p.acao}</p>
          {achado && (
            <p className="mt-2 line-clamp-2 text-sm text-apoio" title={achado.evidencia}>
              <span className="font-medium text-texto">Por quê: </span>
              {rotuloRegra(achado.regra)} · {achado.evidencia}
            </p>
          )}
          <p className="mt-1.5 text-xs text-fraco">Disparado por: {ROTULO_GATILHO[p.disparado_por]}</p>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 md:justify-end">
          <Prazo prazo={p.prazo} fechada={p.status === "fechada"} hoje={hoje} />
          <span className="text-xs tabular-nums text-apoio" title="Cobranças enviadas">
            {p.cobrancas} {p.cobrancas === 1 ? "cobrança" : "cobranças"}
          </span>
          <CicloPendencia modo="compacto" pendencia={p} />
        </div>
      </button>
    </li>
  );
}

function Detalhe({ p, hoje, aoFechar }: { p: Pendencia; hoje: string; aoFechar: () => void }) {
  const mundo = useMundo();
  const achado = mundo.achados.find((a) => a.id === p.achado_id);

  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [aoFechar]);

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label={`Pendência ${p.id}`}>
      <button type="button" className="absolute inset-0 bg-fundo/70 backdrop-blur-sm" aria-label="Fechar" onClick={aoFechar} />
      <aside className="animar-entrar absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col overflow-y-auto border-l border-borda bg-fundo">
        <header className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-borda bg-superficie px-5 py-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-fraco">{p.id}</span>
              <SeloStatus status={p.status} />
              <SeloDestino destino={p.destino} />
              {ehUrgente(p, hoje) && <SeloUrgente />}
              {p.escalada && <SeloEscalado />}
            </div>
            <h2 className="mt-2 text-h2">{p.funcionario_nome}</h2>
            <p className="mt-1 text-body">{p.acao}</p>
          </div>
          <button
            type="button"
            onClick={aoFechar}
            className="flex size-9 shrink-0 items-center justify-center rounded-controle text-apoio hover:bg-superficie-2"
            aria-label="Fechar detalhe"
          >
            <IconeFechar className="size-5" />
          </button>
        </header>

        <div className="flex flex-col gap-5 p-5">
          <div className="grid grid-cols-3 gap-2 text-sm sm:gap-3">
            <div className="rounded-controle bg-superficie px-3 py-2.5">
              <div className="text-xs text-fraco">Prazo</div>
              <Prazo prazo={p.prazo} fechada={p.status === "fechada"} hoje={hoje} />
            </div>
            <div className="rounded-controle bg-superficie px-3 py-2.5">
              <div className="text-xs text-fraco">Cobranças</div>
              <span className="text-sm tabular-nums">{p.cobrancas}</span>
            </div>
            <div className="rounded-controle bg-superficie px-3 py-2.5">
              <div className="text-xs text-fraco">Prioridade</div>
              <span className={cn("text-sm", p.prioridade === "alta" && "text-irregular")}>{p.prioridade}</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <SeloGatilho gatilho={p.disparado_por} comPrefixo />
            {mundo.fonte && (
              <a
                href={mundo.fonte.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-9 items-center rounded-controle border border-borda bg-superficie px-3.5 text-sm font-medium hover:border-fraco"
              >
                Abrir a planilha ↗
              </a>
            )}
          </div>
          <p className="text-sm text-apoio">
            <span className="text-fraco">Motivo: </span>
            {p.motivo}
          </p>

          <section className="rounded-cartao border border-borda bg-superficie p-4">
            <h3 className="mb-3 text-label text-apoio">Ciclo</h3>
            <CicloPendencia modo="completo" pendencia={p} />
          </section>

          {achado && (
            <section className="flex flex-col gap-2">
              <h3 className="text-label text-apoio">Achado de origem</h3>
              <CartaoAchado achado={achado} compacto />
            </section>
          )}

          <section className="flex flex-col gap-2">
            <h3 className="text-label text-apoio">Histórico</h3>
            <ol className="flex flex-col">
              {[...p.historico].reverse().map((h, i) => (
                <li key={`${h.ts}-${i}`} className="grid grid-cols-[5.5rem_1fr] gap-3 border-t border-borda py-2.5 text-sm first:border-t-0">
                  <span className="font-mono text-xs text-fraco">
                    {dataCurta(h.ts)} {hora(h.ts)}
                  </span>
                  <span>
                    <span className="font-medium">{ROTULO_ETAPA[h.etapa]}</span>
                    <span
                      className={cn(
                        "ml-2 text-xs font-medium",
                        h.ator === "agente" ? "text-acento" : "text-apoio",
                      )}
                    >
                      {h.ator === "agente" ? NOME_AGENTE : h.ator === "rh" ? "RH" : "Técnico"}
                    </span>
                    <span className="block text-apoio">{h.detalhe}</span>
                  </span>
                </li>
              ))}
            </ol>
          </section>
          <p className="text-xs text-fraco">
            A correção chega pela própria planilha. O {NOME_AGENTE} confere na leitura seguinte e fecha ou reabre a pendência. Prazo
            final: {data(p.prazo)}.
          </p>
        </div>
      </aside>
    </div>
  );
}

export function Pendencias() {
  const mundo = useMundo();
  const instante = useAgora(30_000);
  const hoje = isoDia(instante);
  const [parametros, setParametros] = useSearchParams();
  const [aba, setAba] = useState<StatusPendencia>("aberta");
  const [destino, setDestino] = useState<"todos" | Destino>("todos");
  const recentes = useRecemFechadas(mundo.pendencias);

  const selecionadaId = parametros.get("p");
  const selecionada = mundo.pendencias.find((p) => p.id === selecionadaId);

  useEffect(() => {
    if (selecionada) setAba(selecionada.status);
  }, [selecionadaId]);

  const naAba = (p: Pendencia) => p.status === aba || recentes.get(p.id) === aba;
  const doDestino = (p: Pendencia) => destino === "todos" || p.destino === destino;
  const lista = mundo.pendencias
    .filter((p) => naAba(p) && doDestino(p))
    .sort((a, b) => {
      const peso = (p: Pendencia) => (ehUrgente(p, hoje) ? 0 : p.prioridade === "alta" ? 1 : 2);
      return peso(a) - peso(b) || a.prazo.localeCompare(b.prazo);
    });
  const urgentes = mundo.pendencias.filter((p) => ehUrgente(p, hoje));

  const contagem = (s: StatusPendencia) => mundo.pendencias.filter((p) => p.status === s && doDestino(p)).length;

  return (
    <Pagina titulo="Pendências" descricao={`Abertas pelo ${NOME_AGENTE} e conferidas por ele na leitura seguinte da planilha.`}>
      {urgentes.length > 0 && (
        <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-cartao border border-irregular-borda/40 bg-irregular-fundo px-4 py-3">
          <span className="text-label text-irregular">
            {urgentes.length} {urgentes.length === 1 ? "pendência urgente" : "pendências urgentes"}: trabalhador sem proteção hoje
          </span>
          <span className="flex flex-wrap gap-1.5">
            {urgentes.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setParametros({ p: p.id })}
                className="rounded-selo border border-irregular-borda/40 px-2 py-0.5 text-xs font-medium text-irregular hover:bg-superficie"
              >
                <span className="font-mono">{p.id}</span> · {p.funcionario_nome.split(" ")[0]} · até {dataCurta(p.prazo)}
              </button>
            ))}
          </span>
        </div>
      )}
      <section role="radiogroup" aria-label="Status" className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
        <CartaoAba rotulo="Abertas" valor={contagem("aberta")} detalhe="ainda sem correção" selecionado={aba === "aberta"} aoClicar={() => setAba("aberta")} icone={<IconeLista className="size-full" />} />
        <CartaoAba rotulo="Aguardando" valor={contagem("aguardando")} detalhe="conferindo na próxima leitura" selecionado={aba === "aguardando"} aoClicar={() => setAba("aguardando")} icone={<IconeCalendario className="size-full" />} />
        <CartaoAba
          rotulo="Reabertas"
          valor={contagem("reaberta")}
          detalhe="correção não confirmada"
          urgente={contagem("reaberta") > 0}
          selecionado={aba === "reaberta"}
          aoClicar={() => setAba("reaberta")}
          icone={<IconeAlerta className="size-full" />}
        />
        <CartaoAba rotulo="Fechadas" valor={contagem("fechada")} detalhe="o problema sumiu na planilha" selecionado={aba === "fechada"} aoClicar={() => setAba("fechada")} icone={<IconeAtividade className="size-full" />} />
      </section>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmentos
          rotulo="Destino"
          valor={destino}
          aoMudar={setDestino}
          opcoes={[
            { valor: "todos", rotulo: "Todos" },
            { valor: "tecnico", rotulo: "Técnico" },
            { valor: "rh", rotulo: "RH" },
          ]}
        />
      </div>

      {lista.length === 0 ? (
        <EstadoVazio
          icone={IconeLista}
          titulo={`Nenhuma pendência ${ROTULO_STATUS[aba].toLowerCase()}`}
          descricao={
            mundo.fonte
              ? `O ${NOME_AGENTE} abre pendências para o técnico ou para o RH e confere sozinho quando a correção chega pela planilha.`
              : "Conecte a planilha para o agente começar."
          }
        />
      ) : (
        <ol className="flex flex-col gap-2">
          {lista.map((p) => (
            <LinhaPendencia
              key={p.id}
              p={p}
              hoje={hoje}
              recemFechada={recentes.has(p.id)}
              aoAbrir={() => setParametros({ p: p.id })}
            />
          ))}
        </ol>
      )}

      {selecionada && <Detalhe p={selecionada} hoje={hoje} aoFechar={() => setParametros({})} />}
    </Pagina>
  );
}
