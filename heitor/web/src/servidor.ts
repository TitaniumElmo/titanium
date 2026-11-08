/**
 * Loja ligada à API de verdade (heitor/api). Mesma interface do mock.ts: as telas
 * leem o mesmo `Mundo` e não sabem de onde ele vem.
 *
 * - Dados: consulta periódica de GET /auditorias, /auditorias/{id}, /auditorias/{id}/achados,
 *   /pendencias e /fontes.
 * - Log ao vivo: SSE GET /eventos (tudo o que o Elmo faz, inclusive o vigia).
 *
 * Quem decide o que é falha são as regras do back-end; aqui só se mostra o que a API devolve.
 * O que a API ainda não tem (entregas da planilha, configurações, relógio da demo) fica vazio
 * ou só local, nunca inventado.
 */
import type { Mundo, FuncionarioBase } from "./mock";
import type {
  Achado,
  Auditoria,
  ColunaMapeada,
  Configuracao,
  EntradaHistorico,
  Evento,
  Fonte,
  Gatilho,
  ItemAtividade,
  Linha,
  Pendencia,
} from "./tipos";

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");
const EMPRESA = import.meta.env.VITE_EMPRESA || "Construtora (demo)";
const URL_PLANILHA = import.meta.env.VITE_URL_PLANILHA || "";
const INTERVALO_CONSULTA_MS = 2000;
const EDICAO_EXPIRA_MS = 90_000; // o aviso some se nenhuma auditoria começar depois da edição

export const SALARIO_MINIMO_USADO = 1621;
export const CONTA_SERVICO = import.meta.env.VITE_CONTA_SERVICO || "a conta de serviço do Elmo";

const CONFIG_PADRAO: Configuracao = {
  canal_aviso: "E-mail",
  prazo_padrao_dias: 5,
  antecedencia_troca_dias: 15,
  intervalo_leitura_s: 10,
};

// ------------------------------------------------------------- formatos da API ---

type AuditoriaApi = {
  id: string;
  status: Auditoria["status"];
  criada_em: string;
  concluida_em?: string | null;
  disparado_por?: string | null;
  descricao_disparo?: string | null;
  n_fichas?: number;
  modo?: Auditoria["modo"] | null;
  modo_por_funcionario?: Record<string, string> | null;
};

type ResumoAuditoriaApi = AuditoriaApi & {
  contagem_gravidade?: Partial<Record<"irregular" | "risco" | "ok", number>>;
  exposicao_total_rs?: number;
  exposicao?: { por_funcionario?: Record<string, { valor_brl?: number }> } | null;
};

type AchadoApi = Omit<Achado, "nome" | "funcao" | "ts" | "exposicao" | "auditoria_id"> & {
  auditoria_id?: string | null;
  exposicao_rs?: number | null;
};

type HistoricoApi = { status?: string; ts: string; nota?: string | null; etapa?: string; ator?: string };
type PendenciaApi = Omit<Pendencia, "historico"> & { auditoria_id?: string; historico?: HistoricoApi[] };

type ColunaApi = { coluna: string; campo: string | null; confianca: number | null; situacao?: string };
type FontesApi = {
  fonte: string;
  intervalo_s: number;
  rodando: boolean;
  verificacoes: number;
  ultima_verificacao: string | null;
  ultimo_erro: string | null;
  colunas?: Record<string, ColunaApi[]>;
};

type EventoApi = Omit<Evento, "saida"> & { saida: unknown };
// GET /fichas: {funcionario_id: entregas}, cada um com a ficha da auditoria mais recente que o incluiu.
type LinhaApi = Omit<Linha, "data" | "motivo"> & { data: string | null; motivo: string | null };

// --------------------------------------------------------------------- estado ---

const cache = {
  auditorias: [] as AuditoriaApi[],
  detalhes: new Map<string, ResumoAuditoriaApi>(),
  achados: new Map<string, AchadoApi[]>(), // auditoria -> achados (fixos depois de concluída)
  pendencias: [] as PendenciaApi[],
  fontes: null as FontesApi | null,
  eventos: {} as Record<string, Evento[]>,
  funcaoDe: new Map<string, string>(), // funcionário -> função (vinda do log: exigencia_funcao ou auditar_ficha)
  fichas: {} as Record<string, LinhaApi[]>, // entregas da planilha por funcionário (GET /fichas)
  edicao: null as { ts: string; descricao: string; visto_em: number } | null,
  config: { ...CONFIG_PADRAO },
  empresa: EMPRESA,
};

let mundo: Mundo = montarMundo();
const ouvintes = new Set<() => void>();
let ligado = false;
let fonteSse: EventSource | null = null;
let notificacaoPendente: number | null = null;
// Ao conectar, o SSE manda o log inteiro de uma vez. Aviso de edição que chega nessa primeira
// leva é história, não edição acontecendo agora: não acende a faixa "conferindo".
const HISTORICO_SSE_MS = 2500;
let sseAbertoEm = 0;

export function agora(): number {
  return Date.now();
}

export function assinar(ouvinte: () => void): () => void {
  ouvintes.add(ouvinte);
  ligar();
  return () => {
    ouvintes.delete(ouvinte);
  };
}

export function obterMundo(): Mundo {
  return mundo;
}

/** Junta várias mudanças seguidas (o SSE manda dezenas de eventos de uma vez) num só render. */
function atualizar() {
  if (notificacaoPendente !== null) return;
  notificacaoPendente = window.setTimeout(() => {
    notificacaoPendente = null;
    mundo = montarMundo();
    for (const o of ouvintes) o();
  }, 80);
}

// ------------------------------------------------------------------------ HTTP ---

async function pegar<T>(caminho: string): Promise<T | null> {
  try {
    const r = await fetch(`${BASE}${caminho}`, { headers: { Accept: "application/json" } });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null; // API fora do ar: a tela continua com o último retrato
  }
}

async function enviar(caminho: string, corpo?: FormData): Promise<boolean> {
  try {
    const r = await fetch(`${BASE}${caminho}`, { method: "POST", body: corpo });
    if (!r.ok) console.warn(`[elmo] POST ${caminho}: ${r.status} ${await r.text().catch(() => "")}`);
    return r.ok;
  } catch (e) {
    console.warn(`[elmo] POST ${caminho} falhou`, e);
    return false;
  }
}

function ligar() {
  if (ligado || typeof window === "undefined") return;
  ligado = true;
  abrirSse();
  void consultar();
  window.setInterval(() => void consultar(), INTERVALO_CONSULTA_MS);
}

let consultando = false;
async function consultar() {
  if (consultando) return;
  consultando = true;
  try {
    const [auditorias, pendencias, fontes, fichas] = await Promise.all([
      pegar<AuditoriaApi[]>("/auditorias"),
      pegar<PendenciaApi[]>("/pendencias"),
      pegar<FontesApi>("/fontes"), // 404 quando não há vigia (deploy sem pasta)
      pegar<Record<string, LinhaApi[]>>("/fichas"), // null em API antiga, sem a rota: a ficha fica vazia
    ]);
    if (auditorias === null) return; // API fora: mantém o que tinha

    const ids = new Set(auditorias.map((a) => a.id));
    if (cache.auditorias.some((a) => !ids.has(a.id))) esquecerTudo(); // reset da demo apagou auditorias

    // Detalhe e achados: busca de novo só o que ainda está rodando ou mudou de status.
    const buscar = auditorias.filter((a) => {
      const d = cache.detalhes.get(a.id);
      return !d || d.status !== a.status || a.status === "processando";
    });
    await Promise.all(
      buscar.map(async (a) => {
        const [detalhe, achados] = await Promise.all([
          pegar<ResumoAuditoriaApi>(`/auditorias/${encodeURIComponent(a.id)}`),
          pegar<AchadoApi[]>(`/auditorias/${encodeURIComponent(a.id)}/achados`),
        ]);
        if (detalhe) cache.detalhes.set(a.id, detalhe);
        if (achados) cache.achados.set(a.id, achados);
      }),
    );

    cache.auditorias = auditorias;
    if (pendencias) cache.pendencias = pendencias;
    if (fichas) cache.fichas = fichas;
    cache.fontes = fontes;
    atualizar();
  } finally {
    consultando = false;
  }
}

function esquecerTudo() {
  cache.detalhes.clear();
  cache.achados.clear();
  cache.pendencias = [];
  cache.eventos = {};
  cache.funcaoDe.clear();
  cache.fichas = {};
  cache.edicao = null;
  abrirSse(); // o log do servidor recomeçou do zero: lê de novo desde o início
}

// ------------------------------------------------------------------------- SSE ---

function abrirSse() {
  fonteSse?.close();
  cache.eventos = {};
  sseAbertoEm = Date.now();
  const es = new EventSource(`${BASE}/eventos`);
  es.addEventListener("evento", (msg) => {
    try {
      receberEvento(JSON.parse((msg as MessageEvent<string>).data) as EventoApi);
    } catch {
      /* mensagem fora do formato: ignora */
    }
  });
  fonteSse = es; // o navegador reconecta sozinho (Last-Event-ID) se a conexão cair
}

function receberEvento(bruto: EventoApi) {
  const saida: Evento["saida"] =
    bruto.saida && typeof bruto.saida === "object"
      ? ({ resumo: "", ...(bruto.saida as Record<string, unknown>) } as Evento["saida"])
      : { resumo: String(bruto.saida ?? "") }; // ex.: passo 0 manda texto ("disparado por: …")
  const ev: Evento = { ...bruto, saida };

  if (ev.ferramenta === "edicao_detectada" && Date.now() - sseAbertoEm > HISTORICO_SSE_MS) {
    const arquivo = String((ev.entrada as { arquivo?: unknown }).arquivo ?? "planilha");
    cache.edicao = { ts: ev.ts, descricao: arquivo, visto_em: Date.now() };
  }
  // A função vem do exigencia_funcao (o LLM nem sempre chama) ou do auditar_ficha (sempre roda).
  if ((ev.ferramenta === "exigencia_funcao" || ev.ferramenta === "auditar_ficha") && ev.funcionario_id) {
    const funcao = (saida as { funcao?: unknown }).funcao;
    if (typeof funcao === "string" && funcao) cache.funcaoDe.set(ev.funcionario_id, funcao);
  }

  const lista = cache.eventos[ev.auditoria_id] ?? [];
  cache.eventos = { ...cache.eventos, [ev.auditoria_id]: [...lista, ev] };
  atualizar();
}

// ---------------------------------------------------------- API -> Mundo da tela ---

const GATILHOS: Gatilho[] = ["alteracao_planilha", "upload", "manual", "prazo_vencido", "rotina"];
function gatilho(v: string | null | undefined): Gatilho {
  return (GATILHOS as string[]).includes(v ?? "") ? (v as Gatilho) : "manual";
}

function paraAuditoria(a: AuditoriaApi): Auditoria {
  const d = cache.detalhes.get(a.id);
  const c = d?.contagem_gravidade ?? {};
  return {
    id: a.id,
    fonte_id: "f-1",
    status: a.status,
    iniciada_em: a.criada_em,
    contagem: { irregular: c.irregular ?? 0, risco: c.risco ?? 0, ok: c.ok ?? 0 },
    exposicao_total: d?.exposicao_total_rs ?? 0,
    disparado_por: gatilho(a.disparado_por),
    descricao_disparo: a.descricao_disparo ?? "",
    n_fichas: a.n_fichas ?? 0,
    modo: a.modo ?? undefined,
    modo_por_funcionario: (a.modo_por_funcionario ?? undefined) as Auditoria["modo_por_funcionario"],
  };
}

function paraHistorico(h: HistoricoApi): EntradaHistorico {
  return {
    etapa: (h.etapa ?? "conferir") as EntradaHistorico["etapa"],
    ator: (h.ator ?? "agente") as EntradaHistorico["ator"],
    ts: h.ts,
    detalhe: h.nota || h.status || "",
  };
}

function paraPendencia(p: PendenciaApi): Pendencia {
  return { ...p, historico: (p.historico ?? []).map(paraHistorico) };
}

/** Nome de cada funcionário: a pendência traz; quem não tem pendência fica com a matrícula. */
function nomes(pendencias: Pendencia[]): Map<string, string> {
  const m = new Map<string, string>();
  for (const p of pendencias) if (p.funcionario_nome) m.set(p.funcionario_id, p.funcionario_nome);
  return m;
}

/**
 * Cada auditoria do vigia reaudita o funcionário e gera achados novos para o mesmo problema;
 * a pendência continua ligada ao achado antigo. Para não contar o problema duas vezes, fica um
 * achado por (funcionário, regra, linha): o que tem pendência, senão o mais recente.
 */
function achadosAtuais(auditorias: AuditoriaApi[], pendencias: Pendencia[]): (AchadoApi & { auditoria_id: string })[] {
  const comPendencia = new Set(pendencias.map((p) => p.achado_id));
  const escolhido = new Map<string, AchadoApi & { auditoria_id: string }>();
  // /auditorias vem da mais recente para a mais antiga: percorre da antiga para a recente.
  for (const aud of [...auditorias].reverse()) {
    for (const a of cache.achados.get(aud.id) ?? []) {
      const chave = `${a.funcionario_id}|${a.regra}|${a.linha}`;
      const atual = escolhido.get(chave);
      if (atual && comPendencia.has(atual.id) && !comPendencia.has(a.id)) continue;
      escolhido.set(chave, { ...a, auditoria_id: a.auditoria_id || aud.id });
    }
  }
  return [...escolhido.values()];
}

function paraFonte(f: FontesApi | null, temAuditoria: boolean): Fonte | null {
  if (!f) {
    // Sem vigia (deploy só com upload): mostra uma fonte "envio de planilha" assim que houver auditoria.
    if (!temAuditoria) return null;
    const agoraIso = new Date().toISOString();
    return {
      id: "f-1", url: URL_PLANILHA, empresa: cache.empresa, tipo: "planilha", status: "conectada",
      ultima_leitura: cache.auditorias[0]?.criada_em ?? null, mapeamento: [],
      intervalo_s: cache.config.intervalo_leitura_s, proxima_leitura: agoraIso,
    };
  }
  const ultima = f.ultima_verificacao;
  const intervalo = Math.max(1, Math.round(f.intervalo_s));
  const proxima = ultima ? new Date(new Date(ultima).getTime() + intervalo * 1000) : new Date();
  const primeira = Object.values(f.colunas ?? {})[0] ?? [];
  const mapeamento: ColunaMapeada[] = primeira
    .filter((c) => c.campo)
    .map((c) => ({ coluna: c.coluna, campo: c.campo as string, confianca: c.confianca ?? 0 }));
  return {
    id: "f-1",
    url: (f as FontesApi & FonteExtraApi).link || URL_PLANILHA, // a pasta que o vigia observa
    empresa: cache.empresa,
    tipo: /drive/i.test(f.fonte) ? "pasta" : "planilha",
    status: f.ultimo_erro ? "erro" : "conectada",
    ultima_leitura: ultima,
    mapeamento,
    intervalo_s: intervalo,
    proxima_leitura: proxima.toISOString(),
  };
}

function atividade(auditorias: Auditoria[], pendencias: Pendencia[], cruas: AuditoriaApi[]): ItemAtividade[] {
  const fimDe = new Map(cruas.map((a) => [a.id, a.concluida_em ?? a.criada_em]));
  return auditorias
    .filter((a) => a.status !== "processando")
    .map((a) => {
      const inicio = new Date(a.iniciada_em).getTime();
      const fim = new Date(fimDe.get(a.id) ?? a.iniciada_em).getTime() + 5000;
      const abertas = pendencias.filter((p) => (p as PendenciaApi).auditoria_id === a.id).map((p) => p.id);
      const fechadas = pendencias
        .filter((p) => p.status === "fechada")
        .filter((p) => {
          const fechou = [...p.historico].reverse().find((h) => h.etapa === "conferir");
          const t = fechou ? new Date(fechou.ts).getTime() : NaN;
          return t >= inicio && t <= fim;
        })
        .map((p) => p.id);
      const partes = [`${a.contagem.irregular} irregular(es), ${a.contagem.risco} risco(s)`];
      if (abertas.length) partes.push(`${abertas.length} pendência(s) aberta(s)`);
      if (fechadas.length) partes.push(`${fechadas.length} fechada(s)`);
      return {
        id: `at-${a.id}`,
        ts: fimDe.get(a.id) ?? a.iniciada_em,
        disparado_por: a.disparado_por,
        resumo: `${a.descricao_disparo || "auditoria"}: ${partes.join(", ")}`,
        auditoria_id: a.id,
        pendencias_abertas: abertas,
        pendencias_fechadas: fechadas,
      };
    });
}

function montarMundo(): Mundo {
  const cruas = cache.auditorias;
  const auditorias = cruas.map(paraAuditoria);
  const pendencias = cache.pendencias.map(paraPendencia);
  const nomeDe = nomes(pendencias);
  // A planilha também diz nome e função: cobre quem não tem pendência ("Matrícula 0303") e a função vazia.
  const funcaoDe = new Map(cache.funcaoDe);
  for (const [fid, ls] of Object.entries(cache.fichas)) {
    const l = ls.find((x) => x.nome) ?? ls[0];
    if (l?.nome && !nomeDe.has(fid)) nomeDe.set(fid, l.nome);
    if (l?.funcao && !funcaoDe.has(fid)) funcaoDe.set(fid, l.funcao);
  }
  const linhas: Linha[] = Object.values(cache.fichas)
    .flat()
    .map((l) => ({ ...l, data: l.data ?? "", motivo: l.motivo ?? "" }));

  const brutos = achadosAtuais(cruas, pendencias);
  const tsDe = new Map(cruas.map((a) => [a.id, a.criada_em]));
  const ids = new Set<string>([
    ...brutos.map((a) => a.funcionario_id),
    ...pendencias.map((p) => p.funcionario_id),
    ...cruas.flatMap((a) => Object.keys(a.modo_por_funcionario ?? {})),
    ...cache.funcaoDe.keys(),
    ...Object.keys(cache.fichas),
  ]);
  const funcionarios: FuncionarioBase[] = [...ids].sort().map((id) => ({
    funcionario_id: id,
    nome: nomeDe.get(id) ?? `Matrícula ${id}`,
    funcao: funcaoDe.get(id) ?? "",
  }));

  // A API calcula a exposição por funcionário (auditoria.exposicao.por_funcionario), não por achado.
  // A tela soma achado.exposicao: o valor de cada funcionário vai para o primeiro achado de passivo dele.
  const exposicaoDe = new Map<string, number>();
  for (const aud of [...cruas].reverse()) {
    for (const [fid, e] of Object.entries(cache.detalhes.get(aud.id)?.exposicao?.por_funcionario ?? {})) {
      if (typeof e?.valor_brl === "number") exposicaoDe.set(fid, e.valor_brl); // a mais recente vale
    }
  }
  const comExposicao = new Set<string>();
  const achados: Achado[] = brutos.map((a) => {
    let exposicao = a.exposicao_rs ?? undefined;
    if (exposicao === undefined && a.tipo === "passivo" && !comExposicao.has(a.funcionario_id)) {
      exposicao = exposicaoDe.get(a.funcionario_id);
      if (exposicao !== undefined) comExposicao.add(a.funcionario_id);
    }
    return {
      ...a,
      nome: nomeDe.get(a.funcionario_id) ?? `Matrícula ${a.funcionario_id}`,
      funcao: funcaoDe.get(a.funcionario_id) ?? "",
      ts: tsDe.get(a.auditoria_id) ?? new Date().toISOString(),
      exposicao,
    };
  });

  const rodando = auditorias.find((a) => a.status === "processando");
  // O aviso de edição some quando uma auditoria começa depois dela (ou depois de 90 s).
  if (cache.edicao) {
    const ed = cache.edicao;
    const comecou = cruas.some((a) => new Date(a.criada_em).getTime() >= new Date(ed.ts).getTime() - 1000);
    if (comecou || Date.now() - ed.visto_em > EDICAO_EXPIRA_MS) cache.edicao = null;
  }

  return {
    ao_vivo: true,
    deslocamento_ms: 0,
    fonte: paraFonte(cache.fontes, cruas.length > 0),
    funcionarios,
    linhas, // GET /fichas
    fora_da_planilha: [],
    achados,
    pendencias,
    auditorias,
    eventos: cache.eventos,
    atividade: atividade(auditorias, pendencias, cruas),
    config: cache.config,
    cobrancas_hoje: 0,
    execucao_atual: rodando?.id ?? null,
    leituras: cache.fontes?.verificacoes ?? 0,
    contadores: {},
    edicao: cache.edicao ? { ts: cache.edicao.ts, descricao: cache.edicao.descricao } : null,
  };
}

// ------------------------------------------------------------------------ ações ---

/** Sem vigia, "conectar" roda a auditoria nas fichas de exemplo do servidor (POST /auditorias exemplo=true). */
export function conectarFonte(_url: string, empresa: string) {
  if (empresa.trim()) cache.empresa = empresa.trim();
  void rodarExemplo();
}

export async function rodarExemplo() {
  const corpo = new FormData();
  corpo.append("exemplo", "true");
  if (await enviar("/auditorias", corpo)) void consultar();
}

export function desconectarFonte() {
  /* a fonte vem do servidor (.env); a tela não desconecta */
}

/** Força o vigia a olhar a pasta agora. No deploy público exige o token de admin: sem ele, só avisa no console. */
export function lerAgora() {
  void enviar("/fontes/verificar").then((ok) => {
    if (ok) void consultar();
  });
}

export function avancarRelogio(_dias: number) {
  /* não existe na API (só HEITOR_PRAZO_TESTE no servidor) */
}

export function resetarDemo() {
  void enviar("/demo/reset").then((ok) => {
    if (!ok) return;
    esquecerTudo();
    void consultar();
  });
}

export function atualizarConfig(parcial: Partial<Configuracao>) {
  cache.config = { ...cache.config, ...parcial }; // só nesta tela: a API não tem configurações
  atualizar();
}

// ------------------------------------------------------------- troca de pasta ---
// POST /fontes (#37): uma pasta por vez, só o time (token de admin). A troca vale para todos
// e apaga o estado em memória do servidor, como o reset da demo.

type FonteExtraApi = { link?: string | null; conta_servico?: string | null; personalizada?: boolean };

const CHAVE_TOKEN = "elmo-token-admin";

export function tokenGuardado(): string {
  try {
    return window.sessionStorage.getItem(CHAVE_TOKEN) ?? "";
  } catch {
    return "";
  }
}

function guardarToken(token: string) {
  try {
    window.sessionStorage.setItem(CHAVE_TOKEN, token);
  } catch {
    /* sem sessionStorage: pede de novo na próxima vez */
  }
}

/** Com quem compartilhar a pasta e se ela foi trocada pela tela (lido do GET /fontes). */
export function detalhesDaFonte(): { conta_servico: string | null; personalizada: boolean } {
  const f = cache.fontes as (FontesApi & FonteExtraApi) | null;
  return { conta_servico: f?.conta_servico ?? null, personalizada: !!f?.personalizada };
}

async function postAdmin(caminho: string, token: string, corpo?: unknown): Promise<string | null> {
  try {
    const r = await fetch(`${BASE}${caminho}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token.trim()}` },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
    if (r.ok) {
      guardarToken(token.trim());
      esquecerTudo(); // o servidor apagou o estado: a tela também
      void consultar();
      return null;
    }
    if (r.status === 401) return "Senha do time incorreta.";
    const erro = (await r.json().catch(() => null)) as { detail?: unknown } | null;
    return typeof erro?.detail === "string" ? erro.detail : `O servidor recusou (${r.status}).`;
  } catch {
    return "Não consegui falar com o servidor.";
  }
}

/** Troca a pasta observada. Devolve null se deu certo, ou a mensagem para mostrar na tela. */
export function trocarPasta(url: string, token: string, empresa?: string): Promise<string | null> {
  if (empresa?.trim()) cache.empresa = empresa.trim();
  return postAdmin("/fontes", token, { url: url.trim() });
}

export function voltarPastaPadrao(token: string): Promise<string | null> {
  return postAdmin("/fontes/padrao", token);
}
