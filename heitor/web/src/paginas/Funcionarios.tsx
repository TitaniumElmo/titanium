import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAgora, useMundo } from "../api";
import { Avatar } from "../componentes/Avatar";
import { EstadoVazio } from "../componentes/base";
import { CartaoAba } from "../componentes/ResumoHistorico";
import { Pagina } from "../componentes/Pagina";
import { SeloGravidade } from "../componentes/Selos";
import { ehUrgente, resumoFuncionarios } from "../derivados";
import { data, dataCurta, isoDia } from "../formato";
import type { Gravidade, Pendencia } from "../tipos";
import { cn, IconeAlerta, IconeDocumento, IconeLista, IconePessoas } from "../util";

const CLASSE_SELECT =
  "h-9 appearance-none rounded-controle border border-borda bg-superficie pl-3 pr-8 text-sm text-texto hover:border-fraco";

const PESO_STATUS: Record<Gravidade, number> = { irregular: 0, risco: 1, ok: 2 };

export function Funcionarios() {
  const mundo = useMundo();
  const hoje = isoDia(useAgora(60_000));
  const [busca, setBusca] = useState("");
  const [funcao, setFuncao] = useState("todas");
  const [status, setStatus] = useState<"todos" | Gravidade>("todos");

  const todos = useMemo(
    () => resumoFuncionarios(mundo, hoje).sort((a, b) => PESO_STATUS[a.status] - PESO_STATUS[b.status] || a.nome.localeCompare(b.nome)),
    [mundo, hoje],
  );
  const funcoes = [...new Set(todos.map((f) => f.funcao))].sort();
  const termo = busca.trim().toLowerCase();
  const base = todos.filter(
    (f) => (!termo || f.nome.toLowerCase().includes(termo) || f.funcionario_id.includes(termo)) && (funcao === "todas" || f.funcao === funcao),
  );
  const lista = base.filter((f) => status === "todos" || f.status === status);
  const conta = (g: Gravidade) => base.filter((f) => f.status === g).length;

  const proximoPasso = (id: string) =>
    mundo.pendencias
      .filter((p) => p.funcionario_id === id && p.status !== "fechada")
      .sort((a, b) => {
        const peso = (p: Pendencia) => (ehUrgente(p, hoje) ? 0 : p.prioridade === "alta" ? 1 : 2);
        return peso(a) - peso(b) || a.prazo.localeCompare(b.prazo);
      })[0];

  if (!mundo.fonte) {
    return (
      <Pagina titulo="Funcionários">
        <EstadoVazio icone={IconePessoas} titulo="Nenhum funcionário lido" descricao="Os funcionários aparecem aqui depois da primeira leitura da planilha." />
      </Pagina>
    );
  }

  return (
    <Pagina titulo="Funcionários">
      <section role="radiogroup" aria-label="Status" className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
        <CartaoAba rotulo="Todos" valor={base.length} detalhe="funcionários monitorados" selecionado={status === "todos"} aoClicar={() => setStatus("todos")} icone={<IconePessoas className="size-full" />} />
        <CartaoAba
          rotulo="Ok"
          valor={conta("ok")}
          detalhe="ficha sem nenhuma falha"
          selecionado={status === "ok"}
          aoClicar={() => setStatus(status === "ok" ? "todos" : "ok")}
          icone={<IconeLista className="size-full" />}
        />
        <CartaoAba
          rotulo="Risco"
          valor={conta("risco")}
          detalhe="falta uma prova ou conferência"
          selecionado={status === "risco"}
          aoClicar={() => setStatus(status === "risco" ? "todos" : "risco")}
          icone={<IconeDocumento className="size-full" />}
        />
        <CartaoAba
          rotulo="Irregular"
          valor={conta("irregular")}
          detalhe="tem falha para corrigir"
          urgente={conta("irregular") > 0}
          selecionado={status === "irregular"}
          aoClicar={() => setStatus(status === "irregular" ? "todos" : "irregular")}
          icone={<IconeAlerta className="size-full" />}
        />
      </section>

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
      </div>

      {lista.length === 0 ? (
        <EstadoVazio icone={IconePessoas} titulo="Ninguém com esses filtros" />
      ) : (
        <div className="overflow-hidden rounded-cartao border border-borda bg-superficie bg-[radial-gradient(120%_90%_at_100%_0%,var(--cartao-brilho),transparent_60%)]">
          <div className="hidden grid-cols-[minmax(0,2fr)_7rem_minmax(0,2.4fr)_6.5rem_6.5rem] gap-3 border-b border-borda bg-superficie-2/60 px-5 py-2.5 text-sm font-medium text-apoio lg:grid">
            <span>Funcionário</span>
            <span>Status</span>
            <span>Próximo passo</span>
            <span>Em aberto</span>
            <span>Próxima troca</span>
          </div>
          <ul>
            {lista.map((f) => {
              const trocaVencida = f.proxima_troca && f.proxima_troca < hoje;
              const passo = proximoPasso(f.funcionario_id);
              return (
                <li key={f.funcionario_id} className="border-t border-borda first:border-t-0">
                  <Link
                    to={`/funcionarios/${f.funcionario_id}`}
                    className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-2 px-4 py-3.5 transition-colors hover:bg-superficie-2 sm:px-5 lg:grid-cols-[minmax(0,2fr)_7rem_minmax(0,2.4fr)_6.5rem_6.5rem]"
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <Avatar nome={f.nome} />
                      <span className="min-w-0">
                        <span className="block truncate text-base font-medium">{f.nome}</span>
                        <span className="block text-sm text-apoio">
                          {f.funcao} · <span className="font-mono text-xs">{f.funcionario_id}</span>
                        </span>
                      </span>
                    </span>
                    <span>
                      <SeloGravidade gravidade={f.status} />
                    </span>
                    <span className="col-span-2 min-w-0 text-sm lg:col-span-1">
                      {passo ? (
                        <>
                          <span className="line-clamp-1 text-texto" title={passo.acao}>
                            {passo.acao.charAt(0).toUpperCase() + passo.acao.slice(1)}
                          </span>
                          <span className={cn("text-xs tabular-nums", passo.prazo < hoje ? "text-irregular" : "text-apoio")}>
                            {passo.destino === "rh" ? "RH" : "Técnico"} · {passo.prazo < hoje ? "venceu " : "até "}
                            {dataCurta(passo.prazo)}
                          </span>
                        </>
                      ) : (
                        <span className="text-fraco">{f.achados_abertos > 0 ? "Sem tarefa · entra no relatório" : "Nada a fazer"}</span>
                      )}
                    </span>
                    <span className="col-span-2 flex flex-wrap gap-x-4 gap-y-1 text-sm tabular-nums text-apoio lg:contents">
                      <span className="flex gap-x-1 lg:flex-col">
                        <span>
                          <span className="text-texto">{f.achados_abertos}</span> {f.achados_abertos === 1 ? "achado" : "achados"}
                        </span>
                        <span className="lg:hidden">·</span>
                        <span>
                          <span className="text-texto">{f.pendencias_abertas}</span> {f.pendencias_abertas === 1 ? "pendência" : "pendências"}
                        </span>
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
