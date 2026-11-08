import { useMemo, useState } from "react";
import { useMundo } from "../api";
import { EstadoVazio, Segmentos } from "../componentes/base";
import { CartaoAchado } from "../componentes/CartaoAchado";
import { Pagina } from "../componentes/Pagina";
import { ROTULO_TIPO } from "../formato";
import type { Gravidade, TipoAchado } from "../tipos";
import { IconeAlerta } from "../util";

type FiltroGravidade = "todas" | Exclude<Gravidade, "ok">;
type FiltroTipo = "todos" | TipoAchado;

export function Achados() {
  const mundo = useMundo();
  const [gravidade, setGravidade] = useState<FiltroGravidade>("todas");
  const [tipo, setTipo] = useState<FiltroTipo>("todos");
  const [funcionario, setFuncionario] = useState("todos");

  const pessoas = useMemo(() => {
    const vistos = new Map<string, string>();
    for (const a of mundo.achados) vistos.set(a.funcionario_id, a.nome);
    return [...vistos.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [mundo.achados]);

  const lista = mundo.achados.filter(
    (a) =>
      a.gravidade !== "ok" &&
      (gravidade === "todas" || a.gravidade === gravidade) &&
      (tipo === "todos" || a.tipo === tipo) &&
      (funcionario === "todos" || a.funcionario_id === funcionario),
  );

  const conta = (g: Gravidade) => mundo.achados.filter((a) => a.gravidade === g).length;

  return (
    <Pagina titulo="Achados" descricao="Lacunas na prova documental, cada uma com a evidência na ficha." comPeriodo>
      <div className="flex flex-wrap items-center gap-2">
        <Segmentos
          rotulo="Gravidade"
          valor={gravidade}
          aoMudar={setGravidade}
          opcoes={[
            { valor: "todas", rotulo: "Todas" },
            { valor: "irregular", rotulo: `Irregular · ${conta("irregular")}` },
            { valor: "risco", rotulo: `Risco · ${conta("risco")}` },
          ]}
        />
        <Segmentos
          rotulo="Tipo"
          valor={tipo}
          aoMudar={setTipo}
          opcoes={[
            { valor: "todos", rotulo: "Todos os tipos" },
            { valor: "corrigivel", rotulo: ROTULO_TIPO.corrigivel },
            { valor: "prova", rotulo: "Prova" },
            { valor: "passivo", rotulo: ROTULO_TIPO.passivo },
          ]}
        />
        <label className="relative inline-flex">
          <span className="sr-only">Funcionário</span>
          <select
            value={funcionario}
            onChange={(e) => setFuncionario(e.target.value)}
            className="h-9 appearance-none rounded-controle border border-borda bg-superficie pl-3 pr-8 text-sm text-texto hover:border-fraco"
          >
            <option value="todos">Todos os funcionários</option>
            {pessoas.map(([id, nome]) => (
              <option key={id} value={id}>
                {nome}
              </option>
            ))}
          </select>
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fraco">▼</span>
        </label>
      </div>

      {lista.length === 0 ? (
        <EstadoVazio
          icone={IconeAlerta}
          titulo={mundo.achados.length ? "Nenhum achado com esses filtros" : "Nenhum achado"}
          descricao="Os achados vêm das regras de auditoria. O agente não decide sozinho o que é irregular."
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {lista.map((a) => (
            <CartaoAchado key={a.id} achado={a} pendencia={mundo.pendencias.find((p) => p.achado_id === a.id)} />
          ))}
        </div>
      )}
    </Pagina>
  );
}
