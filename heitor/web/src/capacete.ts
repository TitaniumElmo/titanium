export type Tom = "base" | "crista" | "aba" | "luz";

export type Pixel = { coluna: number; linha: number; tom: Tom };

export const COLUNAS = 44;
export const LINHAS = 25;

const CENTRO = (COLUNAS - 1) / 2;
const BASE_CUPULA = 3;
const RAIO_X = 18.5;
const RAIO_Y = 19;
const MEIA_CRISTA = 4.5;
const TOPO_CRISTA = 23;

function naCupula(dx: number, linha: number): boolean {
  if (linha < BASE_CUPULA) return false;
  const y = linha - BASE_CUPULA + 0.5;
  return (dx / RAIO_X) ** 2 + (y / RAIO_Y) ** 2 <= 1;
}

function meiaLarguraCrista(linha: number): number {
  return MEIA_CRISTA + Math.max(0, (linha - 11) * 0.3);
}

function naCrista(dx: number, linha: number): boolean {
  if (linha < BASE_CUPULA || linha > TOPO_CRISTA) return false;
  const meia = meiaLarguraCrista(Math.min(linha, 21));
  if (Math.abs(dx) > meia) return false;
  return !(linha === TOPO_CRISTA && Math.abs(dx) > meia - 1);
}

function naFenda(dx: number, linha: number): boolean {
  if (linha < 11) return false;
  return Math.abs(Math.abs(dx) - (meiaLarguraCrista(linha) + 1)) < 0.6;
}

function valorElipse(dx: number, linha: number): number {
  const y = linha - BASE_CUPULA + 0.5;
  return (dx / RAIO_X) ** 2 + (y / RAIO_Y) ** 2;
}

function naAba(dx: number, linha: number): boolean {
  if (linha <= 1) return Math.abs(dx) <= CENTRO;
  if (linha === 2) return Math.abs(dx) <= CENTRO - 0.5;
  if (linha === 3) return Math.abs(dx) >= CENTRO - 2 && Math.abs(dx) <= CENTRO;
  return false;
}

export function gradeCapacete(): Pixel[] {
  const pixels: Pixel[] = [];
  for (let linha = 0; linha < LINHAS; linha++) {
    for (let coluna = 0; coluna < COLUNAS; coluna++) {
      const dx = coluna - CENTRO;
      const crista = naCrista(dx, linha);
      const cupula = naCupula(dx, linha) && !naFenda(dx, linha);
      const aba = naAba(dx, linha);
      if (!crista && !cupula && !aba) continue;
      let tom: Tom = "base";
      if (aba && !crista && !cupula) tom = "aba";
      else if (crista) tom = dx > -3.5 && dx < -1.5 && linha > 6 && linha < 21 ? "luz" : "crista";
      else if (dx < -4 && linha > 9) {
        const e = valorElipse(dx, linha);
        if (e > 0.62 && e < 0.8) tom = "luz";
      }
      pixels.push({ coluna, linha, tom });
    }
  }
  return pixels;
}
