import { useMemo, useState } from "react";
import { useMundo } from "../api";
import { EstadoVazio, Segmentos } from "../componentes/base";
import { CartaoAchado } from "../componentes/CartaoAchado";
import { CartaoAba } from "../componentes/ResumoHistorico";
import { Pagina } from "../componentes/Pagina";
import type { Gravidade, TipoAchado } from "../tipos";
import { IconeAlerta, IconeCalendario, IconeDocumento, IconeLista } from "../util";

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

  const base = mundo.achados.filter(
    (a) => a.gravidade !== "ok" && (gravidade === "todas" || a.gravidade === gravidade) && (funcionario === "todos" || a.funcionario_id === funcionario),
  );
  const lista = base.filter((a) => tipo === "todos" || a.tipo === tipo);
  const total = (t: TipoAchado) => base.filter((a) => a.tipo === t).length;

  const conta = (g: Gravidade) => mundo.achados.filter((a) => a.gravidade === g).length;

  return (
    <Pagina titulo="Achados" descricao="Lacunas na prova documental, cada uma com a evidência na ficha e o destino que o Elmo deu a ela." comPeriodo>
      <section role="radiogroup" aria-label="Tipo de achado" className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
        <CartaoAba
          rotulo="Todos"
          valor={base.length}
          detalhe="falhas encontradas na prova"
          selecionado={tipo === "todos"}
          aoClicar={() => setTipo("todos")}
          icone={<IconeLista className="size-full" />}
        />
        <CartaoAba
          rotulo="Corrigível"
          valor={total("corrigivel")}
          detalhe="viram pendência para o técnico"
          urgente={total("corrigivel") > 0}
          selecionado={tipo === "corrigivel"}
          aoClicar={() => setTipo(tipo === "corrigivel" ? "todos" : "corrigivel")}
          icone={<IconeAlerta className="size-full" />}
        />
        <CartaoAba
          rotulo="Prova"
          valor={total("prova")}
          detalhe="viram pedido de documento ao RH"
          selecionado={tipo === "prova"}
          aoClicar={() => setTipo(tipo === "prova" ? "todos" : "prova")}
          icone={<IconeDocumento className="size-full" />}
        />
        <CartaoAba
          rotulo="Passivo"
          valor={total("passivo")}
          detalhe="sem tarefa: entram no relatório"
          selecionado={tipo === "passivo"}
          aoClicar={() => setTipo(tipo === "passivo" ? "todos" : "passivo")}
          icone={<IconeCalendario className="size-full" />}
        />
      </section>
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
