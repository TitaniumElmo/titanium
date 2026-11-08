import type { Periodo } from "./estado";
import type { Gatilho, ItemAtividade, Pendencia } from "./tipos";

const DIA = 86_400_000;

export const DIAS_DO_PERIODO: Record<Periodo, number> = { "7d": 7, "30d": 30, "90d": 90 };

export type TipoEvento = "abriu" | "fechou" | "cobrou" | "reabriu";

export const ROTULO_EVENTO: Record<TipoEvento, string> = {
  abriu: "abriu pendência",
  fechou: "fechou pendência",
  cobrou: "cobrou ou escalou",
  reabriu: "reabriu pendência",
};

export type Filtros = { funcionario: string; gatilho: Gatilho | ""; evento: TipoEvento | "" };

export const SEM_FILTROS: Filtros = { funcionario: "", gatilho: "", evento: "" };

export function tiposDoItem(item: ItemAtividade, pendencias: Pendencia[]): Set<TipoEvento> {
  const tipos = new Set<TipoEvento>();
  if (item.pendencias_fechadas.length > 0) tipos.add("fechou");
  if (item.pendencias_abertas.length > 0) tipos.add("abriu");
  if (item.disparado_por === "prazo_vencido") tipos.add("cobrou");
  for (const id of item.pendencias_abertas) {
    if (pendencias.find((p) => p.id === id)?.status === "reaberta") tipos.add("reabriu");
  }
  return tipos;
}

export function funcionariosDoItem(item: ItemAtividade, pendencias: Pendencia[]): Set<string> {
  const ids = new Set<string>();
  for (const id of [...item.pendencias_abertas, ...item.pendencias_fechadas]) {
    const p = pendencias.find((x) => x.id === id);
    if (p) ids.add(p.funcionario_id);
  }
  return ids;
}

export function noPeriodo(itens: ItemAtividade[], periodo: Periodo, agora: number): ItemAtividade[] {
  const inicio = agora - DIAS_DO_PERIODO[periodo] * DIA;
  return itens.filter((i) => new Date(i.ts).getTime() >= inicio);
}

export function filtrar(itens: ItemAtividade[], filtros: Filtros, pendencias: Pendencia[]): ItemAtividade[] {
  return itens.filter((i) => {
    if (filtros.gatilho && i.disparado_por !== filtros.gatilho) return false;
    if (filtros.funcionario && !funcionariosDoItem(i, pendencias).has(filtros.funcionario)) return false;
    if (filtros.evento && !tiposDoItem(i, pendencias).has(filtros.evento)) return false;
    return true;
  });
}

export type Resumo = { acoes: number; fechadas: number; abertas: number; reabertas: number; tempoMedioMs: number | null };

export function resumir(itens: ItemAtividade[], pendencias: Pendencia[], periodo: Periodo, agora: number): Resumo {
  const inicio = agora - DIAS_DO_PERIODO[periodo] * DIA;
  const fechadasNoPeriodo = pendencias.filter((p) => {
    if (p.status !== "fechada" || p.historico.length < 2) return false;
    const ultimo = p.historico[p.historico.length - 1];
    return ultimo ? new Date(ultimo.ts).getTime() >= inicio : false;
  });
  const duracoes = fechadasNoPeriodo.map((p) => {
    const primeiro = p.historico[0];
    const ultimo = p.historico[p.historico.length - 1];
    return primeiro && ultimo ? new Date(ultimo.ts).getTime() - new Date(primeiro.ts).getTime() : 0;
  });
  return {
    acoes: itens.length,
    fechadas: new Set(itens.flatMap((i) => i.pendencias_fechadas)).size,
    abertas: pendencias.filter((p) => p.status !== "fechada").length,
    reabertas: pendencias.filter((p) => p.status === "reaberta").length,
    tempoMedioMs: duracoes.length ? duracoes.reduce((a, b) => a + b, 0) / duracoes.length : null,
  };
}

export function rotuloDuracao(ms: number | null): string {
  if (ms === null) return "—";
  const horas = ms / 3_600_000;
  if (horas < 1) return `${Math.max(1, Math.round(ms / 60_000))} min`;
  if (horas < 48) return `${Math.round(horas)} h`;
  return `${(horas / 24).toFixed(1).replace(".", ",")} dias`;
}

export type Coluna = { rotulo: string; abertas: number; fechadas: number };

export function colunasDoGrafico(itens: ItemAtividade[], periodo: Periodo, agora: number): Coluna[] {
  const dias = DIAS_DO_PERIODO[periodo];
  const tamanho = dias === 7 ? 1 : 7;
  const quantidade = Math.ceil(dias / tamanho);
  const inicio = agora - dias * DIA;
  const colunas: Coluna[] = Array.from({ length: quantidade }, (_, i) => ({
    rotulo: new Date(inicio + i * tamanho * DIA).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }),
    abertas: 0,
    fechadas: 0,
  }));
  for (const item of itens) {
    const indice = Math.floor((new Date(item.ts).getTime() - inicio) / (tamanho * DIA));
    const coluna = colunas[Math.min(Math.max(indice, 0), quantidade - 1)];
    if (!coluna) continue;
    coluna.abertas += item.pendencias_abertas.length;
    coluna.fechadas += item.pendencias_fechadas.length;
  }
  return colunas;
}

export function exportarCsv(itens: ItemAtividade[], rotuloGatilho: (g: Gatilho) => string): string {
  const aspas = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const linhas = itens.map((i) =>
    [i.ts, rotuloGatilho(i.disparado_por), i.resumo, i.pendencias_abertas.join(" "), i.pendencias_fechadas.join(" ")].map(aspas).join(","),
  );
  return ["data_hora,gatilho,resumo,pendencias_abertas,pendencias_fechadas", ...linhas].join("\n");
}
