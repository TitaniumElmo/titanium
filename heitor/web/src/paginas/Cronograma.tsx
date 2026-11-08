import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAgora, useMundo } from "../api";
import { EstadoVazio, Segmentos } from "../componentes/base";
import { Pagina } from "../componentes/Pagina";
import { Selo } from "../componentes/Selos";
import { cronograma } from "../derivados";
import { dataCurta, diaDaSemana, isoDia } from "../formato";
import { NOME_AGENTE } from "../marca";
import type { ItemCronograma, StatusCronograma, TipoCronograma } from "../tipos";
import { cn, IconeCalendario } from "../util";

const DIA = 86_400_000;

const ROTULO_TIPO: Record<TipoCronograma, string> = {
  troca_epi: "Troca de EPI",
  ca_vencendo: "CA vencendo",
  treinamento: "Treinamento",
  dds: "DDS",
  prazo_pendencia: "Prazo de pendência",
};

const CORES_STATUS: Record<StatusCronograma, string> = {
  previsto: "border-borda bg-superficie-2 text-apoio",
  atrasado: "border-irregular-borda/40 bg-irregular-fundo text-irregular",
  feito: "border-ok-borda/40 bg-ok-fundo text-ok",
};

function inicioDaSemana(dia: string): string {
  const d = new Date(`${dia}T12:00:00`);
  const deslocamento = (d.getDay() + 6) % 7;
  return isoDia(d.getTime() - deslocamento * DIA);
}

function ItemLinha({ item, hoje }: { item: ItemCronograma; hoje: string }) {
  const corpo = (
    <div className="grid grid-cols-[4.5rem_1fr] gap-3 sm:grid-cols-[6rem_1fr_auto] sm:items-start">
      <span className={cn("pt-0.5 font-mono text-xs", item.data === hoje ? "text-texto" : "text-apoio")}>{diaDaSemana(item.data)}</span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <Selo>{ROTULO_TIPO[item.tipo]}</Selo>
          <span className={cn("rounded-selo border px-2 py-0.5 text-xs font-medium", CORES_STATUS[item.status])}>{item.status}</span>
        </div>
        <p className="mt-1.5 text-sm">{item.titulo}</p>
        <p className="mt-0.5 text-xs text-apoio">
          {item.nome ?? (item.funcao ? `Função: ${item.funcao}` : "")}
          {item.nome && item.funcao ? ` · ${item.funcao}` : ""}
        </p>
        {item.descricao && <p className="mt-0.5 text-xs text-fraco">{item.descricao}</p>}
        {item.afetados && (
          <div className="mt-2 flex flex-wrap gap-1">
            {item.afetados.map((n) => (
              <Selo key={n}>{n}</Selo>
            ))}
          </div>
        )}
      </div>
      <span className="col-span-2 text-xs text-fraco sm:col-span-1 sm:text-right">sugerido pelo {NOME_AGENTE}</span>
    </div>
  );
  const classe = "block rounded-cartao border border-borda bg-superficie p-4 transition-colors";
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

export function Cronograma() {
  const mundo = useMundo();
  const hoje = isoDia(useAgora(60_000));
  const [tipo, setTipo] = useState<"todos" | TipoCronograma>("todos");

  const itens = useMemo(() => {
    const de = isoDia(new Date(`${hoje}T12:00:00`).getTime() - 7 * DIA);
    const ate = isoDia(new Date(`${hoje}T12:00:00`).getTime() + 30 * DIA);
    return cronograma(mundo, hoje, de, ate);
  }, [mundo, hoje]);

  const filtrados = itens.filter((i) => tipo === "todos" || i.tipo === tipo);
  const semanas = new Map<string, ItemCronograma[]>();
  for (const item of filtrados) {
    const chave = inicioDaSemana(item.data);
    semanas.set(chave, [...(semanas.get(chave) ?? []), item]);
  }
  const semanaAtual = inicioDaSemana(hoje);

  if (!mundo.fonte) {
    return (
      <Pagina titulo="Cronograma">
        <EstadoVazio icone={IconeCalendario} titulo="Nada previsto" descricao="Conecte a planilha para o agente montar o cronograma." />
      </Pagina>
    );
  }

  return (
    <Pagina titulo="Cronograma" descricao={`O lado preventivo: tudo aqui foi gerado pelo ${NOME_AGENTE} a partir das fichas. Não há cadastro manual.`}>
      <Segmentos
        rotulo="Tipo"
        valor={tipo}
        aoMudar={setTipo}
        opcoes={[
          { valor: "todos", rotulo: "Tudo" },
          ...(Object.keys(ROTULO_TIPO) as TipoCronograma[])
            .filter((t) => itens.some((i) => i.tipo === t))
            .map((t) => ({ valor: t, rotulo: ROTULO_TIPO[t] })),
        ]}
      />
      {filtrados.length === 0 ? (
        <EstadoVazio icone={IconeCalendario} titulo="Nada previsto nesse filtro" />
      ) : (
        [...semanas.entries()].map(([semana, lista]) => {
          const fim = isoDia(new Date(`${semana}T12:00:00`).getTime() + 6 * DIA);
          return (
            <section key={semana} className="flex flex-col gap-2">
              <h2 className="flex items-center gap-2 text-label text-apoio">
                Semana de {dataCurta(semana)} a {dataCurta(fim)}
                {semana === semanaAtual && <span className="rounded-selo bg-superficie-2 px-1.5 py-0.5 text-texto">esta semana</span>}
              </h2>
              <ol className="flex flex-col gap-2">
                {lista.map((item) => (
                  <li key={item.id}>
                    <ItemLinha item={item} hoje={hoje} />
                  </li>
                ))}
              </ol>
            </section>
          );
        })
      )}
    </Pagina>
  );
}
