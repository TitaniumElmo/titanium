import { SALARIO_MINIMO_USADO } from "../api";
import { reais } from "../formato";
import type { Relatorio } from "../tipos";
import { cn } from "../util";

export function CartaoExposicao({ total, porFuncao, className }: { total: number; porFuncao: Relatorio["exposicao_por_funcao"]; className?: string }) {
  const maior = Math.max(...porFuncao.map((f) => f.valor), 1);
  return (
    <section
      className={cn(
        "flex flex-col gap-4 rounded-cartao border border-acento/30 bg-gradient-to-br from-acento-suave to-superficie p-5",
        className,
      )}
    >
      <div>
        <h2 className="text-label">Exposição potencial máxima</h2>
        <p className="text-h1 tabular-nums text-texto">{reais(total)}</p>
        <p className="mt-1 text-xs text-apoio">Se a perícia confirmar a insalubridade. Só para o passivo.</p>
      </div>
      <ul className="flex flex-col gap-2">
        {porFuncao.map((f) => (
          <li key={f.funcao} className="grid grid-cols-[6rem_1fr_auto] items-center gap-2 text-xs">
            <span className="text-apoio">{f.funcao}</span>
            <span className="h-2 overflow-hidden rounded-full bg-superficie-2">
              <span className="block h-full rounded-full bg-acento" style={{ width: `${(f.valor / maior) * 100}%` }} />
            </span>
            <span className="font-mono">{reais(f.valor)}</span>
          </li>
        ))}
      </ul>
      <p className="text-caption tabular-nums text-fraco">
        grau médio 20% · salário mínimo usado {reais(SALARIO_MINIMO_USADO)} · até 60 meses
      </p>
    </section>
  );
}
