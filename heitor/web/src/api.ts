import { useEffect, useState, useSyncExternalStore } from "react";
import * as mock from "./mock";
import type { Mundo } from "./mock";
import * as servidor from "./servidor";

export type { Mundo };

/**
 * De onde vêm os dados: com VITE_API_URL, da API de verdade (servidor.ts); sem ela,
 * da simulação (mock.ts), que serve de plano B para a demo e para desenvolver a tela.
 */
export const MODO: "api" | "mock" = import.meta.env.VITE_API_URL ? "api" : "mock";
const loja = MODO === "api" ? servidor : mock;

/** O que a tela pode oferecer: a API não tem relógio da demo nem "desconectar" (a fonte vem do .env). */
export const SUPORTA = {
  avancarRelogio: MODO === "mock",
  desconectarFonte: MODO === "mock",
  rodarExemplo: MODO === "api",
  trocarPasta: MODO === "api", // POST /fontes: uma pasta por vez, com a senha do time
  responderPendencia: MODO === "api", // POST /pendencias/{id}/resposta: corrigir pela tela
};

export function useMundo(): Mundo {
  return useSyncExternalStore(loja.assinar, loja.obterMundo, loja.obterMundo);
}

export function useAgora(intervaloMs = 1000): number {
  const [instante, setInstante] = useState(() => loja.agora());
  const mundo = useMundo();
  useEffect(() => {
    setInstante(loja.agora());
    const id = window.setInterval(() => setInstante(loja.agora()), intervaloMs);
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
  conectarFonte: loja.conectarFonte,
  desconectarFonte: loja.desconectarFonte,
  lerAgora: loja.lerAgora,
  avancarRelogio: loja.avancarRelogio,
  resetarDemo: loja.resetarDemo,
  atualizarConfig: loja.atualizarConfig,
  rodarExemplo: servidor.rodarExemplo,
  trocarPasta: servidor.trocarPasta,
  voltarPastaPadrao: servidor.voltarPastaPadrao,
  responderPendencia: servidor.responderPendencia,
};

export const detalhesDaFonte = servidor.detalhesDaFonte;
export const tokenGuardado = servidor.tokenGuardado;

export const agora = loja.agora;
export const CONTA_SERVICO = loja.CONTA_SERVICO;
export const SALARIO_MINIMO_USADO = loja.SALARIO_MINIMO_USADO;
