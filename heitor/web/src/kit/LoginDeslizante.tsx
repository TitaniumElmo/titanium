// REFERÊNCIA — não é parte oficial do site. Trazido do sistema Carvalho & Felinto como inspiração; pode ser usado, adaptado ou descartado.
//
// Tela em dois painéis que trocam de lado deslizando — o layout do login do Carvalho & Felinto.
// Só o "esqueleto" e o efeito: o conteúdo (formulário, textos, botão de trocar) entra por props.
//
// Telas médias/largas: dois painéis absolutos. O painel das ondas é um pouco mais largo que 50% e
// fica por cima só na faixa de sobreposição, com corte diagonal (clip-path) e sombra — dá a
// sensação de um painel sobre o outro. A transição é na propriedade `left` (e não em transform),
// porque `left` em % é relativo ao container: cada posição sai direto em %, sem conversão. Por
// cima das ondas, um brilho radial segue o mouse e some quando ele sai.
//
// Celular: o painel das ondas vira uma faixa compacta em cima do formulário (`topoCelular`), sem
// deslizar — numa coluna só não faz sentido.
//
// Uso:
//   const [lado, setLado] = useState<"a" | "b">("a");
//   <LoginDeslizante
//     invertido={lado === "b"}
//     chave={lado}
//     cores={["#...", "#...", "#..."]}
//     formulario={lado === "a" ? <FormEntrar /> : <FormRecuperar />}
//     painel={<TextoEBotao onTrocar={() => setLado(lado === "a" ? "b" : "a")} />}
//     topoCelular={<FaixaCompacta ... />}
//   />
import { useState, type MouseEvent, type ReactNode } from "react";
import { CORES_PADRAO, FundoOndas, type CoresDasOndas } from "./FundoOndas";

// Quanto o painel das ondas "invade" o do formulário na borda diagonal
const SOBREPOSICAO_PX = 56;

export function LoginDeslizante({
  invertido,
  chave,
  cores,
  formulario,
  painel,
  topoCelular,
  corDoBrilho = "rgba(255,255,255,0.10)",
}: {
  /** false: formulário à esquerda e ondas à direita; true: troca os lados */
  invertido: boolean;
  /** Muda quando o conteúdo muda — faz a animação de entrada rodar de novo */
  chave: string;
  cores?: CoresDasOndas;
  formulario: ReactNode;
  /** Conteúdo por cima das ondas (logo, texto, botão de trocar) — em texto claro */
  painel: ReactNode;
  /** Faixa em cima do formulário no celular; sem ela, o celular mostra só o formulário */
  topoCelular?: ReactNode;
  corDoBrilho?: string;
}) {
  // posição do mouse dentro do painel das ondas, em %; `ativo` faz o fade do brilho
  const [brilho, setBrilho] = useState({ x: 50, y: 50, ativo: false });
  const c = cores ?? CORES_PADRAO;

  function aoMoverMouse(e: MouseEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    setBrilho({
      x: ((e.clientX - r.left) / r.width) * 100,
      y: ((e.clientY - r.top) / r.height) * 100,
      ativo: true,
    });
  }

  return (
    <>
      {/* Celular: empilhado */}
      <div className="flex min-h-screen flex-col bg-card md:hidden">
        {topoCelular && (
          // gradiente parado (e não as ondas): faixa pequena, e assim só um WebGL roda por vez
          <div
            className="px-5 py-5"
            style={{ background: `linear-gradient(to bottom right, ${c[0]}, ${c[2]})` }}
          >
            <div key={chave} className="kit-entrar">
              {topoCelular}
            </div>
          </div>
        )}
        <div className="flex flex-1 items-center justify-center px-6 py-10">
          <div key={chave} className="kit-entrar w-full max-w-sm">
            {formulario}
          </div>
        </div>
      </div>

      {/* Desktop: lado a lado, deslizando */}
      <div className="relative hidden min-h-screen overflow-hidden bg-card md:block">
        <div
          className="absolute inset-y-0 z-10 flex items-center justify-center px-10 transition-[left] duration-700 ease-in-out motion-reduce:transition-none"
          onMouseMove={aoMoverMouse}
          onMouseLeave={() => setBrilho((b) => ({ ...b, ativo: false }))}
          style={{
            width: `calc(50% + ${SOBREPOSICAO_PX}px)`,
            left: invertido ? "0%" : `calc(50% - ${SOBREPOSICAO_PX}px)`,
            clipPath: invertido
              ? `polygon(0% 0%, 100% 0%, calc(100% - ${SOBREPOSICAO_PX}px) 100%, 0% 100%)`
              : `polygon(${SOBREPOSICAO_PX}px 0%, 100% 0%, 100% 100%, 0% 100%)`,
            filter: "drop-shadow(0 10px 40px rgba(0,0,0,0.35))",
          }}
        >
          <FundoOndas cores={cores} className="absolute inset-0" />
          <div
            className="pointer-events-none absolute inset-0 transition-opacity duration-300"
            style={{
              opacity: brilho.ativo ? 1 : 0,
              background: `radial-gradient(circle 260px at ${brilho.x}% ${brilho.y}%, ${corDoBrilho}, transparent 70%)`,
            }}
          />
          {/* "relative" não é decoração: sem ele este div pinta por baixo das ondas/brilho
              (absolutos), mesmo vindo depois no DOM, e o conteúdo some */}
          <div key={chave} className="kit-entrar kit-entrar-longe relative">
            {painel}
          </div>
        </div>

        <div
          className="absolute inset-y-0 z-0 flex w-1/2 items-center justify-center bg-card px-10 transition-[left] duration-700 ease-in-out motion-reduce:transition-none"
          style={{ left: invertido ? "50%" : "0%" }}
        >
          <div key={chave} className="kit-entrar kit-entrar-longe w-full max-w-sm">
            {formulario}
          </div>
        </div>
      </div>
    </>
  );
}
