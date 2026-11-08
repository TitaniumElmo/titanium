import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAgora, useMundo } from "../api";
import { Botao, Cartao, EstadoVazio } from "../componentes/base";
import { CartaoExposicao } from "../componentes/CartaoExposicao";
import { Pagina } from "../componentes/Pagina";
import { relatorio as gerarRelatorio } from "../derivados";
import { useEstado } from "../estado";
import { data, dataCurta, dolares, isoDia, porcentagem, ROTULO_TIPO } from "../formato";
import type { Relatorio as TipoRelatorio, TipoAchado } from "../tipos";
import { cn, IconeDocumento } from "../util";

const DIAS_DO_PERIODO = { "7d": 7, "30d": 30, "90d": 90 } as const;

const SERIES = [
  { chave: "irregular", rotulo: "Irregular", cor: "var(--grafico-irregular)", tracejado: undefined },
  { chave: "risco", rotulo: "Risco", cor: "var(--grafico-risco)", tracejado: "6 4" },
  { chave: "ok", rotulo: "Ok", cor: "var(--grafico-ok)", tracejado: "1 4" },
] as const;

const CORES_TIPO: Record<TipoAchado, string> = {
  corrigivel: "bg-grafico-cat-1",
  prova: "bg-grafico-cat-2",
  passivo: "bg-grafico-cat-3",
};

function AmostraLinha({ cor, tracejado }: { cor: string; tracejado?: string }) {
  return (
    <svg width="22" height="8" aria-hidden>
      <line x1="1" y1="4" x2="21" y2="4" stroke={cor} strokeWidth="2" strokeDasharray={tracejado} strokeLinecap="round" />
    </svg>
  );
}

type PropsDica = {
  active?: boolean;
  payload?: readonly { dataKey?: unknown; value?: unknown }[];
  label?: unknown;
};

function DicaGrafico({ active, payload, label }: PropsDica) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-controle border border-borda bg-superficie px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-mono text-fraco">{data(String(label))}</div>
      {SERIES.map((s) => {
        const item = payload.find((p) => p.dataKey === s.chave);
        return (
          <div key={s.chave} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-apoio">
              <AmostraLinha cor={s.cor} tracejado={s.tracejado} />
              {s.rotulo}
            </span>
            <span className="font-mono text-texto">{String(item?.value ?? 0)}</span>
          </div>
        );
      })}
    </div>
  );
}

function GraficoSerie({ serie }: { serie: TipoRelatorio["serie"] }) {
  const [tabela, setTabela] = useState(false);
  const ultimo = serie[serie.length - 1];
  return (
    <Cartao className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-h3">Achados por dia</h2>
          <p className="text-sm text-apoio">Linhas auditadas por gravidade, conforme as regras de auditoria</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {SERIES.map((s) => (
            <span key={s.chave} className="flex items-center gap-1.5 text-xs text-apoio">
              <AmostraLinha cor={s.cor} tracejado={s.tracejado} />
              {s.rotulo}
              {ultimo && <span className="font-mono text-texto">{ultimo[s.chave]}</span>}
            </span>
          ))}
          <Botao variante="fantasma" className="h-7 px-2 text-xs" onClick={() => setTabela(!tabela)}>
            {tabela ? "Ver gráfico" : "Ver tabela"}
          </Botao>
        </div>
      </div>
      {tabela ? (
        <div className="max-h-72 overflow-auto rounded-controle border border-borda">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-superficie-2 text-left text-xs font-medium text-fraco">
              <tr>
                <th className="px-3 py-2 font-medium">Dia</th>
                {SERIES.map((s) => (
                  <th key={s.chave} className="px-3 py-2 text-right font-medium">
                    {s.rotulo}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...serie].reverse().map((d) => (
                <tr key={d.data} className="border-t border-borda font-mono text-xs">
                  <td className="px-3 py-1.5">{data(d.data)}</td>
                  <td className="px-3 py-1.5 text-right">{d.irregular}</td>
                  <td className="px-3 py-1.5 text-right">{d.risco}</td>
                  <td className="px-3 py-1.5 text-right">{d.ok}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={serie} margin={{ top: 8, right: 24, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="var(--borda)" strokeDasharray="2 4" vertical={false} />
              <XAxis
                dataKey="data"
                tickFormatter={(v: string) => dataCurta(v)}
                stroke="var(--texto-fraco)"
                tick={{ style: { fontSize: "var(--tamanho-12)", fontFamily: "var(--fonte-mono)" } }}
                tickLine={false}
                axisLine={{ stroke: "var(--borda)" }}
                minTickGap={24}
              />
              <YAxis
                allowDecimals={false}
                stroke="var(--texto-fraco)"
                tick={{ style: { fontSize: "var(--tamanho-12)", fontFamily: "var(--fonte-mono)" } }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={(p) => <DicaGrafico active={p.active} payload={p.payload} label={p.label} />} cursor={{ stroke: "var(--texto-fraco)", strokeDasharray: "3 3" }} />
              {SERIES.map((s) => (
                <Line
                  key={s.chave}
                  type="monotone"
                  dataKey={s.chave}
                  name={s.rotulo}
                  stroke={s.cor}
                  strokeWidth={2}
                  strokeDasharray={s.tracejado}
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--superficie)" }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Cartao>
  );
}

function CartaoTipos({ porTipo }: { porTipo: TipoRelatorio["por_tipo"] }) {
  const total = Object.values(porTipo).reduce((s, v) => s + v, 0);
  const tipos = Object.keys(porTipo) as TipoAchado[];
  return (
    <Cartao className="flex flex-col gap-4">
      <div>
        <h2 className="text-label">Achados por tipo</h2>
        <p className="text-h1 tabular-nums">{total}</p>
      </div>
      <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full" role="img" aria-label="Distribuição dos achados por tipo">
        {tipos.map((t) =>
          porTipo[t] ? (
            <span
              key={t}
              title={`${ROTULO_TIPO[t]}: ${porTipo[t]}`}
              className={cn("h-full first:rounded-l-full last:rounded-r-full", CORES_TIPO[t])}
              style={{ width: `${(porTipo[t] / Math.max(1, total)) * 100}%` }}
            />
          ) : null,
        )}
      </div>
      <ul className="flex flex-col gap-2 text-sm">
        {tipos.map((t) => (
          <li key={t} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-apoio">
              <span className={cn("size-2.5 rounded-sm", CORES_TIPO[t])} />
              {ROTULO_TIPO[t]}
            </span>
            <span className="font-mono text-xs">
              {porTipo[t]} <span className="text-fraco">· {porcentagem(porTipo[t] / Math.max(1, total))}</span>
            </span>
          </li>
        ))}
      </ul>
    </Cartao>
  );
}

function CartaoPendencias({ p }: { p: TipoRelatorio["pendencias"] }) {
  const itens = [
    { rotulo: "Abertas", valor: String(p.abertas) },
    { rotulo: "Fechadas", valor: String(p.fechadas) },
    { rotulo: "Reabertas", valor: String(p.reabertas) },
    { rotulo: "Tempo médio até fechar", valor: `${p.tempo_medio_dias.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} dias` },
  ];
  return (
    <Cartao className="flex flex-col gap-4">
      <h2 className="text-label">Pendências</h2>
      <dl className="grid grid-cols-2 gap-3">
        {itens.map((i) => (
          <div key={i.rotulo} className="rounded-controle bg-superficie-2 px-3 py-2.5">
            <dt className="text-xs text-fraco">{i.rotulo}</dt>
            <dd className="text-h2 tabular-nums">{i.valor}</dd>
          </div>
        ))}
      </dl>
    </Cartao>
  );
}

export function Relatorio() {
  const mundo = useMundo();
  const { periodo } = useEstado();
  const hoje = isoDia(useAgora(60_000));
  const rel = useMemo(() => gerarRelatorio(mundo, hoje, DIAS_DO_PERIODO[periodo]), [mundo, hoje, periodo]);

  if (!mundo.fonte) {
    return (
      <Pagina titulo="Relatório" comPeriodo>
        <EstadoVazio
          icone={IconeDocumento}
          titulo="Relatório vazio"
          descricao="O relatório aponta lacunas na prova documental, com a norma e a súmula de cada falha."
        />
      </Pagina>
    );
  }

  const metricas = [
    { rotulo: "Custo médio de LLM por ficha", valor: dolares(rel.custo_medio_ficha_usd) },
    { rotulo: "Passos médios por execução", valor: rel.passos_medios.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) },
    { rotulo: "Precisão contra o gabarito", valor: rel.acerto ? porcentagem(rel.acerto.precisao) : "—" },
    { rotulo: "Recall contra o gabarito", valor: rel.acerto ? porcentagem(rel.acerto.recall) : "—" },
  ];

  return (
    <Pagina titulo="Relatório" descricao="Aponta lacunas na prova documental. Não diz se há insalubridade: isso é papel do perito." comPeriodo>
      <GraficoSerie serie={rel.serie} />
      <div className="grid gap-4 lg:grid-cols-3">
        <CartaoTipos porTipo={rel.por_tipo} />
        <CartaoPendencias p={rel.pendencias} />
        <CartaoExposicao total={rel.exposicao_total} porFuncao={rel.exposicao_por_funcao} />
      </div>
      <section className="flex flex-col gap-2">
        <h2 className="text-label text-apoio">Métricas do agente</h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {metricas.map((m) => (
            <div key={m.rotulo} className="rounded-cartao border border-borda bg-superficie px-4 py-3">
              <div className="text-xs text-fraco">{m.rotulo}</div>
              <div className="font-mono text-lg">{m.valor}</div>
            </div>
          ))}
        </div>
        <p className="text-xs text-fraco">
          Critério do CA: válido na data da entrega. Precisão e recall medidos contra o gabarito do dataset fixo.
        </p>
      </section>
    </Pagina>
  );
}
