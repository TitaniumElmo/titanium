// REFERÊNCIA — não é parte oficial do site. Trazido do sistema Carvalho & Felinto como inspiração; pode ser usado, adaptado ou descartado.
//
// Janela "Ajustar foto": depois de escolher a imagem, a pessoa arrasta e dá zoom pra decidir o
// que entra no círculo do avatar, como no Instagram. Feito à mão, sem biblioteca de recorte.
//
// Funciona com mouse, toque e teclado:
// - arrastar (um dedo ou o mouse) move a foto;
// - zoom pela barra, pela roda do mouse ou pela pinça com dois dedos;
// - setas movem e +/- dão zoom.
//
// O estado é guardado nas coordenadas da FOTO (o ponto dela que fica no centro + o zoom), não em
// pixels da tela: assim o recorte não depende do tamanho da janela, e a conversão pro tamanho
// exibido acontece só na hora de desenhar.
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { AreaDoRecorte } from "./foto";
import { IconeFechar, IconeMais, IconeMenos } from "./util";

const ZOOM_MAX = 4;
// passo do teclado: 10 px na tela por toque de seta
const PASSO_TECLADO_PX = 10;

type Estado = { zoom: number; x: number; y: number };
type Ponto = { x: number; y: number };

export function AjustarFoto({
  bitmap,
  url,
  salvando,
  onCancelar,
  onSalvar,
}: {
  bitmap: ImageBitmap;
  /** URL local (URL.createObjectURL) do mesmo arquivo do bitmap, só pra exibir */
  url: string;
  salvando: boolean;
  onCancelar: () => void;
  onSalvar: (area: AreaDoRecorte) => void;
}) {
  const largura = bitmap.width;
  const altura = bitmap.height;
  const menorLado = Math.min(largura, altura);

  const quadroRef = useRef<HTMLDivElement>(null);
  // lado do quadro na tela, medido (muda com o tamanho da janela/celular)
  const [ladoTela, setLadoTela] = useState(0);
  const [estado, setEstado] = useState<Estado>({ zoom: 1, x: largura / 2, y: altura / 2 });

  // dedos/mouse apertados no quadro, e o início da pinça (quando há dois)
  const ponteiros = useRef(new Map<number, Ponto>());
  const pinca = useRef<{ distancia: number; zoom: number; pontoNaFoto: Ponto } | null>(null);

  // pixels de tela por pixel da foto: com zoom 1 o menor lado da foto preenche o quadro
  const escala = (zoom: number) => (ladoTela * zoom) / menorLado;

  // a foto sempre cobre o quadro inteiro: o centro não pode chegar perto demais da borda
  function limitar(e: Estado): Estado {
    const zoom = Math.min(ZOOM_MAX, Math.max(1, e.zoom));
    const metade = menorLado / (2 * zoom);
    return {
      zoom,
      x: Math.min(largura - metade, Math.max(metade, e.x)),
      y: Math.min(altura - metade, Math.max(metade, e.y)),
    };
  }

  // zoom mantendo parado o ponto da foto que está embaixo de `alvo` (o cursor, o meio da pinça
  // ou o centro do quadro) — é o que faz o zoom "ir na direção" do dedo/mouse
  function zoomEm(e: Estado, novoZoom: number, alvo: Ponto): Estado {
    const s = escala(e.zoom);
    const pontoNaFoto = {
      x: e.x + (alvo.x - ladoTela / 2) / s,
      y: e.y + (alvo.y - ladoTela / 2) / s,
    };
    const zoom = Math.min(ZOOM_MAX, Math.max(1, novoZoom));
    const s2 = escala(zoom);
    return limitar({
      zoom,
      x: pontoNaFoto.x - (alvo.x - ladoTela / 2) / s2,
      y: pontoNaFoto.y - (alvo.y - ladoTela / 2) / s2,
    });
  }

  function pontoNoQuadro(clientX: number, clientY: number): Ponto {
    const r = quadroRef.current!.getBoundingClientRect();
    return { x: clientX - r.left, y: clientY - r.top };
  }

  useEffect(() => {
    const quadro = quadroRef.current;
    if (!quadro) return;
    const observador = new ResizeObserver(([entrada]) => {
      if (entrada) setLadoTela(entrada.contentRect.width);
    });
    observador.observe(quadro);
    return () => observador.disconnect();
  }, []);

  // roda do mouse: registrada à mão porque o onWheel do React é "passive" e não deixa impedir a
  // rolagem da página por trás
  useEffect(() => {
    const quadro = quadroRef.current;
    if (!quadro || ladoTela === 0) return;
    function aoRolar(evento: WheelEvent) {
      evento.preventDefault();
      const alvo = pontoNoQuadro(evento.clientX, evento.clientY);
      setEstado((e) => zoomEm(e, e.zoom * Math.exp(-evento.deltaY * 0.0015), alvo));
    }
    quadro.addEventListener("wheel", aoRolar, { passive: false });
    return () => quadro.removeEventListener("wheel", aoRolar);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- zoomEm só depende de ladoTela
  }, [ladoTela]);

  useEffect(() => {
    function aoTeclar(evento: globalThis.KeyboardEvent) {
      if (evento.key === "Escape" && !salvando) onCancelar();
    }
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [onCancelar, salvando]);

  function iniciarPinca(e: Estado) {
    const [a, b] = [...ponteiros.current.values()] as [Ponto, Ponto];
    const meio = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    const s = escala(e.zoom);
    pinca.current = {
      distancia: Math.hypot(a.x - b.x, a.y - b.y),
      zoom: e.zoom,
      pontoNaFoto: { x: e.x + (meio.x - ladoTela / 2) / s, y: e.y + (meio.y - ladoTela / 2) / s },
    };
  }

  function aoApertar(evento: PointerEvent<HTMLDivElement>) {
    evento.currentTarget.setPointerCapture(evento.pointerId);
    ponteiros.current.set(evento.pointerId, pontoNoQuadro(evento.clientX, evento.clientY));
    if (ponteiros.current.size === 2) iniciarPinca(estado);
  }

  function aoMover(evento: PointerEvent<HTMLDivElement>) {
    const anterior = ponteiros.current.get(evento.pointerId);
    if (!anterior) return;
    const atual = pontoNoQuadro(evento.clientX, evento.clientY);
    ponteiros.current.set(evento.pointerId, atual);

    if (ponteiros.current.size === 1) {
      // arrastar: a foto acompanha o dedo, então o centro anda no sentido contrário
      setEstado((e) => {
        const s = escala(e.zoom);
        return limitar({
          ...e,
          x: e.x - (atual.x - anterior.x) / s,
          y: e.y - (atual.y - anterior.y) / s,
        });
      });
      return;
    }

    const inicio = pinca.current;
    if (ponteiros.current.size === 2 && inicio) {
      // pinça: o zoom segue a distância entre os dedos, e o ponto da foto que estava entre eles
      // no começo continua entre eles (então dá pra mover e dar zoom ao mesmo tempo)
      const [a, b] = [...ponteiros.current.values()] as [Ponto, Ponto];
      const meio = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const zoom = Math.min(
        ZOOM_MAX,
        Math.max(1, (inicio.zoom * Math.hypot(a.x - b.x, a.y - b.y)) / inicio.distancia),
      );
      const s = escala(zoom);
      setEstado(
        limitar({
          zoom,
          x: inicio.pontoNaFoto.x - (meio.x - ladoTela / 2) / s,
          y: inicio.pontoNaFoto.y - (meio.y - ladoTela / 2) / s,
        }),
      );
    }
  }

  function aoSoltar(evento: PointerEvent<HTMLDivElement>) {
    ponteiros.current.delete(evento.pointerId);
    pinca.current = null;
    // se sobrou um dedo depois da pinça, ele continua arrastando a partir de onde está
  }

  function aoTeclarNoQuadro(evento: KeyboardEvent<HTMLDivElement>) {
    const passo = PASSO_TECLADO_PX / escala(estado.zoom);
    const centro = { x: ladoTela / 2, y: ladoTela / 2 };
    const acoes: Record<string, (e: Estado) => Estado> = {
      ArrowLeft: (e) => limitar({ ...e, x: e.x - passo }),
      ArrowRight: (e) => limitar({ ...e, x: e.x + passo }),
      ArrowUp: (e) => limitar({ ...e, y: e.y - passo }),
      ArrowDown: (e) => limitar({ ...e, y: e.y + passo }),
      "+": (e) => zoomEm(e, e.zoom * 1.1, centro),
      "=": (e) => zoomEm(e, e.zoom * 1.1, centro),
      "-": (e) => zoomEm(e, e.zoom / 1.1, centro),
    };
    const acao = acoes[evento.key];
    if (!acao) return;
    evento.preventDefault();
    setEstado(acao);
  }

  function salvar() {
    const metade = menorLado / (2 * estado.zoom);
    onSalvar({ x: estado.x - metade, y: estado.y - metade, lado: metade * 2 });
  }

  const s = escala(estado.zoom);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
      <button
        aria-label="Fechar"
        className="absolute inset-0"
        onClick={onCancelar}
        disabled={salvando}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="ajustar-foto-titulo"
        className="relative w-full max-w-sm rounded-2xl border border-border bg-card p-5 shadow-xl"
      >
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 id="ajustar-foto-titulo" className="text-lg font-extrabold text-primary">
            Ajustar foto
          </h2>
          <button
            onClick={onCancelar}
            disabled={salvando}
            className="grid size-9 shrink-0 place-items-center rounded-lg border border-border text-primary hover:bg-secondary"
            aria-label="Fechar"
          >
            <IconeFechar className="size-4" />
          </button>
        </div>

        <div
          ref={quadroRef}
          tabIndex={0}
          aria-label="Área da foto. Arraste para mover; use as setas para mover e + ou - para o zoom."
          className="relative aspect-square w-full cursor-grab touch-none select-none overflow-hidden rounded-xl bg-black focus:outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing"
          onPointerDown={aoApertar}
          onPointerMove={aoMover}
          onPointerUp={aoSoltar}
          onPointerCancel={aoSoltar}
          onKeyDown={aoTeclarNoQuadro}
        >
          {ladoTela > 0 && (
            <img
              src={url}
              alt=""
              draggable={false}
              className="pointer-events-none absolute left-0 top-0 max-w-none origin-top-left"
              style={{
                width: largura * s,
                height: altura * s,
                transform: `translate(${ladoTela / 2 - estado.x * s}px, ${ladoTela / 2 - estado.y * s}px)`,
              }}
            />
          )}
          {/* máscara: escurece tudo fora do círculo, que é exatamente o que vira o avatar */}
          <div className="pointer-events-none absolute inset-0 rounded-full shadow-[0_0_0_9999px_rgba(0,0,0,0.55)] ring-2 ring-white/80" />
        </div>

        <div className="mt-4 flex items-center gap-3">
          <IconeMenos className="size-4 shrink-0 text-muted-foreground" />
          <input
            type="range"
            aria-label="Zoom"
            min={1}
            max={ZOOM_MAX}
            step={0.01}
            value={estado.zoom}
            onChange={(ev) => {
              const valor = Number(ev.target.value);
              setEstado((e) => zoomEm(e, valor, { x: ladoTela / 2, y: ladoTela / 2 }));
            }}
            className="h-1.5 w-full cursor-pointer accent-primary"
          />
          <IconeMais className="size-4 shrink-0 text-muted-foreground" />
        </div>

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className="inline-flex h-10 items-center rounded-xl border border-border px-4 text-sm font-semibold text-muted-foreground hover:bg-secondary hover:text-foreground"
            onClick={onCancelar}
            disabled={salvando}
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={salvar}
            disabled={salvando || ladoTela === 0}
            className="inline-flex h-10 items-center rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {salvando ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}
