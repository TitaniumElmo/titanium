import { CA_FICTICIO_VENCENDO, VIDA_UTIL_DIAS } from "./fichas";
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

  const usamConcha = m.funcionarios.filter((f) =>
    m.linhas.some((l) => l.funcionario_id === f.funcionario_id && l.ca === CA_FICTICIO_VENCENDO),
  );
  const vencimentoCa = isoDia(paraMs(hoje) + 15 * DIA);
  if (usamConcha.length && dentro(vencimentoCa)) {
    itens.push({
      id: "c-ca",
      tipo: "ca_vencendo",
      funcionario_id: null,
      nome: null,
      funcao: "armador",
      titulo: `O CA ${CA_FICTICIO_VENCENDO} vence em 15 dias e ${usamConcha.length} funcionários usam esse protetor`,
      descricao: "Comprar o próximo lote com CA válido na data da compra",
      afetados: usamConcha.map((f) => f.nome),
      data: vencimentoCa,
      status: "previsto",
      origem: "agente",
      pendencia_id: null,
    });
  }

  const treinamentoEdvaldo = m.pendencias.find((p) => p.funcionario_id === "0410" && p.status === "fechada");
  const fixos: Omit<ItemCronograma, "origem">[] = [
    {
      id: "c-trein-0302",
      tipo: "treinamento",
      funcionario_id: "0302",
      nome: "Rafael Souza Costa",
      funcao: "servente",
      titulo: "Treinamento no uso do protetor auditivo (sem registro)",
      data: isoDia(paraMs(hoje) + 6 * DIA),
      status: "previsto",
      pendencia_id: null,
    },
    {
      id: "c-trein-carp",
      tipo: "treinamento",
      funcionario_id: null,
      nome: null,
      funcao: "carpinteiro",
      titulo: "Reciclagem do treinamento de EPI, carpinteiros",
      data: isoDia(paraMs(hoje) + 20 * DIA),
      status: "previsto",
      pendencia_id: null,
    },
    {
      id: "c-dds-serv",
      tipo: "dds",
      funcionario_id: null,
      nome: null,
      funcao: "servente",
      titulo: "DDS sugerido: uso do protetor auditivo, serventes",
      descricao: "Duas fichas de servente com falha de protetor auditivo no mesmo período",
      data: isoDia(paraMs(hoje) + ((8 - new Date(paraMs(hoje)).getDay()) % 7 || 7) * DIA),
      status: "previsto",
      pendencia_id: null,
    },
    {
      id: "c-dds-arm",
      tipo: "dds",
      funcionario_id: null,
      nome: null,
      funcao: "armador",
      titulo: "DDS sugerido: troca da luva de raspa no prazo, armadores",
      data: isoDia(paraMs(hoje) + 9 * DIA),
      status: "previsto",
      pendencia_id: null,
    },
  ];
  if (treinamentoEdvaldo) {
    const conferido = treinamentoEdvaldo.historico.find((h) => h.etapa === "conferir");
    fixos.push({
      id: "c-trein-0410",
      tipo: "treinamento",
      funcionario_id: "0410",
      nome: "Edvaldo Pereira Santos",
      funcao: "carpinteiro",
      titulo: "Treinamento no uso do protetor auditivo",
      data: conferido ? isoDia(new Date(conferido.ts)) : hoje,
      status: "feito",
      pendencia_id: treinamentoEdvaldo.id,
    });
  }
  for (const item of fixos) if (dentro(item.data)) itens.push({ ...item, origem: "agente" });

  for (const p of m.pendencias) {
    if (!dentro(p.prazo)) continue;
    const funcionario = m.funcionarios.find((f) => f.funcionario_id === p.funcionario_id);
    itens.push({
      id: `c-${p.id}`,
      tipo: "prazo_pendencia",
      funcionario_id: p.funcionario_id,
      nome: p.nome,
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
    const tendencia = Math.max(0, 1 - (dias - i) / (dias * 1.6));
    serie.push({
      data,
      irregular: doDia.filter((a) => a.gravidade === "irregular").length + Math.round(semente(indice) * 3 * tendencia),
      risco: doDia.filter((a) => a.gravidade === "risco").length + Math.round(semente(indice + 7) * 2 * tendencia),
      ok: 10 + Math.round(semente(indice + 13) * 8),
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
  const fichas = concluidas.reduce((s, a) => s + Math.max(a.fichas, 0), 0);
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
    acerto: { precisao: 0.94, recall: 0.9 },
  };
}
