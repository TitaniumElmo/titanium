import { useEffect, useState, useSyncExternalStore } from "react";
import * as mock from "./mock";
import type { Mundo } from "./mock";

export type { Mundo };

export function useMundo(): Mundo {
  return useSyncExternalStore(mock.assinar, mock.obterMundo, mock.obterMundo);
}

export function useAgora(intervaloMs = 1000): number {
  const [instante, setInstante] = useState(() => mock.agora());
  const mundo = useMundo();
  useEffect(() => {
    setInstante(mock.agora());
    const id = window.setInterval(() => setInstante(mock.agora()), intervaloMs);
    return () => window.clearInterval(id);
  }, [intervaloMs, mundo.deslocamento_ms]);
  return instante;
}

export function useProximaLeitura(): number | null {
  const mundo = useMundo();
  const instante = useAgora(250);
  if (!mundo.fonte) return null;
  return Math.max(0, Math.ceil((new Date(mundo.fonte.proxima_leitura).getTime() - instante) / 1000));
}

export const acoes = {
  conectarFonte: mock.conectarFonte,
  desconectarFonte: mock.desconectarFonte,
  lerAgora: mock.lerAgora,
  avancarRelogio: mock.avancarRelogio,
  resetarDemo: mock.resetarDemo,
  atualizarConfig: mock.atualizarConfig,
};

export const agora = mock.agora;
export const CONTA_SERVICO = mock.CONTA_SERVICO;
export const SALARIO_MINIMO_USADO = mock.SALARIO_MINIMO_USADO;
