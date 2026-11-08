import { useMemo } from "react";
import { Link } from "react-router-dom";
import { agora, useAgora, useMundo, useProximaLeitura } from "../api";
import { BotaoLink, EstadoVazio } from "../componentes/base";
import { Pagina } from "../componentes/Pagina";
import { cronograma, ehUrgente, resumoFuncionarios } from "../derivados";
import { dataCurta, diaDaSemana, hora, isoDia } from "../formato";
import { NOME_AGENTE } from "../marca";
import type { Gatilho, Pendencia } from "../tipos";
import { cn, IconeAtividade } from "../util";

const DIA = 86_400_000;

const MOTIVO_SIMPLES: Record<Gatilho, string> = {
  alteracao_planilha: "A planilha mudou",
  upload: "Uma planilha foi enviada",
  manual: "Conferência pedida",
  prazo_vencido: "Um prazo venceu",
  vencimento_futuro: "Um vencimento se aproxima",
  nova_base_caepi: "A base de CAs do governo mudou",
  email: "Chegou um e-mail",
  funcionario_novo: "Funcionário novo",
  rotina: "Conferência diária",
};

function saudacao(instante: number): string {
  const h = new Date(instante).getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

function diasAte(prazo: string, hoje: string): number {
  return Math.round((new Date(`${prazo}T12:00:00`).getTime() - new Date(`${hoje}T12:00:00`).getTime()) / DIA);
}

function rotuloPrazo(p: Pendencia, hoje: string): { texto: string; tom: "urgente" | "atrasada" | "normal" } {
  const dias = diasAte(p.prazo, hoje);
  if (dias < 0) return { texto: `Atrasada há ${-dias} ${dias === -1 ? "dia" : "dias"}`, tom: "atrasada" };
  if (dias === 0) return { texto: "Urgente · até hoje", tom: "urgente" };
  if (dias === 1) return { texto: "Urgente · até amanhã", tom: "urgente" };
  if (ehUrgente(p, hoje)) return { texto: `Urgente · até ${diaDaSemana(p.prazo)}`, tom: "urgente" };
  return { texto: `Até ${diaDaSemana(p.prazo)}`, tom: "normal" };
}

function comoResolver(p: Pendencia): string {
  if (p.status === "reaberta") {
    const conferencia = [...p.historico].reverse().find((h) => h.etapa === "conferir");
    return `A correção anterior não foi confirmada${conferencia ? `: ${conferencia.detalhe.replace(/^Reauditoria: /, "").replace(/\. Pendência reaberta$/, "")}` : ""}. Corrija e registre de novo na planilha.`;
  }
  if (/ficha física|conferir na ficha/i.test(p.acao)) return "Confira a ficha de papel na obra e acerte a planilha. O Elmo confere de novo sozinho.";
  return "Faça a entrega e registre na planilha, com a assinatura. O Elmo confere sozinho na próxima leitura.";
}

function Situacao({ semProtecao, aguardandoRh, emDia, total }: { semProtecao: number; aguardandoRh: number; emDia: number; total: number }) {
  const itens = [
    {
      valor: semProtecao,
      rotulo: semProtecao === 1 ? "trabalhador sem proteção hoje" : "trabalhadores sem proteção hoje",
      para: "/pendencias",
      ponto: semProtecao > 0 ? "bg-irregular-borda" : "bg-ok-borda",
    },
    {
      valor: aguardandoRh,
      rotulo: aguardandoRh === 1 ? "documento aguardando o RH" : "documentos aguardando o RH",
      para: "/pendencias",
      ponto: aguardandoRh > 0 ? "bg-risco-borda" : "bg-ok-borda",
    },
    {
      valor: `${emDia} de ${total}`,
      rotulo: "fichas em dia",
      para: "/funcionarios",
      ponto: emDia === total ? "bg-ok-borda" : "bg-risco-borda",
    },
  ];
  return (
    <section aria-label="Situação hoje" className="grid grid-cols-3 gap-2 sm:gap-3">
      {itens.map((i) => (
        <Link
          key={i.rotulo}
          to={i.para}
          className="flex flex-col gap-1 rounded-cartao border border-borda bg-superficie p-3 transition-colors hover:border-fraco sm:p-4"
        >
          <span className="flex items-center gap-2">
            <span className={cn("size-2.5 rounded-full", i.ponto)} />
            <span className="text-xl font-semibold tabular-nums sm:text-h2">{i.valor}</span>
          </span>
          <span className="text-xs leading-snug text-apoio sm:text-sm">{i.rotulo}</span>
        </Link>
      ))}
    </section>
  );
}

function CartaoTarefa({ p, funcao, hoje, urlPlanilha }: { p: Pendencia; funcao: string; hoje: string; urlPlanilha: string }) {
  const prazo = rotuloPrazo(p, hoje);
  const destaque = prazo.tom !== "normal" || p.escalada;
  return (
    <li
      className={cn(
        "rounded-cartao border bg-superficie p-4",
        destaque ? "border-irregular-borda/40 border-l-4 border-l-irregular-borda" : "border-borda",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded-selo px-2 py-0.5 text-xs font-semibold",
            prazo.tom === "normal" ? "bg-superficie-2 text-apoio" : "bg-irregular-fundo text-irregular",
          )}
        >
          {prazo.texto}
        </span>
        {p.escalada && <span className="text-xs font-medium text-irregular">escalada ao coordenador</span>}
        {p.cobrancas > 0 && !p.escalada && (
          <span className="text-xs text-apoio">
            {p.cobrancas} {p.cobrancas === 1 ? "cobrança enviada" : "cobranças enviadas"}
          </span>
        )}
      </div>
      <h3 className="mt-2 text-label">
        {p.funcionario_nome} <span className="font-normal text-apoio">· {funcao}</span>
      </h3>
      <p className="mt-1 text-body">{p.acao.charAt(0).toUpperCase() + p.acao.slice(1)}</p>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-3 border-t border-borda pt-3">
        <p className="max-w-xl text-sm text-apoio">
          <span className="font-medium text-texto">Como resolver: </span>
          {comoResolver(p)}
        </p>
        <span className="flex shrink-0 flex-wrap gap-2">
          <a
            href={urlPlanilha}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center justify-center gap-2 rounded-controle border border-borda bg-superficie-2 px-3.5 text-sm font-medium text-texto transition-colors hover:border-fraco"
          >
            Abrir a planilha ↗
          </a>
          <BotaoLink para={`/pendencias?p=${p.id}`} variante="fantasma">
            Ver detalhes
          </BotaoLink>
        </span>
      </div>
    </li>
  );
}

export function Inicio() {
  const mundo = useMundo();
  const instante = useAgora(30_000);
  const hoje = isoDia(instante);
  const segundos = useProximaLeitura();

  const dados = useMemo(() => {
    const abertas = mundo.pendencias.filter((p) => p.status !== "fechada");
    const doTecnico = abertas
      .filter((p) => p.destino === "tecnico")
      .sort((a, b) => {
        const peso = (p: Pendencia) => (p.prazo < hoje ? 0 : ehUrgente(p, hoje) ? 1 : p.prioridade === "alta" ? 2 : 3);
        return peso(a) - peso(b) || a.prazo.localeCompare(b.prazo);
      });
    const doRh = abertas.filter((p) => p.destino === "rh").sort((a, b) => a.prazo.localeCompare(b.prazo));
    const semProtecao = new Set(doTecnico.filter((p) => p.prazo < hoje || ehUrgente(p, hoje)).map((p) => p.funcionario_id)).size;
    const funcionarios = resumoFuncionarios(mundo, hoje);
    const base = new Date(`${hoje}T12:00:00`).getTime();
    const proximos = cronograma(mundo, hoje, hoje, isoDia(base + 7 * DIA)).filter(
      (i) => i.status !== "feito" && i.tipo !== "prazo_pendencia",
    );
    const limite = agora() - DIA;
    const recentes = mundo.atividade.filter((a) => new Date(a.ts).getTime() >= limite).slice(0, 5);
    return {
      doTecnico,
      doRh,
      semProtecao,
      emDia: funcionarios.filter((f) => f.status === "ok").length,
      total: funcionarios.length,
      proximos,
      recentes: recentes.length ? recentes : mundo.atividade.slice(0, 3),
      funcaoDe: Object.fromEntries(mundo.funcionarios.map((f) => [f.funcionario_id, f.funcao])),
    };
  }, [mundo, hoje]);

  if (!mundo.fonte) {
    return (
      <Pagina titulo={saudacao(instante)}>
        <EstadoVazio
          icone={IconeAtividade}
          titulo={`O ${NOME_AGENTE} ainda não tem o que vigiar`}
          descricao={`Conecte a planilha de controle de EPI. A partir daí, o ${NOME_AGENTE} confere cada entrega sozinho e mostra aqui o que precisa de você.`}
          acao={
            <BotaoLink para="/fontes" variante="primario">
              Conectar planilha
            </BotaoLink>
          }
        />
      </Pagina>
    );
  }

  const rodando = mundo.execucao_atual !== null || mundo.edicao !== null;
  const visiveis = dados.doTecnico.slice(0, 4);

  return (
    <Pagina
      titulo={saudacao(instante)}
      descricao="O que precisa de você hoje."
      acoes={
        <Link
          to={rodando ? "/agente" : "/historico"}
          className="inline-flex h-9 items-center gap-2 rounded-controle border border-borda bg-superficie px-3 text-sm text-apoio hover:border-fraco"
          title={`O ${NOME_AGENTE} lê a planilha a cada ${mundo.fonte.intervalo_s} segundos · próxima leitura em ${segundos ?? "—"} s`}
        >
          <span className={cn("size-2 rounded-full", rodando ? "animar-pulsar bg-acento" : "bg-ok-borda")} />
          <span className="tabular-nums">
            {dados.total} fichas vigiadas ·{" "}
            {rodando
              ? "conferindo agora"
              : `última conferência às ${mundo.fonte.ultima_leitura ? hora(mundo.fonte.ultima_leitura) : "—"}`}
          </span>
        </Link>
      }
    >
      <Situacao semProtecao={dados.semProtecao} aguardandoRh={dados.doRh.length} emDia={dados.emDia} total={dados.total} />

      <section className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-h3">
            Para resolver <span className="tabular-nums text-apoio">({dados.doTecnico.length})</span>
          </h2>
          <Link to="/pendencias" className="text-label text-apoio hover:text-texto">
            ver todas →
          </Link>
        </div>
        {visiveis.length === 0 ? (
          <p className="rounded-cartao border border-dashed border-borda px-4 py-8 text-center text-sm text-apoio">
            Nada para resolver agora. O {NOME_AGENTE} segue conferindo a planilha.
          </p>
        ) : (
          <ol className="flex flex-col gap-3">
            {visiveis.map((p) => (
              <CartaoTarefa key={p.id} p={p} funcao={dados.funcaoDe[p.funcionario_id] ?? ""} hoje={hoje} urlPlanilha={mundo.fonte?.url ?? ""} />
            ))}
          </ol>
        )}
        {dados.doTecnico.length > visiveis.length && (
          <Link to="/pendencias" className="self-start text-label text-apoio hover:text-texto">
            mais {dados.doTecnico.length - visiveis.length} em Pendências →
          </Link>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="flex flex-col gap-2 rounded-cartao border border-borda bg-superficie p-4">
          <h2 className="text-label">
            Aguardando o RH <span className="tabular-nums text-apoio">({dados.doRh.length})</span>
          </h2>
          {dados.doRh.length === 0 ? (
            <p className="text-sm text-apoio">Nenhum documento pendente.</p>
          ) : (
            <ul className="flex flex-col">
              {dados.doRh.map((p) => (
                <li key={p.id} className="border-t border-borda py-2 first:border-t-0">
                  <Link to={`/pendencias?p=${p.id}`} className="flex items-start justify-between gap-3 text-sm hover:text-texto">
                    <span>
                      <span className="font-medium">{p.funcionario_nome}</span>
                      <span className="block text-apoio">{p.acao.charAt(0).toUpperCase() + p.acao.slice(1)}</span>
                    </span>
                    <span className="shrink-0 text-xs tabular-nums text-apoio">até {dataCurta(p.prazo)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="flex flex-col gap-2 rounded-cartao border border-borda bg-superficie p-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-label">
              Próximos 7 dias <span className="tabular-nums text-apoio">({dados.proximos.length})</span>
            </h2>
            <Link to="/cronograma" className="text-xs font-medium text-apoio hover:text-texto">
              cronograma →
            </Link>
          </div>
          {dados.proximos.length === 0 ? (
            <p className="text-sm text-apoio">Nada previsto para a semana.</p>
          ) : (
            <ul className="flex flex-col">
              {dados.proximos.slice(0, 5).map((i) => (
                <li key={i.id} className="flex items-start justify-between gap-3 border-t border-borda py-2 text-sm first:border-t-0">
                  <span>
                    {i.titulo}
                    <span className="block text-apoio">{i.nome ?? (i.funcao ? `Função: ${i.funcao}` : "")}</span>
                  </span>
                  <span className={cn("shrink-0 text-xs tabular-nums", i.status === "atrasado" ? "text-irregular" : "text-apoio")}>
                    {diaDaSemana(i.data)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-label">O que o {NOME_AGENTE} fez nas últimas 24 horas</h2>
          <Link to="/historico" className="text-xs font-medium text-apoio hover:text-texto">
            histórico completo →
          </Link>
        </div>
        <ul className="rounded-cartao border border-borda bg-superficie">
          {dados.recentes.map((a) => (
            <li key={a.id} className="border-t border-borda first:border-t-0">
              <Link
                to={`/agente?execucao=${a.auditoria_id}`}
                className="grid grid-cols-[3.5rem_1fr] gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-superficie-2"
              >
                <span className="font-mono text-xs leading-5 text-apoio">{hora(a.ts)}</span>
                <span>
                  <span className="text-apoio">{MOTIVO_SIMPLES[a.disparado_por]}: </span>
                  {a.resumo.replace(/ → /g, ", ")}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </Pagina>
  );
}
