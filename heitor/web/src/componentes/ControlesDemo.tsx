import { useEffect } from "react";
import { acoes, useMundo } from "../api";
import { useEstado } from "../estado";
import { IconeFechar } from "../util";
import { Botao } from "./base";

const DIA = 86_400_000;

export function PainelDemo() {
  const mundo = useMundo();
  const rodando = mundo.execucao_atual !== null;
  const dias = Math.round(mundo.deslocamento_ms / DIA);
  const semFonte = !mundo.fonte;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Botao variante="primario" disabled={rodando || semFonte} onClick={acoes.lerAgora}>
          Ler planilha agora
        </Botao>
        <Botao disabled={rodando || semFonte} onClick={() => acoes.avancarRelogio(7)}>
          Avançar o relógio 7 dias
        </Botao>
        <Botao variante="fantasma" onClick={acoes.resetarDemo}>
          Resetar demo
        </Botao>
        <Botao variante="fantasma" onClick={() => window.location.reload()}>
          Ver abertura
        </Botao>
      </div>
      <p className={"text-caption tabular-nums text-fraco"}>
        {rodando ? "execução em andamento" : "agente parado"} · relógio {dias > 0 ? `+${dias} dias` : "normal"} · leituras
        desde o reset: {mundo.leituras}
      </p>
    </div>
  );
}

export function ControlesDemo() {
  const { demoAberta, setDemoAberta } = useEstado();

  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && (e.key === "D" || e.key === "d")) {
        e.preventDefault();
        setDemoAberta(!demoAberta);
      }
      if (e.key === "Escape" && demoAberta) setDemoAberta(false);
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [demoAberta, setDemoAberta]);

  if (!demoAberta) return null;
  return (
    <div
      role="dialog"
      aria-label="Controles da demo"
      className="animar-entrar fixed bottom-4 right-4 z-50 w-[min(420px,calc(100vw-2rem))] rounded-cartao border border-borda bg-superficie p-4 shadow-2xl"
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="text-label text-apoio">Controles da demo</span>
        <button
          type="button"
          onClick={() => setDemoAberta(false)}
          className="flex size-7 items-center justify-center rounded-controle text-apoio hover:bg-superficie-2"
          aria-label="Fechar controles da demo"
        >
          <IconeFechar className="size-4" />
        </button>
      </div>
      <PainelDemo />
    </div>
  );
}

export function FaixaDemo() {
  const mundo = useMundo();
  const dias = Math.round(mundo.deslocamento_ms / DIA);
  if (dias <= 0) return null;
  return (
    <div className="sticky top-0 z-20 flex h-7 items-center justify-center gap-2 border-b border-risco-borda/40 bg-risco-fundo text-xs font-medium text-risco max-menu:top-14">
      modo demo · relógio +{dias} dias
    </div>
  );
}
