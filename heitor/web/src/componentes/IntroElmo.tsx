import { useEffect, useRef, useState } from "react";
import { COLUNAS, gradeCapacete, LINHAS, type Tom } from "../capacete";
import { NOME_AGENTE, SUBTITULO } from "../marca";
import { cn } from "../util";

const DURACAO_MS = 4500;
const SAIDA_MS = 450;
const RITMO = 1.6;
const PROFUNDIDADE = 0.5;

type Bloco = {
  ix: number;
  iy: number;
  iz: number;
  fx: number;
  fy: number;
  fz: number;
  atraso: number;
  tom: Tom;
  fundo: boolean;
  giro: number;
};

function aleatorio(semente: number) {
  let s = semente >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const LADO = 2 / COLUNAS;

function gerarBlocos(): Bloco[] {
  const r = aleatorio(42);
  const blocos: Bloco[] = [];
  for (const p of gradeCapacete()) {
    const x = (p.coluna - (COLUNAS - 1) / 2) * LADO;
    const y = (p.linha - (LINHAS - 1) / 2) * LADO;
    const curvatura = Math.sqrt(Math.max(0, 1 - (x / 1.02) ** 2));
    const frente = p.tom === "aba" ? PROFUNDIDADE * 1.15 * curvatura : PROFUNDIDADE * curvatura;
    for (const fundo of [false, true]) {
      const theta = r() * Math.PI * 2;
      const phi = Math.acos(2 * r() - 1);
      const raio = 1.8 + r() * 1.2;
      blocos.push({
        ix: raio * Math.sin(phi) * Math.cos(theta),
        iy: raio * Math.cos(phi) * 0.75,
        iz: raio * Math.sin(phi) * Math.sin(theta),
        fx: x,
        fy: y,
        fz: fundo ? -frente : frente,
        atraso: (p.linha / LINHAS) * 520 + r() * 260,
        tom: p.tom,
        fundo,
        giro: (r() - 0.5) * Math.PI,
      });
    }
  }
  return blocos;
}

function suave(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function mola(t: number): number {
  if (t >= 1) return 1;
  return 1 - Math.exp(-6 * t) * Math.cos(7.5 * t) * (1 - t);
}

function limitar(v: number): number {
  return Math.min(1, Math.max(0, v));
}

function lerCor(nome: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${nome}`).trim();
}

function brilho(cor: string): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = 64;
  c.height = 64;
  const ctx = c.getContext("2d");
  if (ctx) {
    const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, cor);
    g.addColorStop(1, "transparent");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 64, 64);
  }
  return c;
}

export function IntroElmo({ aoTerminar }: { aoTerminar: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [textoVisivel, setTextoVisivel] = useState(false);
  const [saindo, setSaindo] = useState(false);
  const terminou = useRef(false);

  const sair = () => {
    if (terminou.current) return;
    terminou.current = true;
    setSaindo(true);
    window.setTimeout(aoTerminar, SAIDA_MS);
  };
  const sairRef = useRef(sair);
  sairRef.current = sair;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) {
      sairRef.current();
      return;
    }
    const blocos = gerarBlocos();
    const cores: Record<Tom, string> = {
      base: lerCor("acento"),
      crista: lerCor("acento-forte"),
      aba: lerCor("intro-sombra"),
      luz: lerCor("intro-luz"),
    };
    const corVarredura = lerCor("intro-brilho");
    const halo = brilho(lerCor("intro-onda-1"));
    const semMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let dpr = 1;

    const ajustar = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(canvas.clientWidth * dpr);
      canvas.height = Math.round(canvas.clientHeight * dpr);
    };
    ajustar();
    window.addEventListener("resize", ajustar);

    const projetados = blocos.map(() => ({ x: 0, y: 0, z: 0, lado: 0, alfa: 0, realce: 0 }));
    const ordem = blocos.map((_, i) => i);

    const desenhar = (T: number) => {
      const L = canvas.width;
      const A = canvas.height;
      ctx.clearRect(0, 0, L, A);
      const escala = Math.min(L * 0.36, A * 0.42);
      const cx = L / 2;
      const cy = A * 0.43;

      let rotY = 0;
      if (T < 500) rotY = -0.5;
      else if (T < 2400) rotY = -0.5 + 0.95 * suave((T - 500) / 1900);
      else if (T < 3000) rotY = 0.45 * (1 - suave((T - 2400) / 600));
      const rotX = T < 3000 ? -0.22 * (1 - suave(limitar((T - 2400) / 600))) : 0;
      const cosY = Math.cos(rotY);
      const sinY = Math.sin(rotY);
      const cosX = Math.cos(rotX);
      const sinX = Math.sin(rotX);
      const varredura = T > 2700 && T < 3500 ? -1.2 + 2.4 * ((T - 2700) / 800) : null;
      const distancia = 3.6;

      const formado = limitar((T - 1600) / 900);
      if (formado > 0) {
        ctx.globalAlpha = 0.55 * formado;
        const r = escala * 1.5;
        ctx.drawImage(halo, cx - r, cy - r * 0.8, r * 2, r * 1.6);
        ctx.globalAlpha = 1;
      }

      for (let i = 0; i < blocos.length; i++) {
        const b = blocos[i] as Bloco;
        const t = limitar((T - 350 - b.atraso) / 1300);
        const e = mola(t);
        const x = b.ix + (b.fx - b.ix) * e;
        const y = b.iy + (b.fy - b.iy) * e;
        const z = b.iz + (b.fz - b.iz) * e;
        const xr = x * cosY + z * sinY;
        const zr = -x * sinY + z * cosY;
        const yr = y * cosX - zr * sinX;
        const zf = y * sinX + zr * cosX;
        const s = distancia / (distancia - zf);
        const alvo = projetados[i] as (typeof projetados)[number];
        alvo.x = cx + xr * s * escala;
        alvo.y = cy - yr * s * escala;
        alvo.z = zf;
        alvo.lado = LADO * s * escala * (0.35 + 0.57 * limitar(t * 1.4));
        alvo.alfa = (0.25 + 0.75 * limitar(t * 1.6)) * (b.fundo ? 0.5 : 1);
        alvo.realce = varredura !== null && !b.fundo ? limitar(1 - Math.abs(b.fx - varredura) / 0.12) : 0;
      }

      ordem.sort((a, b) => (projetados[a]?.z ?? 0) - (projetados[b]?.z ?? 0));
      for (const i of ordem) {
        const b = blocos[i] as Bloco;
        const p = projetados[i] as (typeof projetados)[number];
        const lado = Math.max(1, p.lado);
        const px = Math.round(p.x - lado / 2);
        const py = Math.round(p.y - lado / 2);
        ctx.globalAlpha = p.alfa;
        ctx.fillStyle = cores[b.tom];
        ctx.fillRect(px, py, Math.ceil(lado), Math.ceil(lado));
        if (p.realce > 0) {
          ctx.globalAlpha = p.realce * 0.55;
          ctx.fillStyle = corVarredura;
          ctx.fillRect(px, py, Math.ceil(lado), Math.ceil(lado));
        }
      }
      ctx.globalAlpha = 1;
    };

    if (semMovimento) {
      desenhar(DURACAO_MS);
      setTextoVisivel(true);
      const id = window.setTimeout(() => sairRef.current(), 1000);
      return () => {
        window.clearTimeout(id);
        window.removeEventListener("resize", ajustar);
      };
    }

    const inicio = performance.now();
    let quadro = 0;
    const passo = (agora: number) => {
      const T = (agora - inicio) / RITMO;
      desenhar(T);
      if (T > 3000) setTextoVisivel(true);
      if (T >= DURACAO_MS) {
        sairRef.current();
        return;
      }
      quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => {
      cancelAnimationFrame(quadro);
      window.removeEventListener("resize", ajustar);
    };
  }, []);

  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === "Enter" || e.key === " ") sairRef.current();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, []);

  return (
    <div
      role="dialog"
      aria-label="Abertura do Elmo"
      className={cn(
        "fixed inset-0 z-[100] overflow-hidden bg-intro-fundo transition-opacity",
        saindo ? "pointer-events-none opacity-0" : "opacity-100",
      )}
      style={{ transitionDuration: `${SAIDA_MS}ms` }}
    >
      <div className="intro-ondas" aria-hidden />
      <div className="intro-ondas-2" aria-hidden />
      <canvas ref={canvasRef} aria-hidden className="absolute inset-0 size-full" style={{ imageRendering: "pixelated" }} />
      <div
        className={cn(
          "absolute inset-x-0 flex flex-col items-center gap-2 transition-all duration-700",
          textoVisivel ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
        )}
        style={{ top: "calc(43% + min(22vw, 27vh) + 2.25rem)" }}
      >
        <span className="marca text-4xl text-intro-texto">{NOME_AGENTE}</span>
        <span className="text-caption font-medium tracking-sobrescrito text-intro-texto/60">{SUBTITULO}</span>
      </div>
      <button
        type="button"
        onClick={sair}
        className="absolute bottom-6 right-6 rounded-controle border border-intro-texto/15 px-3 py-1.5 text-xs font-medium text-intro-texto/70 transition-colors hover:border-intro-texto/40 hover:text-intro-texto"
      >
        Pular
      </button>
    </div>
  );
}
