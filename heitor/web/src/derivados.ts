import { VIDA_UTIL_DIAS } from "./fichas";
import { isoDia } from "./formato";
import type { Mundo } from "./mock";
import type { Achado, Funcionario, Gravidade, ItemCronograma, Linha, Pendencia, Relatorio, TipoAchado } from "./tipos";

const DIA = 86_400_000;

function paraMs(dia: string): number {
  return new Date(`${dia}T12:00:00`).getTime();
}

export type StatusPapel = "conferido" | "duvida" | "sem_assinatura" | "nao_localizada" | "nao_conferida";

export function statusPapel(l: Linha): StatusPapel {
  if (l.na_ficha === undefined) return "nao_conferida";
  if (l.na_ficha === false) return "nao_localizada";
  if (l.na_ficha === null) return "duvida";
  if (l.assinatura === false) return "sem_assinatura";
  if ((l.confianca.assinatura ?? 1) < 0.7) return "duvida";
  return "conferido";
}

export function ehUrgente(p: Pendencia, hoje: string): boolean {
  if (p.status === "fechada" || p.prazo < hoje) return false;
  const dias = Math.round((paraMs(p.prazo) - paraMs(hoje)) / DIA);
  return dias <= 2;
}

export function achadoAberto(a: Achado, pendencias: Pendencia[]): boolean {
  const p = pendencias.find((x) => x.achado_id === a.id);
  return !p || p.status !== "fechada";
}

function piorGravidade(achados: Achado[]): Gravidade {
  if (achados.some((a) => a.gravidade === "irregular")) return "irregular";
  if (achados.some((a) => a.gravidade === "risco")) return "risco";
  return "ok";
}

export type TrocaPrevista = { epi: string; ultima: string; vence: string };

export function trocasPrevistas(linhas: Linha[]): TrocaPrevista[] {
  const ultimas = new Map<string, string>();
  for (const l of linhas) {
    const atual = ultimas.get(l.epi);
    if (!atual || l.data > atual) ultimas.set(l.epi, l.data);
  }
  return [...ultimas.entries()]
    .filter(([epi]) => VIDA_UTIL_DIAS[epi] !== undefined)
    .map(([epi, ultima]) => ({ epi, ultima, vence: isoDia(paraMs(ultima) + (VIDA_UTIL_DIAS[epi] ?? 0) * DIA) }))
    .sort((a, b) => a.vence.localeCompare(b.vence));
}

function trocasRelevantes(linhas: Linha[], hoje: string): TrocaPrevista[] {
  const limite = isoDia(paraMs(hoje) - 365 * DIA);
  return trocasPrevistas(linhas).filter((t) => t.ultima >= limite);
}

export function resumoFuncionarios(m: Mundo, hoje: string): Funcionario[] {
  return m.funcionarios.map((f) => {
    const linhas = m.linhas.filter((l) => l.funcionario_id === f.funcionario_id);
    const achados = m.achados.filter((a) => a.funcionario_id === f.funcionario_id && achadoAberto(a, m.pendencias));
    const pendencias = m.pendencias.filter((p) => p.funcionario_id === f.funcionario_id && p.status !== "fechada");
    const ultima = linhas.reduce((acc, l) => (l.data > acc ? l.data : acc), "");
    const proxima = trocasRelevantes(linhas, hoje)[0];
    return {
      ...f,
      status: piorGravidade(achados),
      achados_abertos: achados.length,
      pendencias_abertas: pendencias.length,
      ultima_entrega: ultima,
      proxima_troca: proxima?.vence ?? "",
    };
  });
}

export function cronograma(m: Mundo, hoje: string, de: string, ate: string): ItemCronograma[] {
  const itens: ItemCronograma[] = [];
  const dentro = (d: string) => d >= de && d <= ate;
  const antecedencia = m.config.antecedencia_troca_dias;

  for (const f of m.funcionarios) {
    const linhas = m.linhas.filter((l) => l.funcionario_id === f.funcionario_id);
    for (const t of trocasRelevantes(linhas, hoje)) {
      if (!dentro(t.vence)) continue;
      const diasAte = Math.round((paraMs(t.vence) - paraMs(hoje)) / DIA);
      if (diasAte > antecedencia + 15) continue;
      itens.push({
        id: `c-troca-${f.funcionario_id}-${t.epi}`,
        tipo: "troca_epi",
        funcionario_id: f.funcionario_id,
        nome: f.nome,
        funcao: f.funcao,
        titulo: `Trocar ${t.epi}`,
        descricao: `Última entrega em ${t.ultima.split("-").reverse().join("/")}, conforme a durabilidade indicada pelo fabricante`,
        data: t.vence,
        status: t.vence < hoje ? "atrasado" : "previsto",
        origem: "agente",
        pendencia_id: null,
      });
    }
  }

  for (const p of m.pendencias) {
    if (!dentro(p.prazo)) continue;
    const funcionario = m.funcionarios.find((f) => f.funcionario_id === p.funcionario_id);
    itens.push({
      id: `c-${p.id}`,
      tipo: "prazo_pendencia",
      funcionario_id: p.funcionario_id,
      nome: p.funcionario_nome,
      funcao: funcionario?.funcao ?? null,
      titulo: `Prazo da pendência ${p.id}: ${p.acao}`,
      data: p.prazo,
      status: p.status === "fechada" ? "feito" : p.prazo < hoje ? "atrasado" : "previsto",
      origem: "agente",
      pendencia_id: p.id,
    });
  }

  return itens.sort((a, b) => a.data.localeCompare(b.data) || a.tipo.localeCompare(b.tipo));
}

function semente(n: number): number {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

export function relatorio(m: Mundo, hoje: string, dias: number): Relatorio {
  const serie: Relatorio["serie"] = [];
  const base = paraMs(hoje);
  for (let i = dias - 1; i >= 0; i--) {
    const data = isoDia(base - i * DIA);
    const indice = Math.floor(paraMs(data) / DIA);
    const doDia = m.achados.filter((a) => isoDia(new Date(a.ts)) === data);
    // Ruído só na simulação; com a API, a série mostra só o que existe.
    const tendencia = m.ao_vivo ? 0 : Math.max(0, 1 - (dias - i) / (dias * 1.6));
    serie.push({
      data,
      irregular: doDia.filter((a) => a.gravidade === "irregular").length + Math.round(semente(indice) * 3 * tendencia),
      risco: doDia.filter((a) => a.gravidade === "risco").length + Math.round(semente(indice + 7) * 2 * tendencia),
      ok: m.ao_vivo ? doDia.filter((a) => a.gravidade === "ok").length : 10 + Math.round(semente(indice + 13) * 8),
    });
  }

  const por_tipo: Record<TipoAchado, number> = { corrigivel: 0, prova: 0, passivo: 0 };
  for (const a of m.achados) por_tipo[a.tipo] += 1;

  const fechadas = m.pendencias.filter((p) => p.status === "fechada");
  const duracoes = fechadas
    .map((p) => {
      const inicio = p.historico[0];
      const fim = [...p.historico].reverse().find((h) => h.etapa === "conferir");
      return inicio && fim ? (new Date(fim.ts).getTime() - new Date(inicio.ts).getTime()) / DIA : null;
    })
    .filter((d): d is number => d !== null);

  const porFuncao = new Map<string, number>();
  for (const a of m.achados) if (a.exposicao) porFuncao.set(a.funcao, (porFuncao.get(a.funcao) ?? 0) + a.exposicao);

  const concluidas = m.auditorias.filter((a) => a.status === "concluida");
  const eventos = concluidas.flatMap((a) => m.eventos[a.id] ?? []);
  const fichas = concluidas.reduce((s, a) => s + Math.max(a.n_fichas, 0), 0);
  const custo = eventos.reduce((s, e) => s + e.custo_usd, 0);

  return {
    serie,
    por_tipo,
    pendencias: {
      abertas: m.pendencias.filter((p) => p.status === "aberta" || p.status === "aguardando").length,
      fechadas: fechadas.length,
      reabertas: m.pendencias.filter((p) => p.status === "reaberta").length,
      tempo_medio_dias: duracoes.length ? duracoes.reduce((s, d) => s + d, 0) / duracoes.length : 0,
    },
    exposicao_total: [...porFuncao.values()].reduce((s, v) => s + v, 0),
    exposicao_por_funcao: [...porFuncao.entries()].map(([funcao, valor]) => ({ funcao, valor })).sort((a, b) => b.valor - a.valor),
    custo_medio_ficha_usd: fichas ? custo / fichas : 0,
    passos_medios: concluidas.length ? eventos.length / concluidas.length : 0,
    acerto: m.ao_vivo ? null : { precisao: 0.94, recall: 0.9 }, // com a API: sem gabarito, não há acerto a mostrar
  };
}
