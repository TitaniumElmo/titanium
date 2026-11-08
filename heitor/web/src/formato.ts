import type { Destino, Etapa, Gatilho, Gravidade, ModoAuditoria, StatusPendencia, TipoAchado } from "./tipos";

export const ROTULO_GATILHO: Record<Gatilho, string> = {
  alteracao_planilha: "alteração na planilha",
  upload: "envio de planilha",
  manual: "conferência pedida",
  prazo_vencido: "prazo vencido",
  vencimento_futuro: "vencimento próximo",
  nova_base_caepi: "CA cancelado na base",
  email: "e-mail recebido",
  funcionario_novo: "funcionário novo",
  rotina: "rotina diária",
};

export const ROTULO_MODO: Record<ModoAuditoria, string> = {
  llm: "LLM",
  misto: "misto (LLM e regras)",
  deterministico: "só regras",
};

export const ROTULO_REGRA: Record<string, string> = {
  assinatura_ausente: "Entrega sem assinatura",
  ca_ausente: "CA não informado",
  ca_vencido: "CA vencido na entrega",
  ca_nao_encontrado: "CA não encontrado na base",
  ca_cancelado: "CA cancelado ou suspenso",
  ca_conflitante: "CA com dados conflitantes",
  epi_inadequado: "EPI exigido ausente",
  troca_atrasada: "Troca atrasada",
  troca_passado: "Período além da vida útil",
  treinamento_ausente: "Sem registro de treinamento",
  falha_de_ferramenta: "Precisa de revisão",
  funcao_desconhecida: "Função fora da tabela",
  entrega_sem_ficha: "Não está na ficha de papel",
  ficha_sem_planilha: "Só na ficha de papel",
  leitura_incerta: "Leitura da foto em dúvida",
};

export function rotuloRegra(regra: string): string {
  return ROTULO_REGRA[regra] ?? regra.replace(/_/g, " ");
}

export const ROTULO_GRAVIDADE: Record<Gravidade, string> = {
  irregular: "Irregular",
  risco: "Risco",
  ok: "Ok",
};

export const ROTULO_TIPO: Record<TipoAchado, string> = {
  corrigivel: "Corrigível",
  prova: "Prova que talvez exista",
  passivo: "Passivo",
};

export const ROTULO_DESTINO: Record<Destino, string> = {
  tecnico: "Técnico",
  rh: "RH",
};

export const ROTULO_STATUS: Record<StatusPendencia, string> = {
  aberta: "Aberta",
  aguardando: "Aguardando",
  fechada: "Fechada",
  reaberta: "Reaberta",
};

export const ROTULO_ETAPA: Record<Etapa, string> = {
  encontrar: "Encontrar a falha",
  buscar_prova: "Buscar prova que já existe",
  pedir_correcao: "Pedir a correção",
  corrigir: "Corrigir",
  comprovar: "Comprovar",
  conferir: "Conferir",
  cobrar_atraso: "Cobrar atraso",
};

const fusoLocal = Intl.DateTimeFormat().resolvedOptions().timeZone;

function paraData(valor: string | number | Date): Date {
  if (typeof valor === "string" && /^\d{4}-\d{2}-\d{2}$/.test(valor)) return new Date(`${valor}T12:00:00`);
  return new Date(valor);
}

export function hora(valor: string | number | Date): string {
  return paraData(valor).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: fusoLocal });
}

export function horaComSegundos(valor: string | number | Date): string {
  return paraData(valor).toLocaleTimeString("pt-BR", { timeZone: fusoLocal });
}

export function data(valor: string | number | Date): string {
  return paraData(valor).toLocaleDateString("pt-BR");
}

export function dataCurta(valor: string | number | Date): string {
  return paraData(valor).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export function diaDaSemana(valor: string | number | Date): string {
  return paraData(valor).toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" });
}

export function tituloLimpo(titulo: string): string {
  const sem = titulo.replace(/^Prazo da pendência [^:]+:\s*/i, "");
  return sem.charAt(0).toUpperCase() + sem.slice(1);
}

export function reais(valor: number): string {
  return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function dolares(valor: number): string {
  return `US$ ${valor.toLocaleString("pt-BR", { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`;
}

export function porcentagem(valor: number): string {
  return `${Math.round(valor * 100)}%`;
}

export function isoDia(valor: number | Date): string {
  const d = new Date(valor);
  const ano = d.getFullYear();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

export function mesmoDia(a: string | number | Date, b: string | number | Date): boolean {
  return isoDia(paraData(a)) === isoDia(paraData(b));
}

export function rotuloDia(valor: string, agora: number): string {
  if (mesmoDia(valor, agora)) return "Hoje";
  if (mesmoDia(valor, agora - 86_400_000)) return "Ontem";
  const texto = paraData(valor).toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" });
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}
