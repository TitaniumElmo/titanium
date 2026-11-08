import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAgora, useMundo } from "../api";
import { EstadoVazio } from "../componentes/base";
import { Pagina } from "../componentes/Pagina";
import { CartaoAba } from "../componentes/ResumoHistorico";
import { Selo } from "../componentes/Selos";
import { cronograma } from "../derivados";
import { dataCurta, isoDia } from "../formato";
import type { ItemCronograma, StatusCronograma, TipoCronograma } from "../tipos";
import { cn, IconeAlerta, IconeAtividade, IconeCalendario, IconeLista } from "../util";

const DIA = 86_400_000;

const LIMITE_ANTES = -1;
const LIMITE_DEPOIS = 4;

type Horizonte = "atrasados" | "semana" | "proxima" | "depois" | "concluidos";

const ROTULO_TIPO: Record<TipoCronograma, string> = {
  troca_epi: "Troca de EPI",
  ca_vencendo: "CA vencendo",
  treinamento: "Treinamento",
  dds: "DDS",
  prazo_pendencia: "Prazo de pendência",
};

const TITULO_GRUPO: Record<Horizonte, string> = {
  atrasados: "Atrasados",
  semana: "Esta semana",
  proxima: "Próxima semana",
  depois: "Mais adiante",
  concluidos: "Concluídos",
};

const ORDEM: Horizonte[] = ["atrasados", "semana", "proxima", "depois", "concluidos"];

const STATUS: Record<StatusCronograma, { rotulo: string; classe: string }> = {
  previsto: { rotulo: "Previsto", classe: "border-borda bg-superficie-2 text-apoio" },
  atrasado: { rotulo: "Atrasado", classe: "border-irregular-borda/40 bg-irregular-fundo text-irregular" },
  feito: { rotulo: "Concluído", classe: "border-ok-borda/40 bg-ok-fundo text-ok" },
};

const ICONE_STATUS: Record<StatusCronograma, string> = {
  previsto: "M8 2v4M16 2v4M3 10h18M5 5h14a2 2 0 012 2v12a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2z",
  atrasado: "M12 8v5M12 17h.01M10.3 3.9L2.4 18a2 2 0 001.7 3h15.8a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  feito: "M5 13l4 4L19 7",
};

function inicioDaSemana(dia: string): string {
  const d = new Date(`${dia}T12:00:00`);
  const deslocamento = (d.getDay() + 6) % 7;
  return isoDia(d.getTime() - deslocamento * DIA);
}

function limparTitulo(t: string): string {
  const sem = t.replace(/^Prazo da pendência [^:]+:\s*/i, "");
  return sem.charAt(0).toUpperCase() + sem.slice(1);
}

function classificar(item: ItemCronograma, semanaAtual: string): Horizonte {
  if (item.status === "feito") return "concluidos";
  if (item.status === "atrasado") return "atrasados";
  const semana = inicioDaSemana(item.data);
  const proxima = isoDia(new Date(`${semanaAtual}T12:00:00`).getTime() + 7 * DIA);
  if (semana <= semanaAtual) return "semana";
  if (semana === proxima) return "proxima";
  return "depois";
}

function BlocoData({ data, hoje }: { data: string; hoje: string }) {
  const d = new Date(`${data}T12:00:00`);
  return (
    <span
      className={cn(
        "flex w-14 shrink-0 flex-col items-center rounded-controle border px-1 py-1.5 text-center sm:w-16",
        data === hoje ? "border-acento bg-acento-suave" : "border-borda bg-superficie-2",
      )}
    >
      <span className="text-xs uppercase text-apoio">{d.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "")}</span>
      <span className="text-xl font-semibold tabular-nums leading-tight sm:text-2xl">{d.getDate()}</span>
      <span className="text-xs uppercase text-apoio">{d.toLocaleDateString("pt-BR", { month: "short" }).replace(".", "")}</span>
    </span>
  );
}

function ItemLinha({ item, hoje }: { item: ItemCronograma; hoje: string }) {
  const st = STATUS[item.status];
  const corpo = (
    <div className="flex gap-3 sm:gap-4">
      <BlocoData data={item.data} hoje={hoje} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <Selo>{ROTULO_TIPO[item.tipo]}</Selo>
          <span className={cn("inline-flex items-center gap-1.5 rounded-selo border px-2 py-0.5 text-xs font-medium sm:text-sm", st.classe)}>
            <svg aria-hidden viewBox="0 0 24 24" className="size-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d={ICONE_STATUS[item.status]} />
            </svg>
            {st.rotulo}
          </span>
        </div>
        <p className="mt-1.5 text-sm font-medium sm:text-base">{limparTitulo(item.titulo)}</p>
        <p className="mt-0.5 text-sm text-apoio">
          {item.nome ?? (item.funcao ? `Função: ${item.funcao}` : "")}
          {item.nome && item.funcao ? ` · ${item.funcao}` : ""}
        </p>
        {item.descricao && <p className="mt-0.5 text-sm text-fraco">{item.descricao}</p>}
        {item.afetados && (
          <div className="mt-2 flex flex-wrap gap-1">
            {item.afetados.map((n) => (
              <Selo key={n}>{n}</Selo>
            ))}
          </div>
        )}
      </div>
    </div>
  );
  const classe = cn(
    "block rounded-cartao border border-borda bg-superficie bg-[radial-gradient(120%_90%_at_100%_0%,var(--cartao-brilho),transparent_60%)] p-4 transition-colors sm:p-5",
    item.status === "atrasado" && "border-l-4 border-l-irregular-borda",
    item.status === "feito" && "opacity-70",
  );
  if (item.pendencia_id)
    return (
      <Link to={`/pendencias?p=${item.pendencia_id}`} className={cn(classe, "hover:border-fraco")}>
        {corpo}
      </Link>
    );
  if (item.funcionario_id)
    return (
      <Link to={`/funcionarios/${item.funcionario_id}`} className={cn(classe, "hover:border-fraco")}>
        {corpo}
      </Link>
    );
  return <div className={classe}>{corpo}</div>;
}

function FaixaDaSemana({
  itens,
  semanaAtual,
  hoje,
  escolhido,
  aoEscolher,
  deslocamento,
  aoMudarSemana,
}: {
  itens: ItemCronograma[];
  semanaAtual: string;
  hoje: string;
  escolhido: string | null;
  aoEscolher: (dia: string) => void;
  deslocamento: number;
  aoMudarSemana: (novo: number) => void;
}) {
  const dias = Array.from({ length: 7 }, (_, i) => isoDia(new Date(`${semanaAtual}T12:00:00`).getTime() + i * DIA));
  const botao =
    "inline-flex size-9 items-center justify-center rounded-controle border border-borda text-apoio transition-colors hover:border-fraco hover:text-texto disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-borda disabled:hover:text-apoio focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-acento";
  const seta = (d: string) => (
    <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">
          {deslocamento === 0 ? "Esta semana" : `Semana de ${dataCurta(semanaAtual)} a ${dataCurta(dias[6] ?? semanaAtual)}`}
          {deslocamento === 0 && <span className="ml-2 text-sm font-normal text-apoio">{dataCurta(semanaAtual)} a {dataCurta(dias[6] ?? semanaAtual)}</span>}
        </h2>
        <span className="flex items-center gap-2">
          {deslocamento !== 0 && (
            <button type="button" onClick={() => aoMudarSemana(0)} className="h-9 px-2 text-sm text-acento hover:underline">
              voltar para hoje
            </button>
          )}
          <button type="button" className={botao} aria-label="Semana anterior" disabled={deslocamento <= LIMITE_ANTES} onClick={() => aoMudarSemana(deslocamento - 1)}>
            {seta("M15 6l-6 6 6 6")}
          </button>
          <button type="button" className={botao} aria-label="Próxima semana" disabled={deslocamento >= LIMITE_DEPOIS} onClick={() => aoMudarSemana(deslocamento + 1)}>
            {seta("M9 6l6 6-6 6")}
          </button>
        </span>
      </div>
    <section role="group" aria-label="Dias da semana" className="grid grid-cols-7 gap-1.5 rounded-cartao border border-borda bg-superficie p-2 sm:gap-2 sm:p-3">
      {dias.map((dia) => {
        const d = new Date(`${dia}T12:00:00`);
        const total = itens.filter((i) => i.data === dia && i.status !== "feito").length;
        const atrasado = itens.some((i) => i.data === dia && i.status === "atrasado");
        const ehHoje = dia === hoje;
        return (
          <button
            key={dia}
            type="button"
            aria-pressed={escolhido === dia}
            onClick={() => aoEscolher(dia)}
            className={cn(
              "flex cursor-pointer flex-col items-center gap-1 rounded-controle border px-1 py-2 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-acento",
              escolhido === dia ? "border-acento bg-acento-suave" : ehHoje ? "border-borda bg-superficie-2" : "border-transparent hover:border-fraco",
            )}
            aria-label={`${d.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}: ${total} ${total === 1 ? "item" : "itens"}`}
          >
            <span className="text-xs uppercase text-apoio sm:text-sm">{d.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "")}</span>
            <span className="text-base font-semibold tabular-nums sm:text-xl">{d.getDate()}</span>
            <span
              className={cn(
                "inline-flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-xs font-semibold tabular-nums sm:text-sm",
                total === 0 ? "text-fraco" : atrasado ? "bg-irregular-fundo text-irregular" : "bg-superficie-2 text-texto",
              )}
            >
              {total}
            </span>
          </button>
        );
      })}
    </section>
    </div>
  );
}

export function Cronograma() {
  const mundo = useMundo();
  const hoje = isoDia(useAgora(60_000));
  const [tipo, setTipo] = useState<"todos" | TipoCronograma>("todos");
  const [horizonte, setHorizonte] = useState<"todos" | Horizonte>("todos");
  const [dia, setDia] = useState<string | null>(null);
  const [deslocamento, setDeslocamento] = useState(0);
  const semanaAtual = inicioDaSemana(hoje);
  const semanaExibida = isoDia(new Date(`${semanaAtual}T12:00:00`).getTime() + deslocamento * 7 * DIA);

  const itens = useMemo(() => {
    const de = isoDia(new Date(`${hoje}T12:00:00`).getTime() - 7 * DIA);
    const ate = isoDia(new Date(`${hoje}T12:00:00`).getTime() + 30 * DIA);
    return cronograma(mundo, hoje, de, ate);
  }, [mundo, hoje]);

  const porTipo = itens.filter((i) => tipo === "todos" || i.tipo === tipo);
  const contagem = new Map<Horizonte, number>();
  const grupos = new Map<Horizonte, ItemCronograma[]>();
  for (const item of porTipo) {
    const h = classificar(item, semanaAtual);
    contagem.set(h, (contagem.get(h) ?? 0) + 1);
    if (dia === null || item.data === dia) grupos.set(h, [...(grupos.get(h) ?? []), item]);
  }
  const total = (h: Horizonte) => contagem.get(h) ?? 0;
  const noGrupo = (h: Horizonte) => grupos.get(h)?.length ?? 0;
  const tiposPresentes = (Object.keys(ROTULO_TIPO) as TipoCronograma[]).filter((t) => itens.some((i) => i.tipo === t));
  const mostrados = ORDEM.filter((h) => (horizonte === "todos" || dia !== null ? true : h === horizonte) && noGrupo(h) > 0);

  if (!mundo.fonte) {
    return (
      <Pagina titulo="Cronograma">
        <EstadoVazio icone={IconeCalendario} titulo="Nada previsto" descricao="Conecte a planilha para o agente montar o cronograma." />
      </Pagina>
    );
  }

  const escolher = (h: Horizonte) => {
    setDia(null);
    setHorizonte(horizonte === h ? "todos" : h);
  };
  const escolherDia = (d: string) => {
    setHorizonte("todos");
    setDia(dia === d ? null : d);
  };
  const diaEscolhido = dia ? new Date(`${dia}T12:00:00`).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" }) : null;

  return (
    <Pagina titulo="Cronograma">
      <section role="radiogroup" aria-label="Quando" className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
        <CartaoAba
          rotulo="Atrasados"
          valor={total("atrasados")}
          detalhe="já passaram do prazo"
          urgente={total("atrasados") > 0}
          selecionado={horizonte === "atrasados"}
          aoClicar={() => escolher("atrasados")}
          icone={<IconeAlerta className="size-full" />}
        />
        <CartaoAba rotulo="Esta semana" valor={total("semana")} detalhe="para fazer até domingo" selecionado={horizonte === "semana"} aoClicar={() => escolher("semana")} icone={<IconeCalendario className="size-full" />} />
        <CartaoAba rotulo="Próxima semana" valor={total("proxima")} detalhe="já no radar" selecionado={horizonte === "proxima"} aoClicar={() => escolher("proxima")} icone={<IconeLista className="size-full" />} />
        <CartaoAba rotulo="Mais adiante" valor={total("depois")} detalhe="nos próximos 30 dias" selecionado={horizonte === "depois"} aoClicar={() => escolher("depois")} icone={<IconeAtividade className="size-full" />} />
      </section>

      <FaixaDaSemana
        itens={porTipo}
        semanaAtual={semanaExibida}
        hoje={hoje}
        escolhido={dia}
        aoEscolher={escolherDia}
        deslocamento={deslocamento}
        aoMudarSemana={setDeslocamento}
      />

      {diaEscolhido && (
        <p className="flex flex-wrap items-center gap-2 text-sm text-apoio sm:text-base">
          Mostrando só <span className="font-medium text-texto">{diaEscolhido}</span>
          <button type="button" onClick={() => setDia(null)} className="text-acento hover:underline">
            limpar
          </button>
        </p>
      )}

      {tiposPresentes.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative inline-flex">
            <span className="sr-only">Tipo</span>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value as "todos" | TipoCronograma)}
              className="h-9 appearance-none rounded-controle border border-borda bg-superficie pl-3 pr-8 text-sm text-texto hover:border-fraco"
            >
              <option value="todos">Todos os tipos</option>
              {tiposPresentes.map((t) => (
                <option key={t} value={t}>
                  {ROTULO_TIPO[t]}
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fraco">▼</span>
          </label>
        </div>
      )}

      {mostrados.length === 0 ? (
        <EstadoVazio icone={IconeCalendario} titulo={dia ? "Nada previsto nesse dia" : "Nada previsto nesse filtro"} />
      ) : (
        mostrados.map((h) => (
          <section key={h} className="flex flex-col gap-2">
            <h2 className="flex items-baseline gap-2 text-base font-semibold">
              {TITULO_GRUPO[h]}
              <span className="text-sm font-normal tabular-nums text-apoio">{noGrupo(h)}</span>
            </h2>
            <ol className="flex flex-col gap-2">
              {(grupos.get(h) ?? []).map((item) => (
                <li key={item.id}>
                  <ItemLinha item={item} hoje={hoje} />
                </li>
              ))}
            </ol>
          </section>
        ))
      )}
    </Pagina>
  );
}
