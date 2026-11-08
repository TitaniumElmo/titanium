import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMundo } from "../api";
import { hora } from "../formato";
import { NOME_AGENTE } from "../marca";

const MOSTRAR_CONCLUSAO_MS = 45_000;

/** Faixa no topo de todas as páginas: "conferindo" enquanto o agente roda e "concluiu" (com o resultado) logo
 * depois. Sem o "concluiu", a faixa só sumia e quem estava olhando ficava sem saber o que aconteceu. */
export function AvisoConferindo() {
  const mundo = useMundo();
  const execucao = mundo.auditorias.find((a) => a.id === mundo.execucao_atual);
  const edicao = mundo.edicao;

  // Só avisa a conclusão de uma auditoria que a tela VIU rodando (abrir a página não mostra auditorias antigas).
  const statusAntes = useRef<Map<string, string>>(new Map());
  const [concluida, setConcluida] = useState<{ id: string; ate: number } | null>(null);
  useEffect(() => {
    for (const a of mundo.auditorias) {
      const antes = statusAntes.current.get(a.id);
      if (antes === "processando" && a.status !== "processando") {
        setConcluida({ id: a.id, ate: Date.now() + MOSTRAR_CONCLUSAO_MS });
      }
      statusAntes.current.set(a.id, a.status);
    }
  }, [mundo.auditorias]);
  useEffect(() => {
    if (!concluida) return;
    const t = window.setTimeout(() => setConcluida(null), Math.max(0, concluida.ate - Date.now()));
    return () => window.clearTimeout(t);
  }, [concluida]);

  if (edicao || execucao) {
    const texto = edicao
      ? `Edição detectada na planilha às ${hora(edicao.ts)} (${edicao.descricao}).`
      : `${NOME_AGENTE} conferindo: ${execucao?.descricao_disparo ?? ""}.`;
    return (
      <div
        role="status"
        className="sticky top-0 z-20 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b border-acento/30 bg-acento-suave px-4 py-2 text-sm max-menu:top-14"
      >
        <span className="flex items-center gap-2">
          <span className="animar-pulsar size-2 rounded-full bg-acento" />
          <span>
            {texto} O {NOME_AGENTE} está conferindo; o resultado aparece aqui em até 1 minuto.
          </span>
        </span>
        <Link to="/agente" className="text-label text-acento hover:underline">
          ver ao vivo
        </Link>
      </div>
    );
  }

  if (!concluida) return null;
  const auditoria = mundo.auditorias.find((a) => a.id === concluida.id);
  const item = mundo.atividade.find((i) => i.auditoria_id === concluida.id);
  if (!auditoria || !item) return null;

  const acaoDe = (id: string) => mundo.pendencias.find((p) => p.id === id)?.acao ?? id;
  const fechadas = item.pendencias_fechadas;
  const abertas = item.pendencias_abertas;
  const partes: string[] = [];
  if (fechadas.length) partes.push(`${fechadas.length} pendência${fechadas.length > 1 ? "s" : ""} fechada${fechadas.length > 1 ? "s" : ""}`);
  if (abertas.length) partes.push(`${abertas.length} nova${abertas.length > 1 ? "s" : ""}`);
  const resultado = partes.length ? partes.join(", ") : "nenhuma pendência mudou";
  const falhou = auditoria.status === "erro";

  return (
    <div
      role="status"
      className={
        "sticky top-0 z-20 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b px-4 py-2 text-sm max-menu:top-14 " +
        (falhou ? "border-acento/30 bg-acento-suave" : "border-ok-borda bg-ok-fundo")
      }
    >
      <span className="flex items-center gap-2">
        <span className={"size-2 rounded-full " + (falhou ? "bg-acento" : "bg-ok-borda")} />
        <span>
          {falhou
            ? `${NOME_AGENTE} não conseguiu concluir a conferência (${auditoria.descricao_disparo}). As pendências ficaram como estavam.`
            : `${NOME_AGENTE} concluiu (${auditoria.descricao_disparo}): ${resultado}.`}
          {!falhou && fechadas.length > 0 && (
            <span className="text-ok"> Fechada: {acaoDe(fechadas[0] ?? "").slice(0, 80)}{fechadas.length > 1 ? " e outras" : ""}.</span>
          )}
        </span>
      </span>
      <Link to="/pendencias" className="text-label text-acento hover:underline">
        ver pendências
      </Link>
      <button
        type="button"
        onClick={() => setConcluida(null)}
        className="text-label text-fraco hover:underline"
        aria-label="Fechar aviso"
      >
        fechar
      </button>
    </div>
  );
}
