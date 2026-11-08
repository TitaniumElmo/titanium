// REFERÊNCIA — não é parte oficial do site. Trazido do sistema Carvalho & Felinto como inspiração; pode ser usado, adaptado ou descartado.
//
// Ajudantes do kit, pra ele não depender de nenhuma biblioteca além do React.
import type { SVGProps } from "react";

/** Junta classes, ignorando as vazias (um `cn` mínimo, sem clsx/tailwind-merge). */
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

/** "Maria da Silva" → "MS" */
export function iniciais(nome: string): string {
  return nome
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

// Ícones no traço do lucide (licença ISC), copiados em SVG pra não instalar o pacote. Se o
// projeto já usar lucide-react, dá pra trocar por ele sem mudar mais nada.
function Icone({ children, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  );
}

export const IconeCamera = (p: SVGProps<SVGSVGElement>) => (
  <Icone {...p}>
    <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
    <circle cx="12" cy="13" r="3" />
  </Icone>
);

export const IconeLixeira = (p: SVGProps<SVGSVGElement>) => (
  <Icone {...p}>
    <path d="M3 6h18" />
    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
    <path d="M10 11v6" />
    <path d="M14 11v6" />
  </Icone>
);

export const IconeMenos = (p: SVGProps<SVGSVGElement>) => (
  <Icone {...p}>
    <path d="M5 12h14" />
  </Icone>
);

export const IconeMais = (p: SVGProps<SVGSVGElement>) => (
  <Icone {...p}>
    <path d="M5 12h14" />
    <path d="M12 5v14" />
  </Icone>
);

export const IconeFechar = (p: SVGProps<SVGSVGElement>) => (
  <Icone {...p}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </Icone>
);
