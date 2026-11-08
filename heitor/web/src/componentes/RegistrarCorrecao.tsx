import { useMemo, useState, type FormEvent } from "react";
import { acoes, useMundo } from "../api";
import { NOME_AGENTE } from "../marca";
import type { Pendencia } from "../tipos";
import { Botao } from "./base";

const CLASSE_CAMPO =
  "h-11 w-full rounded-controle border border-borda bg-superficie-2 px-3 text-sm text-texto placeholder:text-dica focus:border-acento focus:outline-none sm:text-base";

const ROTULO_STATUS: Record<string, string> = {
  fechada: "Corrigido: a pendência foi fechada.",
  reaberta: "Ainda não resolve: a pendência foi reaberta.",
  aguardando: "Documento recebido: aguardando conferência humana.",
};

/** O técnico registra a correção (ou o RH envia o documento) pela tela; o Elmo reaudita com as mesmas regras.
 * Quem testa sozinho (sem acesso à planilha do Drive) também consegue fechar o ciclo. */
export function RegistrarCorrecao({ p, hoje }: { p: Pendencia; hoje: string }) {
  const mundo = useMundo();
  const achado = mundo.achados.find((a) => a.id === p.achado_id);
  const funcionario = mundo.funcionarios.find((f) => f.funcionario_id === p.funcionario_id);

  // Sugestões: o EPI do problema e um CA que a própria empresa já usa para esse EPI (o técnico confere e muda).
  const sugestao = useMemo(() => {
    const evid = achado?.evidencia ?? "";
    const daLinha = mundo.linhas.find((l) => l.funcionario_id === p.funcionario_id && l.linha === achado?.linha);
    const epi =
      evid.match(/nenhuma entrega de ([^;]+?) na ficha/)?.[1] ??
      (["troca_atrasada", "troca_passado"].includes(achado?.regra ?? "") ? evid.split(":")[0] : undefined) ??
      daLinha?.epi ??
      "";
    const ruim = daLinha?.ca ?? "";
    const contagem = new Map<string, number>();
    for (const l of mundo.linhas) {
      const familia = epi.toLowerCase().slice(0, 3); // "bota" e "botina", "protetor auricular" e "protetor auditivo"
      if (l.ca && l.ca !== ruim && familia && l.epi.toLowerCase().startsWith(familia)) {
        contagem.set(l.ca, (contagem.get(l.ca) ?? 0) + 1);
      }
    }
    const ca = [...contagem.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
    return { epi: epi.trim(), ca };
  }, [achado, mundo.linhas, p.funcionario_id]);

  const [data, setData] = useState(hoje);
  const [epi, setEpi] = useState(sugestao.epi);
  const [ca, setCa] = useState(sugestao.ca);
  const [assinou, setAssinou] = useState(true);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<{ ok: boolean; texto: string } | null>(null);

  if (p.status !== "aberta" && p.status !== "reaberta" && !resultado) return null;
  if (p.status !== "aberta" && p.status !== "reaberta" && resultado) {
    return (
      <section role="status" className={"rounded-cartao border p-4 text-sm " + (resultado.ok ? "border-ok-borda bg-ok-fundo text-ok" : "border-acento/30 bg-superficie")}>
        {resultado.texto}
      </section>
    );
  }
  const rh = p.destino === "rh";

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setResultado(null);
    let r;
    if (rh) {
      if (!arquivo) {
        setEnviando(false);
        return;
      }
      r = await acoes.responderPendencia(p.id, arquivo, arquivo.name, "documento enviado pela tela");
    } else {
      const nome = funcionario?.nome ?? p.funcionario_nome;
      const funcao = funcionario?.funcao || achado?.funcao || "";
      const linha = [p.funcionario_id, nome, funcao, data, epi, "1", ca, "T", assinou ? "sim" : "não"]
        .map((c) => String(c).replace(/[;\n]/g, " "))
        .join(";");
      const csv = `funcionario_id;nome;funcao;data;epi;qtd;ca;motivo;assinatura\n${linha}\n`;
      r = await acoes.responderPendencia(
        p.id,
        new Blob([csv], { type: "text/csv" }),
        `correcao_${p.id}.csv`,
        `entrega registrada pela tela: ${epi}, CA ${ca || "sem CA"}, ${data}`,
      );
    }
    setEnviando(false);
    if (r.ok) {
      window.dispatchEvent(new CustomEvent("elmo:correcao", {
        detail: { texto: `${NOME_AGENTE} conferiu a correção de ${p.funcionario_nome}: ${ROTULO_STATUS[r.status ?? ""] ?? r.status}`, ok: r.status !== "reaberta" },
      }));
    }
    setResultado(
      r.ok
        ? { ok: r.status === "fechada" || r.status === "aguardando", texto: `${ROTULO_STATUS[r.status ?? ""] ?? `Status: ${r.status}.`}${r.detalhe ? ` ${r.detalhe}.` : ""}` }
        : { ok: false, texto: `Não deu para enviar: ${r.detalhe ?? "erro"}.` },
    );
  };

  return (
    <section className="rounded-cartao border border-acento/30 bg-superficie p-4">
      <h3 className="text-label text-apoio">{rh ? "Enviar documento" : "Registrar correção"}</h3>
      <p className="mb-3 mt-0.5 text-xs text-fraco">
        {rh
          ? `Envie a nota fiscal ou a lista de presença. O ${NOME_AGENTE} anexa e deixa para conferência humana.`
          : `Registre a entrega feita. O ${NOME_AGENTE} confere com as mesmas regras e fecha a pendência só se resolver.`}
      </p>
      <form onSubmit={enviar} className="flex flex-col gap-3">
        {rh ? (
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp,.csv"
            onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              Data da entrega
              <input type="date" className={CLASSE_CAMPO} value={data} onChange={(e) => setData(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              Nº do CA
              <input className={CLASSE_CAMPO} value={ca} onChange={(e) => setCa(e.target.value)} placeholder="ex.: 17664" inputMode="numeric" />
            </label>
            <label className="col-span-2 flex flex-col gap-1.5 text-sm font-medium">
              EPI entregue
              <input className={CLASSE_CAMPO} value={epi} onChange={(e) => setEpi(e.target.value)} placeholder="ex.: protetor auditivo" />
            </label>
            <label className="col-span-2 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={assinou} onChange={(e) => setAssinou(e.target.checked)} />
              O funcionário assinou a entrega
            </label>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Botao type="submit" variante="primario" disabled={enviando || (rh ? !arquivo : !epi.trim() || !data)}>
            {enviando ? `${NOME_AGENTE} conferindo…` : rh ? "Enviar documento" : "Registrar e conferir"}
          </Botao>
          {resultado && (
            <span role="status" className={resultado.ok ? "text-sm text-ok" : "text-sm text-irregular"}>
              {resultado.texto}
            </span>
          )}
        </div>
      </form>
    </section>
  );
}
