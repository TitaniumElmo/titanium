import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useAgora, useMundo } from "../api";
import { BotaoLink, Cartao, EstadoVazio } from "../componentes/base";
import { CartaoExposicao } from "../componentes/CartaoExposicao";
import { Pagina } from "../componentes/Pagina";
import { SeloGatilho } from "../componentes/Selos";
import { achadoAberto, cronograma, relatorio } from "../derivados";
import { dataCurta, diaDaSemana, dolares, hora, isoDia } from "../formato";
import { NOME_AGENTE } from "../marca";
import type { Gravidade } from "../tipos";
import { cn, IconeGrade } from "../util";

const DIA = 86_400_000;

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
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {(["irregular", "risco", "ok"] as Gravidade[]).map((g) => (
          <Link
            key={g}
            to={g === "ok" ? "/funcionarios" : "/achados"}
            className="rounded-cartao border border-borda bg-superficie p-5 transition-colors hover:border-fraco"
          >
            <span className="flex items-center gap-2 text-sm text-apoio">
              <span className={cn("size-2 rounded-full", ESTILO_CARTAO[g].ponto)} />
              {ESTILO_CARTAO[g].rotulo}
            </span>
            <span className="mt-2 block text-display tabular-nums">{dados.contagem[g]}</span>
            <span className="text-xs text-fraco">{ESTILO_CARTAO[g].ajuda}</span>
          </Link>
        ))}
        <CartaoExposicao total={dados.rel.exposicao_total} porFuncao={dados.rel.exposicao_por_funcao.slice(0, 2)} />
      </div>

      <Cartao className="flex flex-col gap-4">
        <div>
          <h2 className="text-h3">Funil do ciclo</h2>
          <p className="text-sm text-apoio">Onde cada pendência está, do achado à conferência.</p>
        </div>
        <ol className="grid gap-3 md:grid-cols-4">
          {dados.funil.map((f, i) => (
            <li key={f.rotulo} className="flex flex-col gap-2 rounded-controle bg-superficie-2 p-3">
              <span className="flex items-center justify-between text-xs text-apoio">
                <span>{f.rotulo}</span>
                <span className="tabular-nums text-fraco">{i + 1}/4</span>
              </span>
              <span className="text-h1 tabular-nums">{f.valor}</span>
              <span className="h-1.5 overflow-hidden rounded-full bg-borda">
                <span
                  className={cn("block h-full rounded-full", i === 3 ? "bg-ok-borda" : "bg-apoio")}
                  style={{ width: `${(f.valor / maiorFunil) * 100}%` }}
                />
              </span>
              <span className="text-xs text-fraco">{f.ajuda}</span>
            </li>
          ))}
        </ol>
      </Cartao>

      <div className="grid gap-4 lg:grid-cols-2">
        <Cartao className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-label">Próximos 7 dias</h2>
            <Link to="/cronograma" className="text-label text-apoio hover:text-texto">
              cronograma →
            </Link>
          </div>
          {dados.proximos.length === 0 ? (
            <p className="py-6 text-center text-sm text-fraco">Nada previsto para a semana.</p>
          ) : (
            <ul className="flex flex-col">
              {dados.proximos.slice(0, 6).map((item) => (
                <li key={item.id} className="grid grid-cols-[5.5rem_1fr] gap-3 border-t border-borda py-2.5 text-sm first:border-t-0">
                  <span className={cn("font-mono text-xs", item.status === "atrasado" ? "text-irregular" : "text-apoio")}>
                    {diaDaSemana(item.data)}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate">{item.titulo}</span>
                    <span className="block text-xs text-fraco">{item.nome ?? item.funcao}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Cartao>

        <Cartao className="flex flex-col gap-3">
          <h2 className="text-label">Última execução do agente</h2>
          {ultima ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <SeloGatilho gatilho={ultima.disparado_por} comPrefixo />
              </div>
              <p className="text-sm text-apoio">{ultima.descricao_disparo}</p>
              <dl className="grid grid-cols-3 gap-3">
                <div className="rounded-controle bg-superficie-2 px-3 py-2">
                  <dt className="text-xs text-fraco">Hora</dt>
                  <dd className="font-mono text-sm">
                    {dataCurta(ultima.iniciada_em)} {hora(ultima.iniciada_em)}
                  </dd>
                </div>
                <div className="rounded-controle bg-superficie-2 px-3 py-2">
                  <dt className="text-xs text-fraco">Passos</dt>
                  <dd className="font-mono text-sm">{eventosUltima.length}</dd>
                </div>
                <div className="rounded-controle bg-superficie-2 px-3 py-2">
                  <dt className="text-xs text-fraco">Custo</dt>
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
