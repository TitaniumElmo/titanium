import { Link } from "react-router-dom";
import { useMundo } from "../api";
import { hora } from "../formato";
import { NOME_AGENTE } from "../marca";

export function AvisoConferindo() {
  const mundo = useMundo();
  const execucao = mundo.auditorias.find((a) => a.id === mundo.execucao_atual);
  const edicao = mundo.edicao;
  if (!edicao && !execucao) return null;
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
