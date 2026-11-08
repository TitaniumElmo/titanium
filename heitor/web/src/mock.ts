import { gerarLinhas, linhaNova } from "./fichas";
import { isoDia } from "./formato";
import type {
  Achado,
  Auditoria,
  Configuracao,
  EntradaHistorico,
  Evento,
  Ferramenta,
  Fonte,
  ErroAgente,
  ForaDaPlanilha,
  Gatilho,
  ItemAtividade,
  Linha,
  TipoEvento,
  Pendencia,
} from "./tipos";

export type FuncionarioBase = { funcionario_id: string; nome: string; funcao: string };

export type Mundo = {
  deslocamento_ms: number;
  fonte: Fonte | null;
  funcionarios: FuncionarioBase[];
  linhas: Linha[];
  fora_da_planilha: ForaDaPlanilha[];
  achados: Achado[];
  pendencias: Pendencia[];
  auditorias: Auditoria[];
  eventos: Record<string, Evento[]>;
  atividade: ItemAtividade[];
  config: Configuracao;
  cobrancas_hoje: number;
  execucao_atual: string | null;
  leituras: number;
  contadores: Record<string, number>;
  extras_pendencia_demo?: string;
};

const DIA = 86_400_000;
const SALARIO_MINIMO = 1518;
const INTERVALO_PASSO_MS = 900;

export const SALARIO_MINIMO_USADO = SALARIO_MINIMO;

export const CONTA_SERVICO = "leitor@elmo-auditoria.iam.gserviceaccount.com";

const FUNCIONARIOS: FuncionarioBase[] = [
  { funcionario_id: "0115", nome: "João Batista Silva", funcao: "pedreiro" },
  { funcionario_id: "0118", nome: "Marcos Vinícius Rocha", funcao: "pedreiro" },
  { funcionario_id: "0121", nome: "Antônio Carlos Lima", funcao: "pedreiro" },
  { funcionario_id: "0302", nome: "Rafael Souza Costa", funcao: "servente" },
  { funcionario_id: "0305", nome: "Josué Ferreira Alves", funcao: "servente" },
  { funcionario_id: "0309", nome: "Cícero Barbosa Neto", funcao: "servente" },
  { funcionario_id: "0410", nome: "Edvaldo Pereira Santos", funcao: "carpinteiro" },
  { funcionario_id: "0414", nome: "Gilmar Oliveira Torres", funcao: "carpinteiro" },
  { funcionario_id: "0417", nome: "Severino Ramos Dias", funcao: "carpinteiro" },
  { funcionario_id: "0520", nome: "Wellington Araújo Melo", funcao: "armador" },
  { funcionario_id: "0523", nome: "Luiz Henrique Cavalcanti", funcao: "armador" },
  { funcionario_id: "0526", nome: "Damião Gomes Freitas", funcao: "armador" },
];

const CONFIG_PADRAO: Configuracao = {
  canal_aviso: "E-mail",
  prazo_padrao_dias: 5,
  antecedencia_troca_dias: 15,
  intervalo_leitura_s: 20,
};

let mundo: Mundo = criarMundoInicial(Date.now());
let geracao = 0;
const ouvintes = new Set<() => void>();

export function agora(): number {
  return Date.now() + mundo.deslocamento_ms;
}

function iso(ms: number): string {
  return new Date(ms).toISOString();
}

function primeiroNome(id: string): string {
  return FUNCIONARIOS.find((f) => f.funcionario_id === id)?.nome.split(" ")[0] ?? id;
}

function pessoa(id: string): FuncionarioBase {
  const f = FUNCIONARIOS.find((x) => x.funcionario_id === id);
  if (!f) throw new Error(`funcionário ${id} não existe no mock`);
  return f;
}

function exposicao(meses: number): number {
  return Math.round(0.2 * SALARIO_MINIMO * Math.min(meses, 60) * 100) / 100;
}

function criarFonte(url: string, empresa: string, base: number, intervalo_s: number): Fonte {
  return {
    id: "f-1",
    url,
    empresa,
    tipo: url.includes("/folders/") ? "pasta" : "planilha",
    status: "conectada",
    ultima_leitura: iso(base - 12_000),
    intervalo_s,
    proxima_leitura: iso(base + 8_000),
    mapeamento: [
      { coluna: "Colaborador", campo: "nome", confianca: 0.97 },
      { coluna: "Matrícula", campo: "funcionario_id", confianca: 0.95 },
      { coluna: "Função", campo: "funcao", confianca: 0.93 },
      { coluna: "Data entrega", campo: "data", confianca: 0.98 },
      { coluna: "Equipamento", campo: "epi", confianca: 0.91 },
      { coluna: "Nº CA", campo: "ca", confianca: 0.96 },
      { coluna: "Qtd", campo: "qtd", confianca: 0.88 },
      { coluna: "Motivo", campo: "motivo", confianca: 0.72 },
      { coluna: "Visto", campo: "assinatura", confianca: 0.64 },
    ],
  };
}

type Semente = {
  ferramenta: Ferramenta | ErroAgente | null;
  resumo: string;
  tipo?: TipoEvento;
  funcionario?: string;
  entrada?: Record<string, unknown>;
  custo?: number;
};

function pensar(texto: string, funcionario?: string): Semente {
  return { tipo: "decisao", ferramenta: null, resumo: texto, funcionario, custo: 0.0006 };
}

function saidaDe(s: Semente): Evento["saida"] {
  if (s.tipo === "decisao") return { resumo: s.resumo, pensamento: s.resumo };
  if (s.tipo === "erro") return { resumo: s.resumo, erro: s.ferramenta ?? "erro" };
  return { resumo: s.resumo };
}

function eventosPassados(auditoria_id: string, inicio: number, sementes: Semente[]): Evento[] {
  return sementes.map((s, i) => ({
    auditoria_id,
    funcionario_id: s.funcionario ?? null,
    passo: i + 1,
    tipo: s.tipo ?? "ferramenta",
    ferramenta: s.ferramenta,
    entrada: s.entrada ?? {},
    saida: saidaDe(s),
    custo_usd: s.custo ?? (s.tipo === "erro" ? 0 : 0.0004 + (i % 3) * 0.0003),
    ts: iso(inicio + i * 2_100),
  }));
}

function criarMundoInicial(base: number): Mundo {
  const linhas = gerarLinhas(FUNCIONARIOS, base);
  const n = (id: string, cond: (l: Linha) => boolean) =>
    linhas.find((l) => l.funcionario_id === id && cond(l))?.linha ?? 0;
  const nBotina0118 = n("0118", (l) => l.data === "2023-03-14");
  const nProtetor0309 = n("0309", (l) => l.data === "2024-01-15");
  const nLuva0520 = n("0520", (l) => l.data === "2025-06-29");
  const nLuva0523 = n("0523", (l) => l.data === "2023-05-03");
  const nLuva0417 = n("0417", (l) => l.data === "2024-05-10");
  const nLuva0302 = n("0302", (l) => l.ca === null);
  const nBotina0526 = n("0526", (l) => l.ca === "28499");
  const h = (dias: number, horas: number) => {
    const d = new Date(base - dias * DIA);
    d.setHours(horas, (dias * 17) % 60, 0, 0);
    return d.getTime();
  };
  const prazo = (dias: number) => isoDia(base + dias * DIA);

  const achado = (
    id: string,
    funcionario_id: string,
    auditoria_id: string,
    ts: number,
    dados: Omit<Achado, "id" | "funcionario_id" | "nome" | "funcao" | "auditoria_id" | "ts">,
  ): Achado => ({
    id,
    funcionario_id,
    nome: pessoa(funcionario_id).nome,
    funcao: pessoa(funcionario_id).funcao,
    auditoria_id,
    ts: iso(ts),
    ...dados,
  });

  const t1 = h(6, 7);
  const t2 = h(5, 10);
  const t3 = h(3, 16);
  const t4 = h(2, 9);
  const t5 = h(1, 8);
  const t6 = h(0, 7);

  const achados: Achado[] = [
    achado("a-1", "0410", "au-1", t1, {
      linha: 0,
      regra: "treinamento_ausente",
      gravidade: "irregular",
      tipo: "corrigivel",
      evidencia: "Ficha 0410 sem registro de treinamento no uso do protetor auditivo",
      acao_sugerida: "pedir lista de presença ao RH; se não existir, treinar",
    }),
    achado("a-2", "0118", "au-1", t1, {
      linha: nBotina0118,
      regra: "assinatura_ausente",
      gravidade: "irregular",
      tipo: "passivo",
      evidencia: `Linha ${nBotina0118}, entrega de botina em 14/03/2023 sem assinatura`,
      acao_sugerida: "registrar no relatório; colher assinatura nas próximas entregas",
      exposicao: exposicao(8),
    }),
    achado("a-3", "0309", "au-1", t1, {
      linha: nProtetor0309,
      regra: "periodo_sem_epi",
      gravidade: "irregular",
      tipo: "passivo",
      evidencia: "Sem entrega de protetor auditivo entre 02/2024 e 07/2024",
      acao_sugerida: "registrar no relatório como exposição potencial",
      exposicao: exposicao(6),
    }),
    achado("a-4", "0520", "au-4", t4, {
      linha: nLuva0520,
      regra: "troca_vida_util",
      gravidade: "irregular",
      tipo: "corrigivel",
      evidencia: `Linha ${nLuva0520}, luva de raspa trocada após 120 dias; vida útil do fabricante: 60 dias`,
      acao_sugerida: "trocar a luva agora",
    }),
    achado("a-5", "0115", "au-4", t4, {
      linha: 0,
      regra: "epi_ausente",
      gravidade: "irregular",
      tipo: "corrigivel",
      evidencia: "Ficha 0115 sem protetor auditivo desde 03/2024; pedreiro exposto a ruído (betoneira)",
      acao_sugerida: "entregar protetor auditivo e colher assinatura",
    }),
    achado("a-6", "0523", "au-4", t4, {
      linha: nLuva0523,
      regra: "assinatura_ausente",
      gravidade: "irregular",
      tipo: "passivo",
      evidencia: `Linha ${nLuva0523}, entrega de luva em 03/05/2023 sem assinatura`,
      acao_sugerida: "registrar no relatório; colher assinatura nas próximas entregas",
      exposicao: exposicao(5),
    }),
    achado("a-7", "0417", "au-5", t5, {
      linha: nLuva0417,
      regra: "ca_vencido_na_entrega",
      gravidade: "risco",
      tipo: "prova",
      evidencia: `Linha ${nLuva0417}, luva de raspa CA 21245 entregue em 10/05/2024; CA vencido nessa data`,
      acao_sugerida: "pedir nota fiscal ao RH",
    }),
    achado("a-8", "0302", "au-5", t5, {
      linha: nLuva0302,
      regra: "ca_ausente",
      gravidade: "risco",
      tipo: "prova",
      evidencia: `Linha ${nLuva0302}, campo CA vazio (luva de raspa, 12/09/2023)`,
      acao_sugerida: "pedir nota fiscal ao RH",
    }),
    achado("a-9", "0526", "au-6", t6, {
      linha: nBotina0526,
      regra: "ca_vencido_na_entrega",
      gravidade: "risco",
      tipo: "prova",
      evidencia: `Linha ${nBotina0526}, botina CA 28499 entregue em 18/02/2025; CA vencido desde 02/10/2020`,
      acao_sugerida: "pedir nota fiscal ao RH",
    }),
    achado("a-10", "0526", "au-1", t1, {
      linha: nBotina0526,
      regra: "entrega_sem_ficha",
      gravidade: "risco",
      tipo: "prova",
      evidencia: `Linha ${nBotina0526} da planilha (botina CA 28499, 18/02/2025) não localizada na ficha de papel`,
      acao_sugerida: "conferir a ficha física",
    }),
    achado("a-11", "0523", "au-4", t4, {
      linha: 0,
      regra: "ficha_sem_planilha",
      gravidade: "risco",
      tipo: "prova",
      evidencia: "Ficha de papel: luva de raspa em 20/11/2025, sem linha correspondente na planilha",
      acao_sugerida: "lançar a entrega na planilha se ela aconteceu",
    }),
  ];

  const hist = (etapa: EntradaHistorico["etapa"], ator: EntradaHistorico["ator"], ts: number, detalhe: string) => ({
    etapa,
    ator,
    ts: iso(ts),
    detalhe,
  });

  const pendencias: Pendencia[] = [
    {
      id: "p-1",
      achado_id: "a-1",
      funcionario_id: "0410",
      nome: pessoa("0410").nome,
      destino: "tecnico",
      acao: "treinar Edvaldo no uso do protetor auditivo",
      motivo: "Sem registro de treinamento; o RH confirmou que a lista de presença não existe",
      prazo: prazo(-2),
      status: "fechada",
      gatilho: "rotina",
      cobrancas: 0,
      escalada: false,
      prioridade: "normal",
      historico: [
        hist("encontrar", "agente", t1, "audita_linha: treinamento exigido para carpinteiro, sem registro"),
        hist("buscar_prova", "rh", t1 + 60_000, "Pedida ao RH a lista de presença do treinamento"),
        hist("buscar_prova", "rh", t2, "RH respondeu: a lista de presença não existe"),
        hist("pedir_correcao", "agente", t2 + 60_000, "Pendência enviada ao técnico por e-mail"),
        hist("corrigir", "tecnico", t3 - 3 * 3_600_000, "Treinamento aplicado na obra"),
        hist("comprovar", "tecnico", t3 - 3_600_000, "Lista de presença registrada na planilha"),
        hist("conferir", "agente", t3, "Reauditoria: registro de treinamento confere. Pendência fechada"),
      ],
    },
    {
      id: "p-2",
      achado_id: "a-4",
      funcionario_id: "0520",
      nome: pessoa("0520").nome,
      destino: "tecnico",
      acao: "trocar a luva de raspa do Wellington e colher assinatura",
      motivo: "Intervalo entre trocas maior que a vida útil indicada pelo fabricante",
      prazo: prazo(-1),
      status: "reaberta",
      gatilho: "alteracao_planilha",
      cobrancas: 1,
      escalada: false,
      prioridade: "normal",
      historico: [
        hist("encontrar", "agente", t4, "audita_linha: troca após 120 dias; vida útil de 60 dias"),
        hist("pedir_correcao", "agente", t4 + 60_000, "Pendência enviada ao técnico por e-mail"),
        hist("corrigir", "tecnico", t5 - 4 * 3_600_000, "Troca registrada na planilha"),
        hist("comprovar", "tecnico", t5 - 4 * 3_600_000 + 60_000, "Linha nova na ficha 0520"),
        hist("conferir", "agente", t5 - 3 * 3_600_000, "Reauditoria: linha nova sem assinatura. Pendência reaberta"),
        hist("cobrar_atraso", "agente", t6, "Prazo vencido: técnico cobrado por e-mail"),
      ],
    },
    {
      id: "p-3",
      achado_id: "a-5",
      funcionario_id: "0115",
      nome: pessoa("0115").nome,
      destino: "tecnico",
      acao: "Entregar protetor auditivo ao João e colher a assinatura: ele opera a betoneira sem proteção auditiva registrada desde 03/2024.",
      motivo: "Pedreiro exposto a ruído sem protetor auditivo na ficha desde 03/2024",
      prazo: prazo(1),
      status: "aberta",
      gatilho: "alteracao_planilha",
      cobrancas: 0,
      escalada: false,
      prioridade: "alta",
      historico: [
        hist("encontrar", "agente", t4, "audita_linha: protetor auditivo exigido para pedreiro, ausente na ficha"),
        hist("pedir_correcao", "agente", t4 + 90_000, "Pendência enviada ao técnico por e-mail"),
      ],
    },
    {
      id: "p-4",
      achado_id: "a-7",
      funcionario_id: "0417",
      nome: pessoa("0417").nome,
      destino: "rh",
      acao: "enviar a nota fiscal da compra da luva CA 21245",
      motivo: "Critério: CA válido na data da entrega. Vencido nessa data; a nota fiscal pode provar a compra antes",
      prazo: prazo(4),
      status: "aguardando",
      gatilho: "alteracao_planilha",
      cobrancas: 0,
      escalada: false,
      prioridade: "normal",
      historico: [
        hist("encontrar", "agente", t5, "consulta_ca: CA 21245 vencido entre 29/04/2024 e 24/06/2024"),
        hist("buscar_prova", "rh", t5 + 60_000, "Pedida ao RH a nota fiscal da compra"),
      ],
    },
    {
      id: "p-5",
      achado_id: "a-9",
      funcionario_id: "0526",
      nome: pessoa("0526").nome,
      destino: "rh",
      acao: "enviar a nota fiscal da compra da botina CA 28499",
      motivo: "CA vencido desde 02/10/2020 e entrega em 2025; sem nota fiscal vira irregular",
      prazo: prazo(5),
      status: "aberta",
      gatilho: "nova_base_caepi",
      cobrancas: 0,
      escalada: false,
      prioridade: "normal",
      historico: [
        hist("encontrar", "agente", t6, "consulta_ca: CA 28499 vencido desde 02/10/2020"),
        hist("buscar_prova", "rh", t6 + 60_000, "Pedida ao RH a nota fiscal da compra"),
      ],
    },
    {
      id: "p-6",
      achado_id: "a-10",
      funcionario_id: "0526",
      nome: pessoa("0526").nome,
      destino: "tecnico",
      acao: `Conferir na ficha física do Damião: linha ${nBotina0526}: entrega da botina (18/02/2025) não localizada no papel; linha 5: assinatura em dúvida, compare com o nome do funcionário.`,
      motivo: "A planilha tem entregas que a foto da ficha de papel não confirmou",
      prazo: prazo(2),
      status: "aberta",
      gatilho: "rotina",
      cobrancas: 0,
      escalada: false,
      prioridade: "normal",
      historico: [
        hist("encontrar", "agente", t1 + 30_000, "conferir_ficha_de_papel: 1 entrega não localizada, 1 assinatura em dúvida"),
        hist("pedir_correcao", "agente", t1 + 45_000, "Pendência de conferência enviada ao técnico por e-mail"),
      ],
    },
  ];

  const auditoria = (
    id: string,
    inicio: number,
    gatilho: Gatilho,
    gatilho_detalhe: string,
    contagem: Auditoria["contagem"],
    exposicao_total: number,
    fichas = 1,
  ): Auditoria => ({
    id,
    fonte_id: "f-1",
    status: "concluida",
    iniciada_em: iso(inicio),
    contagem,
    exposicao_total,
    gatilho,
    gatilho_detalhe,
    fichas,
    modo: "llm",
  });

  const exp1 = (achados[1]?.exposicao ?? 0) + (achados[2]?.exposicao ?? 0);
  const exp4 = achados[5]?.exposicao ?? 0;

  const auditorias: Auditoria[] = [
    auditoria("au-6", t6, "nova_base_caepi", "base CAEPI atualizada: 1 CA usado na obra mudou de situação", { irregular: 0, risco: 1, ok: 0 }, 0),
    auditoria("au-5", t5, "alteracao_planilha", "1 linha alterada na ficha 0520 e 2 nas fichas 0302 e 0417", { irregular: 0, risco: 2, ok: 1 }, 0, 3),
    auditoria("au-4", t4, "alteracao_planilha", "3 linhas novas nas fichas 0115, 0520 e 0523", { irregular: 3, risco: 0, ok: 4 }, exp4, 3),
    auditoria("au-3", t3, "alteracao_planilha", "1 linha nova na ficha 0410", { irregular: 0, risco: 0, ok: 1 }, 0),
    auditoria("au-2", t2, "email", "RH respondeu sobre a lista de presença da ficha 0410", { irregular: 0, risco: 0, ok: 0 }, 0),
    auditoria("au-1", t1, "rotina", "auditoria completa das 12 fichas", { irregular: 3, risco: 0, ok: 38 }, exp1, 12),
  ];
  const au5 = auditorias.find((a) => a.id === "au-5");
  if (au5) {
    au5.modo = "misto";
    au5.modo_por_funcionario = { "0520": "llm", "0302": "llm", "0417": "degradado" };
  }

  const eventos: Record<string, Evento[]> = {
    "au-1": eventosPassados("au-1", t1, [
      { ferramenta: "ler_fonte", resumo: "12 fichas, 41 linhas lidas" },
      { ferramenta: "mapear_colunas", resumo: "9 colunas mapeadas; Visto com confiança 0,64" },
      pensar("Rotina diária: audito as 12 fichas, 3 por vez. Ficha limpa encerra cedo; ficha suspeita eu investigo.", "0121"),
      { ferramenta: "auditar_ficha", resumo: "ficha 0121: 7 linhas, nenhuma lacuna", funcionario: "0121" },
      { ferramenta: "auditar_ficha", resumo: "ficha 0410: sem registro de treinamento", funcionario: "0410" },
      pensar("Ficha do Antônio limpa: CAs válidos na entrega e EPI certo para a função. Encerro em 2 passos.", "0121"),
      { ferramenta: "auditar_ficha", resumo: "ficha 0526: botina com CA vencido na entrega", funcionario: "0526" },
      pensar("Treinamento exigido sem registro. Antes de cobrar o técnico, peço a lista de presença ao RH.", "0410"),
      { ferramenta: "criar_pendencia", entrada: { destino: "rh" }, resumo: "RH: lista de presença da ficha 0410", funcionario: "0410" },
      pensar("Ficha do Damião suspeita: CA vencido desde 2020 e entrega em 2025. Vou investigar.", "0526"),
      { ferramenta: "historico_da_empresa", resumo: "outras fichas com CA 28499: nenhuma", funcionario: "0526" },
      { ferramenta: "consulta_ca", entrada: { numero: "28499" }, resumo: "CA 28499 vencido desde 02/10/2020", funcionario: "0526" },
      { ferramenta: "conferir_ficha_de_papel", resumo: `linha ${nBotina0526} não localizada na ficha de papel`, funcionario: "0526" },
      pensar("A entrega da botina não está no papel e o CA venceu antes. Peço a nota fiscal ao RH e a conferência física ao técnico.", "0526"),
      { ferramenta: "criar_pendencia", entrada: { destino: "tecnico" }, resumo: "técnico: conferir a ficha física do Damião", funcionario: "0526" },
      { ferramenta: "auditar_ficha", resumo: `ficha 0118: linha ${nBotina0118} sem assinatura`, funcionario: "0118" },
      { ferramenta: "auditar_ficha", resumo: "ficha 0309: sem protetor de 02 a 07/2024", funcionario: "0309" },
      { ferramenta: "calcula_exposicao", resumo: "Exposição potencial máxima de 14 meses" },
      { ferramenta: "gerar_relatorio", resumo: "Relatório com 3 achados" },
    ]),
    "au-2": eventosPassados("au-2", t2, [
      { ferramenta: "ler_fonte", resumo: "E-mail do RH: lista de presença não existe" },
      { ferramenta: "criar_pendencia", resumo: "Técnico: treinar Edvaldo, prazo 5 dias" },
    ]),
    "au-3": eventosPassados("au-3", t3, [
      { ferramenta: "ler_fonte", resumo: "1 linha nova na ficha 0410" },
      { ferramenta: "extrair_ficha", resumo: "Treinamento registrado em " + isoDia(t3).split("-").reverse().join("/") },
      { ferramenta: "audita_linha", resumo: "Registro de treinamento confere → ok" },
      { ferramenta: "fechar_pendencia", resumo: "Correção confere: p-1 fechada" },
    ]),
    "au-4": eventosPassados("au-4", t4, [
      { ferramenta: "ler_fonte", resumo: "3 linhas novas em 3 fichas" },
      { ferramenta: "extrair_ficha", resumo: "Fichas 0115, 0520 e 0523 lidas" },
      { ferramenta: "exigencia_funcao", resumo: "Pedreiro: ruído → protetor auditivo" },
      { ferramenta: "audita_linha", resumo: "Ficha 0115 sem protetor auditivo → irregular" },
      { ferramenta: "audita_linha", resumo: "Luva da ficha 0520 além da vida útil → irregular" },
      { ferramenta: "audita_linha", resumo: `Linha ${nLuva0523} da ficha 0523 sem assinatura → passivo` },
      { ferramenta: "calcula_exposicao", resumo: "Exposição potencial máxima de 5 meses" },
      { ferramenta: "criar_pendencia", resumo: "Técnico: protetor auditivo para o João" },
      { ferramenta: "criar_pendencia", resumo: "Técnico: trocar a luva do Wellington" },
      { ferramenta: "gerar_relatorio", resumo: "Relatório com 3 achados novos" },
    ]),
    "au-5": eventosPassados("au-5", t5, [
      { ferramenta: "ler_fonte", resumo: "3 linhas alteradas" },
      {
        tipo: "erro",
        ferramenta: "modelo_indisponivel",
        resumo: "LLM indisponível: a ficha 0417 segue com a política determinística (modo degradado)",
        funcionario: "0417",
      },
      { ferramenta: "audita_linha", resumo: "Troca na ficha 0520 sem assinatura → não confere" },
      { ferramenta: "fechar_pendencia", resumo: "p-2 reaberta: falta assinatura" },
      { ferramenta: "consulta_ca", resumo: "CA 21245 vencido na data da entrega" },
      { ferramenta: "audita_linha", resumo: `Linha ${nLuva0417} da ficha 0417 → risco`, funcionario: "0417" },
      { ferramenta: "audita_linha", resumo: `Linha ${nLuva0302} da ficha 0302, CA vazio → risco` },
      { ferramenta: "criar_pendencia", resumo: "RH: nota fiscal da luva CA 21245" },
    ]),
    "au-6": eventosPassados("au-6", t6, [
      { ferramenta: "consulta_ca", resumo: "CA 28499: vencido desde 02/10/2020" },
      { ferramenta: "audita_linha", resumo: `Linha ${nBotina0526} da ficha 0526 → risco` },
      { ferramenta: "criar_pendencia", resumo: "RH: nota fiscal da botina CA 28499" },
      { ferramenta: "cobrar_atraso", resumo: "Técnico cobrado: p-2, prazo vencido" },
    ]),
  };

  const atividade: ItemAtividade[] = [
    {
      id: "at-6",
      ts: iso(t6),
      gatilho: "nova_base_caepi",
      resumo: "CA 28499 vencido na base CAEPI → auditou a ficha do Damião → pediu nota fiscal ao RH; cobrou o técnico pela pendência do Wellington",
      auditoria_id: "au-6",
      pendencias_abertas: ["p-5"],
      pendencias_fechadas: [],
    },
    {
      id: "at-5",
      ts: iso(t5),
      gatilho: "alteracao_planilha",
      resumo: "Detectou 3 linhas alteradas → a troca do Wellington veio sem assinatura e a pendência foi reaberta → pediu nota fiscal ao RH",
      auditoria_id: "au-5",
      pendencias_abertas: ["p-4", "p-2"],
      pendencias_fechadas: [],
    },
    {
      id: "at-4",
      ts: iso(t4),
      gatilho: "alteracao_planilha",
      resumo: "Detectou 3 linhas novas → auditou → abriu 2 pendências para o técnico e registrou 1 passivo",
      auditoria_id: "au-4",
      pendencias_abertas: ["p-3", "p-2"],
      pendencias_fechadas: [],
    },
    {
      id: "at-3",
      ts: iso(t3),
      gatilho: "alteracao_planilha",
      resumo: "Detectou o treinamento do Edvaldo na planilha → conferiu → fechou a pendência",
      auditoria_id: "au-3",
      pendencias_abertas: [],
      pendencias_fechadas: ["p-1"],
    },
    {
      id: "at-2",
      ts: iso(t2),
      gatilho: "email",
      resumo: "RH respondeu que a lista de presença não existe → pediu ao técnico que treine o Edvaldo",
      auditoria_id: "au-2",
      pendencias_abertas: ["p-1"],
      pendencias_fechadas: [],
    },
    {
      id: "at-1",
      ts: iso(t1),
      gatilho: "rotina",
      resumo: "Auditou as 12 fichas → 3 irregulares → pediu ao RH a lista de presença do Edvaldo",
      auditoria_id: "au-1",
      pendencias_abertas: [],
      pendencias_fechadas: [],
    },
  ];

  return {
    deslocamento_ms: 0,
    fonte: criarFonte(
      "https://docs.google.com/spreadsheets/d/exemplo-construtora-mandacaru",
      "Construtora Mandacaru",
      base,
      CONFIG_PADRAO.intervalo_leitura_s,
    ),
    funcionarios: FUNCIONARIOS,
    linhas,
    fora_da_planilha: [{ funcionario_id: "0523", data: "2025-11-20", epi: "luva de raspa" }],
    achados,
    pendencias,
    auditorias,
    eventos,
    atividade,
    config: { ...CONFIG_PADRAO },
    cobrancas_hoje: 1,
    execucao_atual: null,
    leituras: 0,
    contadores: { a: 11, p: 6, au: 6, at: 6 },
  };
}

function notificar() {
  ouvintes.forEach((ouvinte) => ouvinte());
}

function mudar(alterar: (m: Mundo) => void) {
  const copia = structuredClone(mundo);
  alterar(copia);
  mundo = copia;
  notificar();
}

function novoId(prefixo: string, m: Mundo): string {
  const proximo = (m.contadores[prefixo] ?? 0) + 1;
  m.contadores[prefixo] = proximo;
  return `${prefixo}-${proximo}`;
}

export function assinar(ouvinte: () => void): () => void {
  ouvintes.add(ouvinte);
  garantirRelogio();
  return () => {
    ouvintes.delete(ouvinte);
  };
}

export function obterMundo(): Mundo {
  return mundo;
}

type Passo = Semente & {
  efeito?: (m: Mundo, ctx: Contexto) => void;
};

type Contexto = {
  auditoria_id: string;
  abertas: string[];
  fechadas: string[];
  extras: Record<string, string>;
};

type Roteiro = {
  fichas: number;
  gatilho: Gatilho;
  detalhe: string;
  contagem: Auditoria["contagem"];
  passos: Passo[];
  resumo: (ctx: Contexto) => string;
};

function iniciarExecucao(roteiro: Roteiro) {
  const minhaGeracao = geracao;
  let ctx: Contexto | null = null;
  mudar((m) => {
    const id = novoId("au", m);
    ctx = { auditoria_id: id, abertas: [], fechadas: [], extras: {} };
    m.auditorias.unshift({
      id,
      fonte_id: m.fonte?.id ?? "f-1",
      status: "rodando",
      iniciada_em: iso(agora()),
      contagem: { irregular: 0, risco: 0, ok: 0 },
      exposicao_total: 0,
      gatilho: roteiro.gatilho,
      gatilho_detalhe: roteiro.detalhe,
      fichas: roteiro.fichas,
      modo: "llm",
    });
    m.eventos[id] = [];
    m.execucao_atual = id;
    if (m.fonte) m.fonte.status = "lendo";
  });
  const contexto = ctx as Contexto | null;
  if (!contexto) return;

  roteiro.passos.forEach((passo, i) => {
    window.setTimeout(() => {
      if (geracao !== minhaGeracao) return;
      mudar((m) => {
        passo.efeito?.(m, contexto);
        m.eventos[contexto.auditoria_id]?.push({
          auditoria_id: contexto.auditoria_id,
          funcionario_id: passo.funcionario ?? null,
          passo: i + 1,
          tipo: passo.tipo ?? "ferramenta",
          ferramenta: passo.ferramenta,
          entrada: passo.entrada ?? {},
          saida: saidaDe(passo),
          custo_usd: passo.custo ?? 0.0003 + ((i * 7) % 5) * 0.0002,
          ts: iso(agora()),
        });
      });
    }, (i + 1) * INTERVALO_PASSO_MS);
  });

  window.setTimeout(
    () => {
      if (geracao !== minhaGeracao) return;
      mudar((m) => {
        const auditoria = m.auditorias.find((a) => a.id === contexto.auditoria_id);
        if (auditoria) {
          auditoria.status = "concluida";
          auditoria.contagem = roteiro.contagem;
          auditoria.exposicao_total = m.achados
            .filter((a) => a.auditoria_id === contexto.auditoria_id)
            .reduce((soma, a) => soma + (a.exposicao ?? 0), 0);
        }
        m.atividade.unshift({
          id: novoId("at", m),
          ts: iso(agora()),
          gatilho: roteiro.gatilho,
          resumo: roteiro.resumo(contexto),
          auditoria_id: contexto.auditoria_id,
          pendencias_abertas: contexto.abertas,
          pendencias_fechadas: contexto.fechadas,
        });
        m.execucao_atual = null;
        if (m.fonte) m.fonte.status = "conectada";
      });
    },
    (roteiro.passos.length + 1) * INTERVALO_PASSO_MS,
  );
}

function roteiroLinhasNovas(): Roteiro {
  const id = "0302";
  const nome = primeiroNome(id);
  return {
    fichas: 1,
    gatilho: "alteracao_planilha",
    detalhe: "2 linhas novas na ficha 0302",
    contagem: { irregular: 1, risco: 0, ok: 2 },
    resumo: (ctx) =>
      `Detectou 2 linhas novas na ficha do ${nome} → auditou → abriu ${ctx.abertas.length} pendência para o técnico`,
    passos: [
      { ferramenta: "ler_fonte", entrada: { fonte: "f-1" }, resumo: "2 linhas novas na ficha 0302" },
      { ferramenta: "mapear_colunas", resumo: "Colunas iguais às da última leitura" },
      pensar(`2 linhas novas na ficha do ${nome}. Confiro CA e EPI exigido antes de abrir qualquer pendência.`, id),
      {
        ferramenta: "extrair_ficha",
        entrada: { ficha: id },
        funcionario: id,
        resumo: `ficha do ${nome}, linhas 7 e 8`,
        efeito: (m) => {
          const hoje = isoDia(agora());
          m.linhas.push(linhaNova(pessoa(id), 7, hoje, "botina", "9182", "T"), linhaNova(pessoa(id), 8, hoje, "capacete", "29637", "T"));
        },
      },
      {
        ferramenta: "conferir_ficha_de_papel",
        funcionario: id,
        resumo: "linhas 7 e 8: assinatura compatível com o nome",
        efeito: (m) => {
          for (const l of m.linhas) if (l.funcionario_id === id && l.linha >= 7) l.na_ficha = true;
        },
      },
      { ferramenta: "reextrair_campo", entrada: { linha: 8, campo: "assinatura" }, resumo: "Visto da linha 8: 0,62 → 0,95, presente", funcionario: id },
      { ferramenta: "exigencia_funcao", entrada: { funcao: "servente" }, resumo: "servente: ruído → protetor auditivo", funcionario: id },
      { ferramenta: "consulta_ca", entrada: { numero: "9182" }, resumo: "CA 9182 (botina) válido na entrega", funcionario: id },
      { ferramenta: "audita_linha", entrada: { linha: 7 }, resumo: "linha 7, botina → ok", funcionario: id },
      { ferramenta: "consulta_ca", entrada: { numero: "29637" }, resumo: "CA 29637 (capacete) válido na entrega", funcionario: id },
      { ferramenta: "audita_linha", entrada: { linha: 8 }, resumo: "linha 8, capacete → ok", funcionario: id },
      {
        ferramenta: "audita_linha",
        entrada: { funcionario_id: id, regra: "epi_adequado" },
        funcionario: id,
        resumo: "sem protetor auditivo → irregular",
        efeito: (m, ctx) => {
          const achado_id = novoId("a", m);
          ctx.extras.achado = achado_id;
          m.achados.unshift({
            id: achado_id,
            funcionario_id: id,
            nome: pessoa(id).nome,
            funcao: pessoa(id).funcao,
            linha: 0,
            regra: "epi_ausente",
            gravidade: "irregular",
            tipo: "corrigivel",
            evidencia: "Ficha 0302 sem protetor auditivo; servente exposto a ruído (betoneira)",
            acao_sugerida: "entregar protetor auditivo e colher assinatura",
            auditoria_id: ctx.auditoria_id,
            ts: iso(agora()),
          });
        },
      },
      pensar(`Servente na betoneira sem protetor auditivo: o ${nome} está sem proteção hoje. Prazo de 1 dia.`, id),
      {
        ferramenta: "criar_pendencia",
        entrada: { destino: "tecnico" },
        funcionario: id,
        resumo: `técnico, protetor do ${nome}, prazo 1 dia`,
        efeito: (m, ctx) => {
          const pid = novoId("p", m);
          ctx.abertas.push(pid);
          m.extras_pendencia_demo = pid;
          const t = agora();
          m.pendencias.unshift({
            id: pid,
            achado_id: ctx.extras.achado ?? "",
            funcionario_id: id,
            nome: pessoa(id).nome,
            destino: "tecnico",
            acao: `Entregar protetor auditivo ao ${nome} e colher a assinatura: ele trabalha na betoneira sem proteção auditiva registrada.`,
            motivo: "Servente exposto a ruído sem protetor auditivo na ficha",
            prazo: isoDia(t + DIA),
            status: "aberta",
            gatilho: "alteracao_planilha",
            cobrancas: 0,
            escalada: false,
            prioridade: "alta",
            historico: [
              { etapa: "encontrar", ator: "agente", ts: iso(t - 2_000), detalhe: "audita_linha: protetor auditivo exigido para servente, ausente na ficha" },
              { etapa: "pedir_correcao", ator: "agente", ts: iso(t), detalhe: "Pendência enviada ao técnico por e-mail" },
            ],
          });
        },
      },
      { ferramenta: "gerar_relatorio", resumo: "Relatório atualizado: 1 achado novo" },
    ],
  };
}

function roteiroCorrecao(pendencia_id: string | undefined): Roteiro {
  const id = "0302";
  const nome = primeiroNome(id);
  return {
    fichas: 1,
    gatilho: "alteracao_planilha",
    detalhe: "1 linha nova na ficha 0302 (correção)",
    contagem: { irregular: 0, risco: 0, ok: 1 },
    resumo: (ctx) =>
      ctx.fechadas.length
        ? `Detectou a entrega do protetor ao ${nome} → conferiu → fechou a pendência`
        : `Detectou 1 linha nova na ficha do ${nome} → auditou → sem lacunas`,
    passos: [
      { ferramenta: "ler_fonte", entrada: { fonte: "f-1" }, resumo: "1 linha nova na ficha 0302" },
      pensar(`Linha nova na ficha do ${nome}, que tem pendência aberta. Confiro se é a correção.`, id),
      {
        ferramenta: "extrair_ficha",
        entrada: { ficha: id },
        funcionario: id,
        resumo: "linha 9, protetor auditivo, com visto",
        efeito: (m) => {
          m.linhas.push(linhaNova(pessoa(id), 9, isoDia(agora()), "protetor auditivo", "17664"));
        },
      },
      { ferramenta: "consulta_ca", entrada: { numero: "17664" }, resumo: "CA 17664 (protetor) válido na entrega" },
      { ferramenta: "exigencia_funcao", entrada: { funcao: "servente" }, resumo: "servente: protetor auditivo exigido" },
      { ferramenta: "audita_linha", entrada: { linha: 9 }, resumo: "linha 9, protetor entregue e assinado → ok" },
      {
        ferramenta: "fechar_pendencia",
        entrada: { pendencia: pendencia_id ?? null },
        resumo: pendencia_id ? `correção confere, ${pendencia_id} fechada` : "nenhuma pendência a fechar",
        efeito: (m, ctx) => {
          const p = m.pendencias.find((x) => x.id === pendencia_id && x.status !== "fechada");
          if (!p) return;
          const t = agora();
          p.historico.push(
            { etapa: "corrigir", ator: "tecnico", ts: iso(t - 60_000), detalhe: "Protetor auditivo entregue na obra" },
            { etapa: "comprovar", ator: "tecnico", ts: iso(t - 30_000), detalhe: "Linha 9 adicionada na planilha, com visto" },
            { etapa: "conferir", ator: "agente", ts: iso(t), detalhe: "Reauditoria: entrega confere. Pendência fechada" },
          );
          p.status = "fechada";
          ctx.fechadas.push(p.id);
        },
      },
      { ferramenta: "gerar_relatorio", resumo: "Ficha 0302 sem lacunas abertas" },
    ],
  };
}

function roteiroPrazos(m: Mundo): Roteiro | null {
  const hoje = isoDia(agora());
  const vencidas = m.pendencias.filter((p) => p.status !== "fechada" && p.prazo < hoje);
  if (!vencidas.length) return null;
  const escaladas: string[] = [];
  const passos: Passo[] = vencidas.map((p) => {
    const segunda = p.cobrancas + 1 >= 2;
    if (segunda) escaladas.push(p.id);
    const quem = p.destino === "rh" ? "RH" : "técnico";
    return {
      ferramenta: "cobrar_atraso",
      entrada: { pendencia: p.id, cobranca: p.cobrancas + 1 },
      resumo: segunda ? `${p.id}, 2ª cobrança, escalado` : `${quem}, ${p.id} vencida`,
      efeito: (mm, ctx) => {
        const alvo = mm.pendencias.find((x) => x.id === p.id);
        if (!alvo) return;
        alvo.cobrancas += 1;
        mm.cobrancas_hoje += 1;
        const ts = iso(agora());
        if (alvo.cobrancas >= 2) {
          alvo.escalada = true;
          alvo.prioridade = "alta";
          alvo.historico.push({ etapa: "cobrar_atraso", ator: "agente", ts, detalhe: "Segunda cobrança: escalado ao coordenador" });
        } else {
          alvo.historico.push({ etapa: "cobrar_atraso", ator: "agente", ts, detalhe: `Prazo vencido: ${quem} cobrado por e-mail` });
        }
        ctx.abertas.push(alvo.id);
      },
    };
  });
  passos.push({ ferramenta: "gerar_relatorio", resumo: `${vencidas.length} prazos vencidos no relatório` });
  return {
    fichas: 0,
    gatilho: "prazo_vencido",
    detalhe: `${vencidas.length} pendências com prazo vencido`,
    contagem: { irregular: 0, risco: 0, ok: 0 },
    resumo: () =>
      `${vencidas.length} prazos vencidos → cobrou o técnico e o RH` +
      (escaladas.length ? ` → escalou ${escaladas.join(", ")} ao coordenador` : ""),
    passos,
  };
}

function fazerLeitura() {
  if (!mundo.fonte || mundo.execucao_atual) return;
  const proxima = mundo.leituras + 1;
  mudar((m) => {
    m.leituras = proxima;
    if (m.fonte) {
      m.fonte.ultima_leitura = iso(agora());
      m.fonte.proxima_leitura = iso(agora() + m.config.intervalo_leitura_s * 1000);
    }
  });
  if (proxima === 1) iniciarExecucao(roteiroLinhasNovas());
  else if (proxima === 2) iniciarExecucao(roteiroCorrecao(mundo.extras_pendencia_demo));
}

let relogio: number | null = null;

function garantirRelogio() {
  if (relogio !== null || typeof window === "undefined") return;
  relogio = window.setInterval(() => {
    const fonte = mundo.fonte;
    if (!fonte || mundo.execucao_atual) return;
    if (agora() >= new Date(fonte.proxima_leitura).getTime()) fazerLeitura();
  }, 500);
}

export function conectarFonte(url: string, empresa: string) {
  geracao += 1;
  const base = Date.now();
  const novo = criarMundoInicial(base);
  novo.fonte = criarFonte(url, empresa, base, mundo.config.intervalo_leitura_s);
  novo.config = { ...mundo.config };
  mundo = novo;
  notificar();
}

export function desconectarFonte() {
  geracao += 1;
  mudar((m) => {
    m.fonte = null;
    m.achados = [];
    m.linhas = [];
    m.fora_da_planilha = [];
    m.pendencias = [];
    m.auditorias = [];
    m.eventos = {};
    m.atividade = [];
    m.execucao_atual = null;
    m.cobrancas_hoje = 0;
    m.leituras = 0;
    m.deslocamento_ms = 0;
  });
}

export function lerAgora() {
  if (!mundo.fonte || mundo.execucao_atual) return;
  fazerLeitura();
}

export function avancarRelogio(dias: number) {
  if (mundo.execucao_atual) return;
  mudar((m) => {
    m.deslocamento_ms += dias * DIA;
    if (m.fonte) m.fonte.proxima_leitura = iso(Date.now() + m.deslocamento_ms + m.config.intervalo_leitura_s * 1000);
  });
  const roteiro = roteiroPrazos(mundo);
  if (roteiro) iniciarExecucao(roteiro);
}

export function resetarDemo() {
  geracao += 1;
  const config = mundo.config;
  mundo = criarMundoInicial(Date.now());
  mundo.config = { ...config };
  if (mundo.fonte) mundo.fonte.intervalo_s = config.intervalo_leitura_s;
  notificar();
}

export function atualizarConfig(parcial: Partial<Configuracao>) {
  mudar((m) => {
    m.config = { ...m.config, ...parcial };
    if (m.fonte && parcial.intervalo_leitura_s) {
      m.fonte.intervalo_s = parcial.intervalo_leitura_s;
      m.fonte.proxima_leitura = iso(agora() + parcial.intervalo_leitura_s * 1000);
    }
  });
}
