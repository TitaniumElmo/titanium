// REFERÊNCIA — não é parte oficial do site. Trazido do sistema Carvalho & Felinto como inspiração; pode ser usado, adaptado ou descartado.
//
// Prepara a foto de perfil no navegador antes do upload: carrega o arquivo, recorta o quadrado
// que a pessoa escolheu na janela de ajuste (AjustarFoto.tsx) e desenha em LADO_PX x LADO_PX num
// canvas, saindo como JPEG. Assim o backend não precisa de biblioteca de imagem: só confere que
// chegou um JPEG desse tamanho. JPEG e não WEBP porque todo navegador gera JPEG pelo canvas; WEBP
// falha em Safari antigo.

// Se o backend validar o tamanho, use o mesmo valor lá
export const LADO_PX = 256;

export class FotoIlegivel extends Error {}

// Navegadores com proteção forte contra rastreamento (Tor, Brave no modo estrito, Firefox com
// privacy.resistFingerprinting) deixam o canvas "funcionar" mas devolvem uma imagem falsa, em
// geral toda branca — sem essa checagem a foto branca seria salva sem ninguém perceber
export class CanvasBloqueado extends Error {}

// Diferença máxima por canal pra ainda contar como "a mesma cor": o Brave no modo padrão soma um
// ruído de ±1–2 nos pixels, que não pode fazer uma imagem em branco parecer foto de verdade
const TOLERANCIA_COR = 8;

// lado da miniatura usada só pra checar o bloqueio — pequena porque basta ver se há variação
const LADO_CHECAGEM_PX = 64;

// Foto inteira de uma cor só = canvas bloqueado. Uma foto de verdade nunca é assim; o único caso
// legítimo seria alguém mandar de propósito um quadrado liso, o que não faz sentido num avatar.
// Olha a foto INTEIRA (e não o recorte): com o ajuste, recortar só um pedaço liso (uma parede,
// o céu) é normal e não pode ser confundido com bloqueio
function fotoLisa(bitmap: ImageBitmap): boolean {
  const canvas = document.createElement("canvas");
  canvas.width = LADO_CHECAGEM_PX;
  canvas.height = LADO_CHECAGEM_PX;
  const ctx = canvas.getContext("2d");
  if (!ctx) return false;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, LADO_CHECAGEM_PX, LADO_CHECAGEM_PX);
  ctx.drawImage(bitmap, 0, 0, LADO_CHECAGEM_PX, LADO_CHECAGEM_PX);
  const { data } = ctx.getImageData(0, 0, LADO_CHECAGEM_PX, LADO_CHECAGEM_PX);
  const [r, g, b] = [data[0]!, data[1]!, data[2]!];
  for (let i = 4; i < data.length; i += 4) {
    if (
      Math.abs(data[i]! - r) > TOLERANCIA_COR ||
      Math.abs(data[i + 1]! - g) > TOLERANCIA_COR ||
      Math.abs(data[i + 2]! - b) > TOLERANCIA_COR
    ) {
      return false;
    }
  }
  return true;
}

// Checa o bloqueio já ao carregar, antes de abrir a janela de ajuste: se o navegador bloqueia o
// canvas, a pessoa fica sabendo antes de perder tempo enquadrando a foto
export async function carregarFoto(arquivo: File): Promise<ImageBitmap> {
  let bitmap: ImageBitmap;
  try {
    // os navegadores atuais já aplicam a rotação do EXIF (foto de celular "deitada") aqui
    bitmap = await createImageBitmap(arquivo);
  } catch {
    throw new FotoIlegivel();
  }
  if (fotoLisa(bitmap)) {
    bitmap.close();
    throw new CanvasBloqueado();
  }
  return bitmap;
}

/** Quadrado da foto original (em pixels dela) que vira o avatar. */
export type AreaDoRecorte = { x: number; y: number; lado: number };

export async function recortarFoto(bitmap: ImageBitmap, area: AreaDoRecorte): Promise<File> {
  const canvas = document.createElement("canvas");
  canvas.width = LADO_PX;
  canvas.height = LADO_PX;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new FotoIlegivel();

  // JPEG não tem transparência: sem esse fundo, a parte transparente de um PNG viraria preto
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, LADO_PX, LADO_PX);
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bitmap, area.x, area.y, area.lado, area.lado, 0, 0, LADO_PX, LADO_PX);

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", 0.85),
  );
  if (!blob) throw new FotoIlegivel();
  return new File([blob], "foto.jpg", { type: "image/jpeg" });
}
