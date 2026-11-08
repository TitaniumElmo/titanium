import { useState } from "react";
import { cn, iniciais } from "../util";

const TAMANHOS = {
  sm: "size-7 text-xs",
  md: "size-9 text-xs",
  lg: "size-14 text-lg",
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
        "relative inline-flex shrink-0 select-none items-center justify-center overflow-hidden rounded-full border border-borda bg-superficie-2 font-semibold text-apoio",
        TAMANHOS[tamanho],
        className,
      )}
    >
      {iniciais(nome)}
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
      className={cn("absolute inset-0 size-full object-cover transition-opacity", estado === "ok" ? "opacity-100" : "opacity-0")}
    />
  );
}
