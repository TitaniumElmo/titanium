import { isoDia } from "./formato";
import type { Linha } from "./tipos";

const DIA = 86_400_000;

export const VIDA_UTIL_DIAS: Record<string, number> = {
  capacete: 730,
  botina: 180,
  "óculos de proteção": 180,
  "luva de raspa": 60,
  "protetor auditivo": 90,
  "protetor tipo concha": 180,
};

export const CA_FICTICIO_VENCENDO = "41562";

type Entrega = { data: string; epi: string; ca: string | null; assinatura: boolean; motivo: string };

type Pessoa = { funcionario_id: string; nome: string; funcao: string };

function entrega(data: string, epi: string, ca: string | null, assinatura = true, motivo = "E"): Entrega {
  return { data, epi, ca, assinatura, motivo };
}

function historicoPadrao(): Entrega[] {
  return [
    entrega("2023-02-06", "capacete", "29637"),
    entrega("2023-02-06", "botina", "9182"),
    entrega("2023-02-06", "óculos de proteção", "10344"),
    entrega("2023-05-03", "luva de raspa", "21245"),
    entrega("2023-09-12", "luva de raspa", "21245", true, "T"),
    entrega("2024-03-11", "protetor auditivo", "17664"),
  ];
}

function semProtetor(lista: Entrega[]): Entrega[] {
  return lista.filter((e) => e.epi !== "protetor auditivo");
}

export function gerarLinhas(pessoas: Pessoa[], base: number): Linha[] {
  const linhas: Linha[] = [];
  pessoas.forEach((p, idx) => {
    const recente = (dias: number) => isoDia(base - dias * DIA);
    let lista = historicoPadrao();
    lista.push(entrega(recente(100 + idx * 7), "botina", "12844", true, "T"));
    lista.push(entrega(recente(30 + idx * 5), "protetor auditivo", "17664", true, "T"));
    if (p.funcao === "armador") lista.push(entrega(recente(165), "protetor tipo concha", CA_FICTICIO_VENCENDO));

    switch (p.funcionario_id) {
      case "0115":
        lista = semProtetor(lista);
        break;
      case "0118":
        lista[1] = entrega("2023-03-14", "botina", "9182", false);
        break;
      case "0302":
        lista[4] = entrega("2023-09-12", "luva de raspa", null, true, "T");
        lista = semProtetor(lista);
        break;
      case "0309":
        lista[5] = entrega("2024-01-15", "protetor auditivo", "17664");
        lista.push(entrega("2024-08-05", "protetor auditivo", "17664", true, "T"));
        break;
      case "0417":
        lista[3] = entrega("2024-05-10", "luva de raspa", "21245");
        break;
      case "0520":
        lista[4] = entrega("2025-03-01", "luva de raspa", "21245", true, "T");
        lista[5] = entrega("2025-06-29", "luva de raspa", "21245", true, "T");
        break;
      case "0523":
        lista[3] = entrega("2023-05-03", "luva de raspa", "21245", false);
        break;
      case "0526":
        lista[2] = entrega("2025-02-18", "botina", "28499", true, "T");
        break;
    }

    lista
      .sort((a, b) => a.data.localeCompare(b.data))
      .forEach((e, i) =>
        linhas.push({
          funcionario_id: p.funcionario_id,
          nome: p.nome,
          funcao: p.funcao,
          linha: i + 1,
          data: e.data,
          epi: e.epi,
          qtd: e.epi.startsWith("luva") ? 2 : 1,
          ca: e.ca,
          motivo: e.motivo,
          assinatura: e.assinatura,
          confianca: { ca: e.ca ? 0.97 : 0.99, assinatura: e.assinatura ? 0.92 : 0.88 },
          origem: "planilha",
        }),
      );
  });
  return aplicarConferenciaDePapel(linhas);
}

const COM_FICHA_DE_PAPEL = new Set(["0118", "0121", "0309", "0520", "0523", "0526"]);

export function aplicarConferenciaDePapel(linhas: Linha[]): Linha[] {
  return linhas.map((l) => {
    if (!COM_FICHA_DE_PAPEL.has(l.funcionario_id)) return l;
    const conferida: Linha = { ...l, na_ficha: true, confianca: { ...l.confianca, assinatura: l.assinatura ? 0.95 : 0.93 } };
    if (l.funcionario_id === "0526" && l.ca === "28499") return { ...conferida, na_ficha: false, assinatura: null };
    if (l.funcionario_id === "0520" && l.data === "2025-06-29") return { ...conferida, confianca: { ...conferida.confianca, assinatura: 0.55 } };
    if (l.funcionario_id === "0526" && l.linha === 5) return { ...conferida, confianca: { ...conferida.confianca, assinatura: 0.58 } };
    return conferida;
  });
}

export function linhaNova(p: Pessoa, numero: number, data: string, epi: string, ca: string, motivo = "E"): Linha {
  return {
    funcionario_id: p.funcionario_id,
    nome: p.nome,
    funcao: p.funcao,
    linha: numero,
    data,
    epi,
    qtd: 1,
    ca,
    motivo,
    assinatura: true,
    confianca: { ca: 0.98, assinatura: 0.95 },
    origem: "planilha",
  };
}
