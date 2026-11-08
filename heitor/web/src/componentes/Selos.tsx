import type { ReactNode } from "react";
import { ROTULO_DESTINO, ROTULO_GATILHO, ROTULO_GRAVIDADE, ROTULO_STATUS, ROTULO_TIPO } from "../formato";
import type { Destino, Gatilho, Gravidade, StatusPendencia, TipoAchado } from "../tipos";
import { cn } from "../util";

const BASE_SELO =
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-selo border px-2 py-0.5 text-xs font-medium leading-4";

export function Selo({ className, children, titulo }: { className?: string; children: ReactNode; titulo?: string }) {
  return (
    <span className={cn(BASE_SELO, "border-borda bg-superficie-2 text-apoio", className)} title={titulo}>
      {children}
    </span>
  );
}

const CORES_GRAVIDADE: Record<Gravidade, string> = {
  irregular: "border-irregular-borda/40 bg-irregular-fundo text-irregular",
  risco: "border-risco-borda/40 bg-risco-fundo text-risco",
  ok: "border-ok-borda/40 bg-ok-fundo text-ok",
};

const PONTO_GRAVIDADE: Record<Gravidade, string> = {
  irregular: "bg-irregular-borda",
  risco: "bg-risco-borda",
  ok: "bg-ok-borda",
};

export function SeloGravidade({ gravidade }: { gravidade: Gravidade }) {
  return (
    <span className={cn(BASE_SELO, CORES_GRAVIDADE[gravidade])}>
      <span className={cn("size-1.5 rounded-full", PONTO_GRAVIDADE[gravidade])} />
      {ROTULO_GRAVIDADE[gravidade]}
    </span>
  );
}

export function SeloTipo({ tipo }: { tipo: TipoAchado }) {
  return <Selo className={tipo === "passivo" ? "border-dashed" : undefined}>{ROTULO_TIPO[tipo]}</Selo>;
}

export function SeloGatilho({ gatilho, comPrefixo = false }: { gatilho: Gatilho; comPrefixo?: boolean }) {
  return (
    <Selo className="text-texto">
      <span className="size-1.5 rounded-full bg-apoio" />
      {comPrefixo && <span className="text-fraco">Disparado por:</span>}
      {ROTULO_GATILHO[gatilho]}
    </Selo>
  );
}

export function SeloDestino({ destino }: { destino: Destino }) {
  return <Selo>{ROTULO_DESTINO[destino]}</Selo>;
}

const CORES_STATUS: Record<StatusPendencia, string> = {
  aberta: "border-borda bg-superficie-2 text-texto",
  aguardando: "border-borda bg-superficie-2 text-apoio",
  fechada: "border-ok-borda/40 bg-ok-fundo text-ok",
  reaberta: "border-risco-borda/40 bg-risco-fundo text-risco",
};

export function SeloStatus({ status }: { status: StatusPendencia }) {
  return <span className={cn(BASE_SELO, CORES_STATUS[status])}>{ROTULO_STATUS[status]}</span>;
}

export function SeloEscalado() {
  return <span className={cn(BASE_SELO, CORES_GRAVIDADE.irregular)}>escalado ao coordenador</span>;
}

export function SeloUrgente() {
  return (
    <span className={cn(BASE_SELO, CORES_GRAVIDADE.irregular)} title="Prazo de 1 a 2 dias: trabalhador sem proteção hoje">
      urgente · sem proteção hoje
    </span>
  );
}
