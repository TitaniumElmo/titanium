import type { Evento } from "./tipos";

export type Clima = "neutro" | "pedido" | "ok" | "atencao";

export type Traducao = { titulo: string; clima: Clima };

export function traduzir(e: Evento): Traducao {
  const resumo = e.saida.resumo.toLowerCase();
  switch (e.ferramenta) {
    case "ler_fonte":
      return { titulo: "Leu a planilha", clima: "neutro" };
    case "edicao_detectada":
      return { titulo: "Viu uma edição na planilha", clima: "neutro" };
    case "mapear_colunas":
      return { titulo: "Entendeu as colunas da planilha", clima: "neutro" };
    case "extrair_ficha":
      return { titulo: "Leu as fichas de EPI", clima: "neutro" };
    case "reextrair_campo":
      return { titulo: "Releu um campo da ficha", clima: "neutro" };
    case "consulta_ca":
      return { titulo: "Conferiu o CA do equipamento", clima: resumo.includes("vencido") ? "atencao" : "neutro" };
    case "buscar_ca_proximo":
      return { titulo: "Procurou um CA parecido", clima: "neutro" };
    case "exigencia_funcao":
      return { titulo: "Conferiu o que a função exige", clima: "neutro" };
    case "audita_linha":
      return { titulo: "Auditou uma entrega", clima: resumo.includes("ok") ? "ok" : "atencao" };
    case "auditar_ficha":
      return { titulo: "Auditou a ficha inteira", clima: "neutro" };
    case "calcula_exposicao":
      return { titulo: "Calculou a exposição em R$", clima: "neutro" };
    case "historico_da_empresa":
      return { titulo: "Consultou o histórico da empresa", clima: "neutro" };
    case "conferir_ficha_de_papel":
      return { titulo: "Conferiu a ficha de papel", clima: resumo.includes("sem assinatura") || resumo.includes("não localizada") ? "atencao" : "neutro" };
    case "criar_pendencia":
      return { titulo: e.entrada.destino === "rh" || resumo.startsWith("rh") ? "Pediu um documento ao RH" : "Pediu uma correção ao técnico", clima: "pedido" };
    case "cobrar_atraso":
      return { titulo: "Cobrou um prazo vencido", clima: "atencao" };
    case "fechar_pendencia":
      return resumo.includes("reaberta")
        ? { titulo: "Reabriu uma pendência", clima: "atencao" }
        : { titulo: "Conferiu a correção e fechou a pendência", clima: "ok" };
    case "gerar_relatorio":
      return { titulo: "Atualizou o relatório", clima: "neutro" };
    default:
      return { titulo: "Executou um passo", clima: "neutro" };
  }
}

export function duracaoDaExecucao(eventos: Evento[]): string {
  const primeiro = eventos[0];
  const ultimo = eventos[eventos.length - 1];
  if (!primeiro || !ultimo) return "—";
  const segundos = Math.max(0, Math.round((new Date(ultimo.ts).getTime() - new Date(primeiro.ts).getTime()) / 1000));
  if (segundos < 60) return `${segundos} s`;
  return `${Math.floor(segundos / 60)} min ${String(segundos % 60).padStart(2, "0")} s`;
}

export const EXPLICACAO_ERRO: Record<string, string> = {
  modelo_indisponivel: "A inteligência artificial ficou fora do ar. O Elmo seguiu pelas regras, sem deixar de conferir nada.",
  resposta_invalida: "A inteligência artificial deu uma resposta que o Elmo não pôde usar. Ele refez o passo pelas regras.",
  pendencia_recusada: "Uma pendência não pôde ser criada. Ela foi encaminhada para revisão do técnico.",
};
