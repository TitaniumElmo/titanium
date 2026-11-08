import type { ReactNode } from "react";
import { larguraTexto, TextoPixel } from "./TextoPixel";

export type Cabine = "A" | "B" | "C" | "F" | "D" | "E";

export const LARGURA_CABINE = 80;
const MARGEM = 3;
const TOPO_CENA = 4;
const BASE_CENA = 143;
const COR_LARANJA = "#ff8a1e";
const COR_MADEIRA = "#c9a26b";
const COR_CONTORNO_MADEIRA = "#5a3418";
const COR_SINAL = "#ffd21e";

export const CABINES: { id: Cabine; x: number; nome: string; numero?: string }[] = [
  { id: "A", x: 60, nome: "A PLANILHA", numero: "1" },
  { id: "B", x: 140, nome: "B AUDITORIA", numero: "1·6" },
  { id: "C", x: 220, nome: "C FICHA PAPEL" },
  { id: "F", x: 300, nome: "F RH", numero: "2" },
  { id: "D", x: 380, nome: "D TECNICO", numero: "3·7" },
  { id: "E", x: 460, nome: "E CANTEIRO", numero: "4·5" },
];

const NUMERO_X: Record<Cabine, number> = { A: 107, B: 178, C: 260, F: 370, D: 433, E: 490 };

type Decoracao = { faixa: string; piso: string } | null;

const DECORACAO: Record<Cabine, Decoracao> = {
  A: { faixa: "#2e5e5a", piso: "azulejo" },
  B: { faixa: "#2c4a66", piso: "cinza" },
  C: { faixa: "#6b5a2a", piso: "madeira" },
  F: { faixa: "#5a2e3a", piso: "carpete" },
  D: { faixa: "#2f4f3a", piso: "cimento" },
  E: null,
};

const ICONES: Record<Cabine, string[]> = {
  A: ["#######", "#.#.#.#", "#######", "#.#.#.#", "#######", "#.#.#.#", "#######"],
  B: [".###...", "#...#..", "#...#..", "#...#..", ".###...", "....#..", ".....#."],
  C: ["....##.", "...###.", "..###..", ".###...", "##.....", ".......", "#######"],
  F: ["###....", "#######", "#.....#", "#.....#", "#.....#", "#.....#", "#######"],
  D: ["....#..", "....#..", ".#####.", ".#...#.", ".#.#.#.", ".#...#.", ".#####."],
  E: ["..###..", ".#####.", "#######", "#######", "#######", "#######", "......."],
};

const PISO_TOPO = 125;
const PISO_ALTURA = 15;
const FAIXA_TOPO = 64;
const FAIXA_BASE = 124;

function IconePixel({ cabine, x, y, cor }: { cabine: Cabine; x: number; y: number; cor: string }) {
  const caminho = ICONES[cabine]
    .map((linha, ly) =>
      linha
        .split("")
        .map((px, lx) => (px === "#" ? `M${lx} ${ly}h1v1h-1z` : ""))
        .join(""),
    )
    .join("");
  return (
    <svg
      aria-hidden
      viewBox="0 0 7 7"
      width={7}
      height={7}
      shapeRendering="crispEdges"
      style={{ position: "absolute", left: x, top: y, zIndex: 7 }}
    >
      <path d={caminho} fill={cor} />
    </svg>
  );
}

function Pisos() {
  return (
    <defs>
      <pattern id="piso-azulejo" width="8" height="8" patternUnits="userSpaceOnUse">
        <rect width="8" height="8" fill="#b4b5b9" />
        <rect width="8" height="1" fill="#8f9096" />
        <rect width="1" height="8" fill="#8f9096" />
        <rect x="3" y="3" width="1" height="1" fill="#c6c7cb" />
      </pattern>
      <pattern id="piso-cinza" width="8" height="8" patternUnits="userSpaceOnUse">
        <rect width="8" height="8" fill="#cfd0d3" />
        <rect x="2" y="5" width="1" height="1" fill="#bdbec2" />
        <rect x="6" y="1" width="1" height="1" fill="#dcdde0" />
      </pattern>
      <pattern id="piso-madeira" width="24" height="10" patternUnits="userSpaceOnUse">
        <rect width="24" height="10" fill="#b5834c" />
        <rect y="4" width="24" height="1" fill="#8e6137" />
        <rect y="9" width="24" height="1" fill="#8e6137" />
        <rect x="0" y="0" width="1" height="4" fill="#8e6137" />
        <rect x="12" y="5" width="1" height="4" fill="#8e6137" />
        <rect x="6" y="2" width="3" height="1" fill="#c4935c" />
      </pattern>
      <pattern id="piso-carpete" width="4" height="4" patternUnits="userSpaceOnUse">
        <rect width="4" height="4" fill="#7b4455" />
        <rect x="1" y="1" width="1" height="1" fill="#6a3949" />
        <rect x="3" y="3" width="1" height="1" fill="#8a5365" />
      </pattern>
      <pattern id="piso-cimento" width="6" height="6" patternUnits="userSpaceOnUse">
        <rect width="6" height="6" fill="#9b9992" />
        <rect x="1" y="2" width="1" height="1" fill="#8b8982" />
        <rect x="4" y="4" width="1" height="1" fill="#aba9a2" />
      </pattern>
    </defs>
  );
}

export function FundoCabines() {
  const itens: ReactNode[] = [];
  for (const c of CABINES) {
    const d = DECORACAO[c.id];
    if (!d) continue;
    const x = c.x + MARGEM;
    const largura = LARGURA_CABINE - MARGEM * 2;
    itens.push(
      <g key={c.id}>
        <rect x={x} y={FAIXA_TOPO} width={largura} height={FAIXA_BASE - FAIXA_TOPO} fill={d.faixa} />
        <rect x={x} y={FAIXA_TOPO} width={largura} height={1} fill="#ffffff" fillOpacity={0.18} />
        <rect x={x} y={PISO_TOPO} width={largura} height={PISO_ALTURA} fill={`url(#piso-${d.piso})`} />
      </g>,
    );
  }
  return (
    <svg
      aria-hidden
      width={540}
      height={180}
      shapeRendering="crispEdges"
      style={{ position: "absolute", left: 0, top: 0, zIndex: 1, pointerEvents: "none" }}
    >
      <Pisos />
      {itens}
    </svg>
  );
}

export function NumeroDoChao({ cabine }: { cabine: Cabine }) {
  const c = CABINES.find((i) => i.id === cabine);
  if (!c?.numero) return null;
  const largura = larguraTexto(c.numero) * 2;
  return <TextoPixel texto={c.numero} x={NUMERO_X[cabine] - Math.floor(largura / 2)} y={128} cor={COR_SINAL} escala={2} z={1} />;
}

export function Divisorias() {
  const itens = CABINES.map((c) => {
    const b = c.x;
    return (
      <g key={c.id}>
        <rect x={b - 2} y={TOPO_CENA} width={4} height={96} fill={COR_CONTORNO_MADEIRA} />
        <rect x={b - 1} y={TOPO_CENA} width={2} height={96} fill={COR_MADEIRA} />
        <rect x={b - 3} y={98} width={6} height={BASE_CENA - 98 - 2} fill={COR_CONTORNO_MADEIRA} />
        <rect x={b - 2} y={99} width={4} height={BASE_CENA - 98 - 4} fill={COR_MADEIRA} />
        <rect x={b - 2} y={99} width={1} height={BASE_CENA - 98 - 4} fill="#ffffff" fillOpacity={0.25} />
      </g>
    );
  });
  return (
    <svg
      aria-hidden
      width={540}
      height={180}
      shapeRendering="crispEdges"
      style={{ position: "absolute", left: 0, top: 0, zIndex: 3, pointerEvents: "none" }}
    >
      {itens}
    </svg>
  );
}

export function Escurecimento({ ativa, rodando }: { ativa: Cabine | null; rodando: boolean }) {
  const destaque = rodando ? ativa : null;
  return (
    <>
      {CABINES.map((c) => {
        const brilho = destaque ? (c.id === destaque ? 1 : 0.55) : 0.85;
        return (
          <div
            key={c.id}
            aria-hidden
            className="pointer-events-none absolute bg-black transition-opacity duration-300"
            style={{
              left: c.x + MARGEM,
              top: TOPO_CENA,
              width: LARGURA_CABINE - MARGEM * 2,
              height: BASE_CENA - TOPO_CENA,
              opacity: 1 - brilho,
              zIndex: 4,
            }}
          />
        );
      })}
    </>
  );
}

export function ContornoAtivo({ ativa, rodando }: { ativa: Cabine | null; rodando: boolean }) {
  const c = rodando ? CABINES.find((i) => i.id === ativa) : undefined;
  if (!c) return null;
  return (
    <div
      aria-hidden
      className="animar-contorno pointer-events-none absolute"
      style={{
        left: c.x + MARGEM,
        top: TOPO_CENA,
        width: LARGURA_CABINE - MARGEM * 2,
        height: BASE_CENA - TOPO_CENA,
        boxShadow: `inset 0 0 0 1px ${COR_LARANJA}, inset 0 0 4px ${COR_LARANJA}`,
        zIndex: 7,
      }}
    />
  );
}

const TOPO_PLACA = 12;
const LARGURA_PLACA = 72;

export function Correntes({ cabine }: { cabine: Cabine }) {
  const c = CABINES.find((i) => i.id === cabine);
  if (!c) return null;
  const esquerda = c.x + 4 + 7;
  const direita = c.x + 4 + LARGURA_PLACA - 8;
  const elos: ReactNode[] = [];
  for (let y = TOPO_CENA; y < TOPO_PLACA; y++) {
    const cor = y % 2 === 0 ? "#9a9a9a" : "#5c5c5c";
    elos.push(<rect key={`e${y}`} x={esquerda} y={y} width={1} height={1} fill={cor} />);
    elos.push(<rect key={`d${y}`} x={direita} y={y} width={1} height={1} fill={cor} />);
  }
  return (
    <svg
      aria-hidden
      width={540}
      height={20}
      shapeRendering="crispEdges"
      style={{ position: "absolute", left: 0, top: 0, zIndex: 6, pointerEvents: "none" }}
    >
      {elos}
    </svg>
  );
}

export function PlacaCabine({ cabine, acesa, imagem }: { cabine: Cabine; acesa: boolean; imagem: string }) {
  const c = CABINES.find((i) => i.id === cabine);
  if (!c) return null;
  const cor = acesa ? "var(--cena-placa-acesa)" : "var(--cena-placa-apagada)";
  const largura = larguraTexto(c.nome);
  const total = 7 + 3 + largura;
  const inicio = c.x + 4 + Math.floor((LARGURA_PLACA - total) / 2);
  return (
    <>
      <Correntes cabine={cabine} />
      <img
        src={imagem}
        alt=""
        draggable={false}
        className="pointer-events-none absolute select-none"
        style={{ left: c.x + 4, top: TOPO_PLACA, zIndex: 6, imageRendering: "pixelated" }}
      />
      <IconePixel cabine={cabine} x={inicio} y={TOPO_PLACA + 4} cor={cor} />
      <TextoPixel texto={c.nome} x={inicio + 10} y={TOPO_PLACA + 5} cor={cor} />
    </>
  );
}
