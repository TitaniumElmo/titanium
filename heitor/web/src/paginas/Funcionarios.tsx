import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAgora, useMundo } from "../api";
import { Avatar } from "../componentes/Avatar";
import { EstadoVazio, Segmentos } from "../componentes/base";
import { Pagina } from "../componentes/Pagina";
import { SeloGravidade } from "../componentes/Selos";
import { resumoFuncionarios } from "../derivados";
import { data, isoDia } from "../formato";
import type { Gravidade } from "../tipos";
import { cn, IconePessoas } from "../util";

const CLASSE_SELECT =
  "h-9 appearance-none rounded-controle border border-borda bg-superficie pl-3 pr-8 text-sm text-texto hover:border-fraco";

export function Funcionarios() {
  const mundo = useMundo();
  const hoje = isoDia(useAgora(60_000));
  const [busca, setBusca] = useState("");
  const [funcao, setFuncao] = useState("todas");
  const [status, setStatus] = useState<"todos" | Gravidade>("todos");

  const todos = useMemo(() => resumoFuncionarios(mundo, hoje), [mundo, hoje]);
  const funcoes = [...new Set(todos.map((f) => f.funcao))].sort();
  const termo = busca.trim().toLowerCase();
  const lista = todos.filter(
    (f) =>
      (!termo || f.nome.toLowerCase().includes(termo) || f.funcionario_id.includes(termo)) &&
      (funcao === "todas" || f.funcao === funcao) &&
      (status === "todos" || f.status === status),
  );

  if (!mundo.fonte) {
    return (
      <Pagina titulo="Funcionários">
        <EstadoVazio icone={IconePessoas} titulo="Nenhum funcionário lido" descricao="Os funcionários aparecem aqui depois da primeira leitura da planilha." />
      </Pagina>
    );
  }

  return (
    <Pagina titulo="Funcionários" descricao="Status geral de cada pessoa: o pior entre os achados em aberto.">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar por nome ou matrícula"
          className="h-9 w-full rounded-controle border border-borda bg-superficie px-3 text-sm text-texto placeholder:text-dica focus:border-acento focus:outline-none sm:w-64"
        />
        <label className="relative inline-flex">
          <span className="sr-only">Função</span>
          <select value={funcao} onChange={(e) => setFuncao(e.target.value)} className={CLASSE_SELECT}>
            <option value="todas">Todas as funções</option>
            {funcoes.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fraco">▼</span>
        </label>
        <Segmentos
          rotulo="Status"
          valor={status}
          aoMudar={setStatus}
          opcoes={[
            { valor: "todos", rotulo: "Todos" },
            { valor: "irregular", rotulo: "Irregular" },
            { valor: "risco", rotulo: "Risco" },
            { valor: "ok", rotulo: "Ok" },
          ]}
        />
      </div>

      {lista.length === 0 ? (
        <EstadoVazio icone={IconePessoas} titulo="Ninguém com esses filtros" />
      ) : (
        <div className="overflow-hidden rounded-cartao border border-borda bg-superficie">
          <div className="hidden grid-cols-[minmax(0,2fr)_7rem_6rem_6rem_7rem_7rem] gap-3 border-b border-borda bg-superficie-2 px-4 py-2 text-xs font-medium text-fraco lg:grid">
            <span>Funcionário</span>
            <span>Status</span>
            <span>Achados</span>
            <span>Pendências</span>
            <span>Última entrega</span>
            <span>Próxima troca</span>
          </div>
          <ul>
            {lista.map((f) => {
              const trocaVencida = f.proxima_troca && f.proxima_troca < hoje;
              return (
                <li key={f.funcionario_id} className="border-t border-borda first:border-t-0">
                  <Link
                    to={`/funcionarios/${f.funcionario_id}`}
                    className="grid grid-cols-[1fr_auto] items-center gap-3 px-4 py-3 transition-colors hover:bg-superficie-2 lg:grid-cols-[minmax(0,2fr)_7rem_6rem_6rem_7rem_7rem]"
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <Avatar nome={f.nome} />
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">{f.nome}</span>
                        <span className="block text-xs text-apoio">
                          {f.funcao} · <span className="font-mono">{f.funcionario_id}</span>
                        </span>
                      </span>
                    </span>
                    <span>
                      <SeloGravidade gravidade={f.status} />
                    </span>
                    <span className="col-span-2 flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-apoio lg:contents">
                      <span>
                        <span className="text-texto">{f.achados_abertos}</span>
                        <span className="lg:hidden"> achados</span>
                      </span>
                      <span>
                        <span className="text-texto">{f.pendencias_abertas}</span>
                        <span className="lg:hidden"> pendências</span>
                      </span>
                      <span>
                        <span className="lg:hidden">última </span>
                        {f.ultima_entrega ? data(f.ultima_entrega) : "—"}
                      </span>
                      <span className={cn(trocaVencida && "text-irregular")}>
                        <span className="lg:hidden">troca </span>
                        {f.proxima_troca ? data(f.proxima_troca) : "—"}
                      </span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Pagina>
  );
}
