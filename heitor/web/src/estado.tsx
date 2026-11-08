import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useMundo } from "./api";

export type Periodo = "7d" | "30d" | "90d";

export const ROTULO_PERIODO: Record<Periodo, string> = {
  "7d": "Últimos 7 dias",
  "30d": "Últimos 30 dias",
  "90d": "Últimos 90 dias",
};

type ValorEstado = {
  periodo: Periodo;
  setPeriodo: (p: Periodo) => void;
  empresa: string | null;
  pendenciasAbertas: number;
  auditoriaRodando: boolean;
  demoAberta: boolean;
  setDemoAberta: (aberta: boolean) => void;
};

const ContextoEstado = createContext<ValorEstado | null>(null);

export function ProvedorEstado({ children }: { children: ReactNode }) {
  const [periodo, setPeriodo] = useState<Periodo>("30d");
  const [demoAberta, setDemoAberta] = useState(false);
  const mundo = useMundo();
  const empresa = mundo.fonte?.empresa ?? null;
  const pendenciasAbertas = mundo.pendencias.filter((p) => p.status !== "fechada").length;
  const auditoriaRodando = mundo.execucao_atual !== null;

  const valor = useMemo<ValorEstado>(
    () => ({ periodo, setPeriodo, empresa, pendenciasAbertas, auditoriaRodando, demoAberta, setDemoAberta }),
    [periodo, empresa, pendenciasAbertas, auditoriaRodando, demoAberta],
  );
  return <ContextoEstado.Provider value={valor}>{children}</ContextoEstado.Provider>;
}

export function useEstado(): ValorEstado {
  const valor = useContext(ContextoEstado);
  if (!valor) throw new Error("useEstado fora do ProvedorEstado");
  return valor;
}
