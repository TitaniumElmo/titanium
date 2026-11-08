import type { ButtonHTMLAttributes, ComponentType, ReactNode, SVGProps } from "react";
import { Link } from "react-router-dom";
import { cn } from "../util";

export function Cartao({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cn("rounded-cartao border border-borda bg-superficie p-5", className)}>{children}</section>;
}

type VarianteBotao = "primario" | "secundario" | "fantasma";

const CLASSES_BOTAO: Record<VarianteBotao, string> = {
  primario: "bg-acento text-sobre-acento hover:bg-acento-forte",
  secundario: "border border-borda bg-superficie-2 text-texto hover:border-fraco",
  fantasma: "text-apoio hover:bg-superficie-2 hover:text-texto",
};

const BASE_BOTAO =
  "inline-flex items-center justify-center gap-2 rounded-controle px-3.5 h-9 text-sm font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none";

export function Botao({
  variante = "secundario",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: VarianteBotao }) {
  return <button type="button" className={cn(BASE_BOTAO, CLASSES_BOTAO[variante], className)} {...props} />;
}

export function BotaoLink({
  para,
  variante = "secundario",
  className,
  children,
}: {
  para: string;
  variante?: VarianteBotao;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Link to={para} className={cn(BASE_BOTAO, CLASSES_BOTAO[variante], className)}>
      {children}
    </Link>
  );
}

export function EstadoVazio({
  icone: Icone,
  titulo,
  descricao,
  acao,
}: {
  icone: ComponentType<SVGProps<SVGSVGElement>>;
  titulo: string;
  descricao?: string;
  acao?: ReactNode;
}) {
  return (
    <div className="animar-entrar flex flex-col items-center justify-center rounded-cartao border border-dashed border-borda px-6 py-16 text-center">
      <span className="mb-4 flex size-11 items-center justify-center rounded-full bg-superficie-2 text-xl text-apoio">
        <Icone />
      </span>
      <h2 className="text-h3">{titulo}</h2>
      {descricao && <p className="mt-1.5 max-w-sm text-sm text-apoio">{descricao}</p>}
      {acao && <div className="mt-5">{acao}</div>}
    </div>
  );
}

export function Segmentos<T extends string>({
  valor,
  opcoes,
  aoMudar,
  rotulo,
}: {
  valor: T;
  opcoes: { valor: T; rotulo: ReactNode }[];
  aoMudar: (v: T) => void;
  rotulo: string;
}) {
  return (
    <div role="radiogroup" aria-label={rotulo} className="inline-flex flex-wrap rounded-controle border border-borda bg-superficie p-0.5">
      {opcoes.map((o) => (
        <button
          key={o.valor}
          type="button"
          role="radio"
          aria-checked={valor === o.valor}
          onClick={() => aoMudar(o.valor)}
          className={cn(
            "h-8 rounded-selo px-3 text-sm font-medium transition-colors",
            valor === o.valor ? "bg-superficie-2 text-texto" : "text-apoio hover:text-texto",
          )}
        >
          {o.rotulo}
        </button>
      ))}
    </div>
  );
}
