// REFERÊNCIA — não é parte oficial do site. Trazido do sistema Carvalho & Felinto como inspiração; pode ser usado, adaptado ou descartado.
//
// Avatar redondo: mostra a foto quando há `fotoUrl` e as iniciais do nome quando não há — e
// também enquanto a foto carrega ou se ela falhar (as iniciais ficam por baixo e a foto só
// aparece quando terminou de carregar, sem "piscar" ícone de imagem quebrada).
import { useState } from "react";
import { cn, iniciais } from "./util";

const TAMANHOS = {
  sm: "size-6 text-[10px]",
  md: "size-9 text-xs",
  lg: "size-24 text-2xl",
} as const;

export function Avatar({
  nome,
  fotoUrl,
  tamanho = "md",
  className,
}: {
  nome: string;
  fotoUrl?: string | null;
  tamanho?: keyof typeof TAMANHOS;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 select-none items-center justify-center overflow-hidden rounded-full bg-secondary font-bold text-primary",
        TAMANHOS[tamanho],
        className,
      )}
    >
      {iniciais(nome)}
      {/* key: trocar de foto começa do zero (escondida até carregar a nova) */}
      {fotoUrl && <Foto key={fotoUrl} src={fotoUrl} />}
    </span>
  );
}

function Foto({ src }: { src: string }) {
  const [estado, setEstado] = useState<"carregando" | "ok" | "falhou">("carregando");
  if (estado === "falhou") return null;
  return (
    <img
      src={src}
      alt=""
      onLoad={() => setEstado("ok")}
      onError={() => setEstado("falhou")}
      className={cn(
        "absolute inset-0 size-full object-cover transition-opacity",
        estado === "ok" ? "opacity-100" : "opacity-0",
      )}
    />
  );
}
