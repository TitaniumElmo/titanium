import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useAgora, useMundo } from "../api";
import { BotaoLink, Cartao, EstadoVazio } from "../componentes/base";
import { CartaoExposicao } from "../componentes/CartaoExposicao";
import { Pagina } from "../componentes/Pagina";
import { SeloGatilho } from "../componentes/Selos";
import { achadoAberto, cronograma, relatorio } from "../derivados";
import { dataCurta, diaDaSemana, dolares, hora, isoDia, tituloLimpo } from "../formato";
import { NOME_AGENTE } from "../marca";
import type { Gravidade } from "../tipos";
import { cn, IconeGrade } from "../util";

const DIA = 86_400_000;
const FUNDO_PRETO = "bg-superficie bg-[radial-gradient(120%_90%_at_100%_0%,var(--cartao-brilho),transparent_60%)]";
const FUNDO_URGENTE = "bg-gradient-to-b from-cartao-urgente-topo via-cartao-urgente-meio to-cartao-urgente-base";

const ESTILO_CARTAO: Record<Gravidade, { ponto: string; rotulo: string; ajuda: string }> = {
  irregular: { ponto: "bg-irregular-borda", rotulo: "Irregular", ajuda: "achados em aberto" },
  risco: { ponto: "bg-risco-borda", rotulo: "Risco", ajuda: "dependem de prova" },
  ok: { ponto: "bg-ok-borda", rotulo: "Ok", ajuda: "linhas sem lacuna" },
};

export function VisaoGeral() {
  const mundo = useMundo();
  const hoje = isoDia(useAgora(60_000));

  const dados = useMemo(() => {
    const abertos = mundo.achados.filter((a) => achadoAberto(a, mundo.pendencias));
    const linhasComAchado = new Set(mundo.achados.map((a) => `${a.funcionario_id}-${a.linha}`));
    const contagem: Record<Gravidade, number> = {
      irregular: abertos.filter((a) => a.gravidade === "irregular").length,
      risco: abertos.filter((a) => a.gravidade === "risco").length,
      ok: mundo.linhas.filter((l) => !linhasComAchado.has(`${l.funcionario_id}-${l.linha}`)).length,
    };
    const base = new Date(`${hoje}T12:00:00`).getTime();
    const proximos = cronograma(mundo, hoje, hoje, isoDia(base + 7 * DIA)).filter((i) => i.status !== "feito");
    const rel = relatorio(mundo, hoje, 7);
    const funil = [
      { rotulo: "Encontradas", valor: mundo.pendencias.length, ajuda: "pendências abertas pelo agente" },
      {
        rotulo: "Aguardando o técnico ou o RH",
        valor: mundo.pendencias.filter((p) => p.status !== "fechada").length,
        ajuda: "abertas, aguardando ou reabertas",
      },
      {
        rotulo: "Corrigidas",
        valor: mundo.pendencias.filter((p) => p.historico.some((h) => h.etapa === "comprovar")).length,
        ajuda: "a correção chegou pela planilha",
      },
      { rotulo: "Conferidas", valor: mundo.pendencias.filter((p) => p.status === "fechada").length, ajuda: "o agente conferiu e fechou" },
    ];
    return { contagem, proximos, rel, funil };
  }, [mundo, hoje]);

  const ultima = mundo.auditorias.find((a) => a.status === "concluida");
  const eventosUltima = ultima ? (mundo.eventos[ultima.id] ?? []) : [];
  const maiorFunil = Math.max(...dados.funil.map((f) => f.valor), 1);

  if (!mundo.fonte) {
    return (
      <Pagina titulo="Visão geral" comPeriodo>
        <EstadoVazio
          icone={IconeGrade}
          titulo="Sem dados para resumir"
          descricao="Depois da primeira auditoria, esta página mostra o funil do ciclo e a exposição potencial máxima."
          acao={
            <BotaoLink para="/fontes" variante="primario">
              Conectar planilha
            </BotaoLink>
          }
        />
      </Pagina>
    );
  }

  return (
    <Pagina titulo="Visão geral" comPeriodo>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
          <section aria-label="Situação das fichas" className="grid grid-cols-3 gap-2 sm:gap-3">
            {(["irregular", "risco", "ok"] as Gravidade[]).map((g) => {
              const urgente = g === "irregular" && dados.contagem[g] > 0;
              return (
                <Link
                  key={g}
                  to={g === "ok" ? "/funcionarios" : "/achados"}
                  className={cn(
                    "flex min-w-0 flex-col gap-2 rounded-cartao border border-borda p-3 transition-colors hover:border-fraco focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-acento sm:gap-3 sm:p-5",
                    urgente ? FUNDO_URGENTE : FUNDO_PRETO,
                  )}
                >
                  <span className={cn("text-xs font-semibold uppercase tracking-sobrescrito sm:text-sm", urgente ? "text-irregular" : "text-apoio")}>
                    {ESTILO_CARTAO[g].rotulo}
                  </span>
                  <span className={cn("inline-flex w-fit items-center rounded-full px-3 py-1.5 sm:px-4 sm:py-2", urgente ? "bg-selo-claro text-selo-claro-texto" : "bg-superficie-2 text-texto")}>
                    <span className="text-2xl font-semibold tabular-nums sm:text-3xl sm:leading-none">{dados.contagem[g]}</span>
                  </span>
                  <span className="text-xs leading-snug text-apoio sm:text-base">{ESTILO_CARTAO[g].ajuda}</span>
                </Link>
              );
            })}
          </section>

          <Cartao className={cn("flex flex-1 flex-col gap-4 sm:p-6", FUNDO_PRETO)}>
            <div>
              <h2 className="text-base font-semibold sm:text-lg">Funil do ciclo</h2>
              <p className="text-sm text-apoio sm:text-base">Onde cada pendência está, do achado à conferência.</p>
            </div>
            <ol className="grid grid-cols-2 gap-3">
              {dados.funil.map((f, i) => (
                <li key={f.rotulo} className="flex flex-col gap-2 rounded-controle bg-superficie-2 p-3 sm:p-4">
                  <span className="flex items-center justify-between gap-2 text-sm text-apoio">
                    <span>{f.rotulo}</span>
                    <span className="tabular-nums text-fraco">{i + 1}/4</span>
                  </span>
                  <span className="text-h1 tabular-nums">{f.valor}</span>
                  <span className="h-1.5 overflow-hidden rounded-full bg-borda">
                    <span className={cn("block h-full rounded-full", i === 3 ? "bg-ok-borda" : "bg-apoio")} style={{ width: `${(f.valor / maiorFunil) * 100}%` }} />
                  </span>
                  <span className="text-sm text-fraco">{f.ajuda}</span>
                </li>
              ))}
            </ol>
          </Cartao>
        </div>
        <CartaoExposicao total={dados.rel.exposicao_total} porFuncao={dados.rel.exposicao_por_funcao.slice(0, 2)} className="lg:self-start" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Cartao className={cn("flex flex-col gap-3 sm:p-6", FUNDO_PRETO)}>
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold sm:text-lg">Próximos 7 dias</h2>
            <Link to="/cronograma" className="text-sm text-apoio hover:text-texto">
              cronograma →
            </Link>
          </div>
          {dados.proximos.length === 0 ? (
            <p className="py-6 text-center text-sm text-fraco">Nada previsto para a semana.</p>
          ) : (
            <ul className="flex flex-col">
              {dados.proximos.slice(0, 6).map((item) => (
                <li key={item.id} className="grid grid-cols-[6rem_1fr] gap-3 border-t border-borda py-3 text-sm first:border-t-0 sm:text-base">
                  <span className={cn("font-mono text-xs", item.status === "atrasado" ? "text-irregular" : "text-apoio")}>
                    {diaDaSemana(item.data)}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate">{tituloLimpo(item.titulo)}</span>
                    <span className="block text-sm text-apoio">{item.nome ?? item.funcao}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Cartao>

        <Cartao className={cn("flex flex-col gap-3 sm:p-6", FUNDO_PRETO)}>
          <h2 className="text-base font-semibold sm:text-lg">Última execução do agente</h2>
          {ultima ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <SeloGatilho gatilho={ultima.disparado_por} comPrefixo />
              </div>
              <p className="text-sm text-apoio sm:text-base">{ultima.descricao_disparo}</p>
              <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-controle bg-superficie-2 px-3 py-2">
                  <dt className="text-sm text-apoio">Hora</dt>
                  <dd className="font-mono text-sm">
                    {dataCurta(ultima.iniciada_em)} {hora(ultima.iniciada_em)}
                  </dd>
                </div>
                <div className="rounded-controle bg-superficie-2 px-3 py-2">
                  <dt className="text-sm text-apoio">Passos</dt>
                  <dd className="font-mono text-sm">{eventosUltima.length}</dd>
                </div>
                <div className="rounded-controle bg-superficie-2 px-3 py-2">
                  <dt className="text-sm text-apoio">Custo</dt>
                  <dd className="font-mono text-sm">{dolares(eventosUltima.reduce((s, e) => s + e.custo_usd, 0))}</dd>
                </div>
              </dl>
              <BotaoLink para={`/agente?execucao=${ultima.id}`} variante="primario" className="self-start">
                Ver ao vivo
              </BotaoLink>
            </>
          ) : (
            <p className="text-sm text-fraco">O {NOME_AGENTE} ainda não executou.</p>
          )}
        </Cartao>
      </div>
    </Pagina>
  );
}
