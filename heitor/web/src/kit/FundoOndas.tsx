// REFERÊNCIA — não é parte oficial do site. Trazido do sistema Carvalho & Felinto como inspiração; pode ser usado, adaptado ou descartado.
//
// Fundo animado em ondas, em WebGL puro (sem biblioteca). Trazido do login do sistema Carvalho &
// Felinto, onde substituiu o @shadergradient/react (que puxava three.js, ~1 MB, só pra isso).
//
// Como funciona:
// - um plano 10x10 dividido em 192x192, deslocado (x = -1,4) e girado (10° em Y, 50° em Z);
// - cada ponto sobe/desce com ruído de Perlin 3D (Stefan Gustavson, domínio público) que anda
//   com o tempo;
// - a cor é um degradê entre as 3 cores pela posição horizontal e pela ALTURA da onda: cor 1 e 2
//   no fundo, cor 3 aparece nas cristas (o "brilho") — então a cor 3 é a mais clara/viva;
// - câmera a 3,6 de distância olhando de frente, campo de visão de 45°.
//
// Sem WebGL, ou com "reduzir movimento" ligado no sistema, fica um gradiente parado por baixo / um
// quadro só. Uso: <FundoOndas cores={["#escuro", "#medio", "#brilho"]} className="absolute inset-0" />
//
// NÃO ponha `opacity` (nem opacity-xx do Tailwind) nele: em algumas placas (Intel/Direct3D) o
// Chrome pinta o canvas WebGL de BRANCO quando ele fica semitransparente. Pra deixar mais fraco,
// coloque por cima uma camada da cor do fundo com transparência (ex.: bg-black/60).
import { useEffect, useRef } from "react";

export type CoresDasOndas = [string, string, string];

// Cores de exemplo (neutras): troque pelas do site passando a prop `cores`
export const CORES_PADRAO: CoresDasOndas = ["#050505", "#1a1a1a", "#4a4a4a"];
const DIVISOES = 192;
const LADO_PLANO = 10;

const VERTICE = `
attribute vec2 aPosicao;
uniform mat4 uMVP;
uniform float uTempo;
varying vec3 vPos;

vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
vec3 fade(vec3 t) { return t * t * t * (t * (t * 6.0 - 15.0) + 10.0); }

float cnoise(vec3 P) {
  vec3 Pi0 = floor(P);
  vec3 Pi1 = Pi0 + vec3(1.0);
  Pi0 = mod289(Pi0);
  Pi1 = mod289(Pi1);
  vec3 Pf0 = fract(P);
  vec3 Pf1 = Pf0 - vec3(1.0);
  vec4 ix = vec4(Pi0.x, Pi1.x, Pi0.x, Pi1.x);
  vec4 iy = vec4(Pi0.yy, Pi1.yy);
  vec4 iz0 = Pi0.zzzz;
  vec4 iz1 = Pi1.zzzz;
  vec4 ixy = permute(permute(ix) + iy);
  vec4 ixy0 = permute(ixy + iz0);
  vec4 ixy1 = permute(ixy + iz1);
  vec4 gx0 = ixy0 * (1.0 / 7.0);
  vec4 gy0 = fract(floor(gx0) * (1.0 / 7.0)) - 0.5;
  gx0 = fract(gx0);
  vec4 gz0 = vec4(0.5) - abs(gx0) - abs(gy0);
  vec4 sz0 = step(gz0, vec4(0.0));
  gx0 -= sz0 * (step(0.0, gx0) - 0.5);
  gy0 -= sz0 * (step(0.0, gy0) - 0.5);
  vec4 gx1 = ixy1 * (1.0 / 7.0);
  vec4 gy1 = fract(floor(gx1) * (1.0 / 7.0)) - 0.5;
  gx1 = fract(gx1);
  vec4 gz1 = vec4(0.5) - abs(gx1) - abs(gy1);
  vec4 sz1 = step(gz1, vec4(0.0));
  gx1 -= sz1 * (step(0.0, gx1) - 0.5);
  gy1 -= sz1 * (step(0.0, gy1) - 0.5);
  vec3 g000 = vec3(gx0.x, gy0.x, gz0.x);
  vec3 g100 = vec3(gx0.y, gy0.y, gz0.y);
  vec3 g010 = vec3(gx0.z, gy0.z, gz0.z);
  vec3 g110 = vec3(gx0.w, gy0.w, gz0.w);
  vec3 g001 = vec3(gx1.x, gy1.x, gz1.x);
  vec3 g101 = vec3(gx1.y, gy1.y, gz1.y);
  vec3 g011 = vec3(gx1.z, gy1.z, gz1.z);
  vec3 g111 = vec3(gx1.w, gy1.w, gz1.w);
  vec4 norm0 = taylorInvSqrt(vec4(dot(g000, g000), dot(g010, g010), dot(g100, g100), dot(g110, g110)));
  g000 *= norm0.x; g010 *= norm0.y; g100 *= norm0.z; g110 *= norm0.w;
  vec4 norm1 = taylorInvSqrt(vec4(dot(g001, g001), dot(g011, g011), dot(g101, g101), dot(g111, g111)));
  g001 *= norm1.x; g011 *= norm1.y; g101 *= norm1.z; g111 *= norm1.w;
  float n000 = dot(g000, Pf0);
  float n100 = dot(g100, vec3(Pf1.x, Pf0.yz));
  float n010 = dot(g010, vec3(Pf0.x, Pf1.y, Pf0.z));
  float n110 = dot(g110, vec3(Pf1.xy, Pf0.z));
  float n001 = dot(g001, vec3(Pf0.xy, Pf1.z));
  float n101 = dot(g101, vec3(Pf1.x, Pf0.y, Pf1.z));
  float n011 = dot(g011, vec3(Pf0.x, Pf1.yz));
  float n111 = dot(g111, Pf1);
  vec3 fade_xyz = fade(Pf0);
  vec4 n_z = mix(vec4(n000, n100, n010, n110), vec4(n001, n101, n011, n111), fade_xyz.z);
  vec2 n_yz = mix(n_z.xy, n_z.zw, fade_xyz.y);
  float n_xyz = mix(n_yz.x, n_yz.y, fade_xyz.x);
  return 2.2 * n_xyz;
}

void main() {
  vec3 posicao = vec3(aPosicao, 0.0);
  float t = uTempo * 0.2;
  float distorcao = 0.75 * cnoise(0.43 * posicao * 1.3 + t);
  vec3 pos = posicao + vec3(0.0, 0.0, 1.0) * distorcao * 3.6;
  vPos = pos;
  gl_Position = uMVP * vec4(pos, 1.0);
}
`;

const FRAGMENTO = `
precision highp float;
uniform vec3 uCor1;
uniform vec3 uCor2;
uniform vec3 uCor3;
varying vec3 vPos;

void main() {
  vec3 base = mix(mix(uCor1, uCor2, smoothstep(-3.0, 3.0, vPos.x)), uCor3, vPos.z);
  gl_FragColor = vec4(clamp(base * 0.96, 0.0, 1.0), 1.0);
}
`;

// --- matrizes 4x4 (colunas, como o WebGL espera) ----------------------------------------------
type Mat4 = number[];

function multiplicar(a: Mat4, b: Mat4): Mat4 {
  const r = new Array<number>(16).fill(0);
  for (let c = 0; c < 4; c++)
    for (let l = 0; l < 4; l++)
      for (let k = 0; k < 4; k++) r[c * 4 + l]! += a[k * 4 + l]! * b[c * 4 + k]!;
  return r;
}

function perspectiva(fovGraus: number, aspecto: number, perto: number, longe: number): Mat4 {
  const f = 1 / Math.tan((fovGraus * Math.PI) / 360);
  const nf = 1 / (perto - longe);
  return [
    f / aspecto,
    0,
    0,
    0,
    0,
    f,
    0,
    0,
    0,
    0,
    (longe + perto) * nf,
    -1,
    0,
    0,
    2 * longe * perto * nf,
    0,
  ];
}

// câmera em (0, 0, -3,6) olhando pra origem, "pra cima" = +Y (azimute 180°, polar 90°)
function visao(): Mat4 {
  const olho = [0, 0, -3.6];
  const z = [0, 0, -1]; // do alvo pro olho, normalizado
  const x = [-1, 0, 0]; // cima(0,1,0) × z
  const y = [0, 1, 0];
  const pontinho = (v: number[]) => v[0]! * olho[0]! + v[1]! * olho[1]! + v[2]! * olho[2]!;
  return [
    x[0]!,
    y[0]!,
    z[0]!,
    0,
    x[1]!,
    y[1]!,
    z[1]!,
    0,
    x[2]!,
    y[2]!,
    z[2]!,
    0,
    -pontinho(x),
    -pontinho(y),
    -pontinho(z),
    1,
  ];
}

// modelo = deslocar(-1,4, 0, 0) × girar X(0°) × girar Y(10°) × girar Z(50°) (Euler "XYZ" do three.js)
function modelo(): Mat4 {
  const ry = (10 * Math.PI) / 180;
  const rz = (50 * Math.PI) / 180;
  const girarY: Mat4 = [
    Math.cos(ry),
    0,
    -Math.sin(ry),
    0,
    0,
    1,
    0,
    0,
    Math.sin(ry),
    0,
    Math.cos(ry),
    0,
    0,
    0,
    0,
    1,
  ];
  const girarZ: Mat4 = [
    Math.cos(rz),
    Math.sin(rz),
    0,
    0,
    -Math.sin(rz),
    Math.cos(rz),
    0,
    0,
    0,
    0,
    1,
    0,
    0,
    0,
    0,
    1,
  ];
  const deslocar: Mat4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -1.4, 0, 0, 1];
  return multiplicar(deslocar, multiplicar(girarY, girarZ));
}

function malhaDoPlano() {
  const n = DIVISOES + 1;
  const vertices = new Float32Array(n * n * 2);
  for (let i = 0; i < n; i++)
    for (let j = 0; j < n; j++) {
      vertices[(i * n + j) * 2] = (j / DIVISOES - 0.5) * LADO_PLANO;
      vertices[(i * n + j) * 2 + 1] = (0.5 - i / DIVISOES) * LADO_PLANO;
    }
  const indices = new Uint16Array(DIVISOES * DIVISOES * 6);
  let k = 0;
  for (let i = 0; i < DIVISOES; i++)
    for (let j = 0; j < DIVISOES; j++) {
      const a = i * n + j;
      const b = a + n;
      indices.set([a, b, a + 1, b, b + 1, a + 1], k);
      k += 6;
    }
  return { vertices, indices };
}

function hexParaRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255) as [number, number, number];
}

function compilar(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
  tipo: number,
  codigo: string,
) {
  const shader = gl.createShader(tipo);
  if (!shader) return null;
  gl.shaderSource(shader, codigo);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.warn("[FundoOndas] shader não compilou:", gl.getShaderInfoLog(shader));
    return null;
  }
  return shader;
}

export function FundoOndas({
  className,
  cores = CORES_PADRAO,
}: {
  className?: string;
  /** [fundo, meio, brilho das cristas], em hex "#rrggbb" */
  cores?: CoresDasOndas;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    // Canvas OPACO (alpha: false): com canvas transparente, o Chrome com placa Intel no Direct3D
    // mostrava o painel BRANCO — o desenho saía certo, mas a mistura com sombra/recorte falhava. WebGL2 primeiro (o mesmo que o three.js usava), WebGL1 de reserva; o
    // shader (GLSL ES 1.0) roda igual nos dois
    const opcoes: WebGLContextAttributes = { antialias: true, alpha: false };
    const gl: WebGLRenderingContext | WebGL2RenderingContext | null = !canvas
      ? null
      : (canvas.getContext("webgl2", opcoes) ?? canvas.getContext("webgl", opcoes));
    if (!canvas || !gl) return; // sem WebGL: fica o gradiente parado que está por baixo

    const vertice = compilar(gl, gl.VERTEX_SHADER, VERTICE);
    const fragmento = compilar(gl, gl.FRAGMENT_SHADER, FRAGMENTO);
    const programa = gl.createProgram();
    if (!vertice || !fragmento || !programa) return;
    gl.attachShader(programa, vertice);
    gl.attachShader(programa, fragmento);
    gl.linkProgram(programa);
    if (!gl.getProgramParameter(programa, gl.LINK_STATUS)) return;
    gl.useProgram(programa);

    const { vertices, indices } = malhaDoPlano();
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, indices, gl.STATIC_DRAW);
    const aPosicao = gl.getAttribLocation(programa, "aPosicao");
    gl.enableVertexAttribArray(aPosicao);
    gl.vertexAttribPointer(aPosicao, 2, gl.FLOAT, false, 0, 0);

    cores.forEach((cor, i) =>
      gl.uniform3fv(gl.getUniformLocation(programa, `uCor${i + 1}`), hexParaRgb(cor)),
    );
    const uMVP = gl.getUniformLocation(programa, "uMVP");
    const uTempo = gl.getUniformLocation(programa, "uTempo");
    // as dobras da superfície se encobrem: o teste de profundidade é que desenha a borda da dobra
    gl.enable(gl.DEPTH_TEST);
    // onde a onda não cobre: preto, a mesma cor do canto do gradiente de reserva
    gl.clearColor(0, 0, 0, 1);

    const visaoModelo = multiplicar(visao(), modelo());
    const semMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const parado = semMovimento;
    const inicio = performance.now();
    let quadro = 0;
    const desenhar = (agora: number) => {
      gl.uniform1f(uTempo, (agora - inicio) / 1000);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.drawElements(gl.TRIANGLES, indices.length, gl.UNSIGNED_SHORT, 0);
      if (!parado) quadro = requestAnimationFrame(desenhar);
    };

    // resolução 1:1 com a tela, como o original (pixelDensity 1)
    const ajustarTamanho = () => {
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
      gl.viewport(0, 0, canvas.width, canvas.height);
      const projecao = perspectiva(45, canvas.width / Math.max(1, canvas.height), 0.1, 1000);
      gl.uniformMatrix4fv(uMVP, false, multiplicar(projecao, visaoModelo));
      // mudar o tamanho do canvas apaga o desenho: parado, precisa redesenhar o quadro
      if (parado) desenhar(performance.now());
    };
    ajustarTamanho();
    const observador = new ResizeObserver(ajustarTamanho);
    observador.observe(canvas);
    if (!parado) quadro = requestAnimationFrame(desenhar);

    // o navegador pode cortar o WebGL (memória, muitas abas, troca de placa de vídeo): aí para de
    // desenhar e o canvas fica transparente, mostrando o gradiente de reserva que está por baixo
    const aoPerderContexto = (evento: Event) => {
      evento.preventDefault();
      cancelAnimationFrame(quadro);
    };
    canvas.addEventListener("webglcontextlost", aoPerderContexto);

    return () => {
      canvas.removeEventListener("webglcontextlost", aoPerderContexto);
      cancelAnimationFrame(quadro);
      observador.disconnect();
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
    // as cores entram como texto pra não reiniciar o WebGL a cada render (array novo a cada vez)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cores.join()]);

  return (
    <div className={className}>
      {/* por baixo o tempo todo: aparece antes do primeiro quadro e se o WebGL faltar. Estilo
          direto (e não classe do Tailwind) pra o painel nunca ficar transparente */}
      <div
        className="absolute inset-0"
        style={{ background: `linear-gradient(to bottom right, ${cores[0]}, ${cores[2]})` }}
      />
      <canvas ref={canvasRef} aria-hidden className="absolute inset-0 size-full" />
    </div>
  );
}
