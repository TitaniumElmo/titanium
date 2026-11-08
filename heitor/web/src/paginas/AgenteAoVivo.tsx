import { useSearchParams } from "react-router-dom";
import { useAgora, useMundo, useProximaLeitura } from "../api";
import { BotaoLink, Cartao, EstadoVazio } from "../componentes/base";
import { CenaEscritorio } from "../cenario/CenaEscritorio";
import { ehUrgente } from "../derivados";
import { CartaoAchado } from "../componentes/CartaoAchado";
import { CicloPendencia } from "../componentes/CicloPendencia";
import { LogAgente } from "../componentes/LogAgente";
import { Pagina } from "../componentes/Pagina";
import { Selo, SeloGatilho } from "../componentes/Selos";
import { dataCurta, dolares, hora, isoDia, ROTULO_GATILHO, ROTULO_MODO } from "../formato";
import { NOME_AGENTE } from "../marca";
import { cn, IconeOlho } from "../util";

export function AgenteAoVivo() {
  const mundo = useMundo();
  const segundos = useProximaLeitura();
  const hoje = isoDia(useAgora(30_000));
  const [parametros, setParametros] = useSearchParams();
  const pedida = parametros.get("execucao");
  const id = pedida ?? mundo.execucao_atual ?? mundo.auditorias[0]?.id;
  const auditoria = mundo.auditorias.find((a) => a.id === id);

  if (!mundo.fonte || !auditoria) {
    return (
      <Pagina titulo="Agente ao vivo">
        <EstadoVazio
          icone={IconeOlho}
          titulo="Nenhuma execução ainda"
          descricao={`Quando a planilha mudar, a execução do ${NOME_AGENTE} aparece aqui, passo a passo.`}
          acao={
            !mundo.fonte && (
              <BotaoLink para="/fontes" variante="primario">
                Conectar planilha
              </BotaoLink>
            )
          }
        />
      </Pagina>
    );
  }

  const eventos = mundo.eventos[auditoria.id] ?? [];
  const rodando = auditoria.status === "processando";
  const achados = mundo.achados.filter((a) => a.auditoria_id === auditoria.id);
  const nomes = Object.fromEntries(mundo.funcionarios.map((f) => [f.funcionario_id, f.nome]));
  const custo = eventos.reduce((soma, e) => soma + e.custo_usd, 0);
  const decisoes = eventos.filter((e) => e.tipo === "decisao").length;
  const degradados = [
    ...new Set([
      ...Object.entries(auditoria.modo_por_funcionario ?? {})
        .filter(([, m]) => m === "degradado")
        .map(([id]) => id),
      ...eventos.filter((e) => e.tipo === "erro" && e.ferramenta === "modelo_indisponivel").map((e) => e.funcionario_id ?? ""),
    ]),
  ].filter(Boolean);
  const outraRodando = mundo.execucao_atual && mundo.execucao_atual !== auditoria.id;

  const escolher = (novo: string) => {
    if (novo === "atual") setParametros({});
    else setParametros({ execucao: novo });
  };

  return (
    <Pagina
      titulo="Agente ao vivo"
      acoes={
        <label className="relative inline-flex">
          <span className="sr-only">Execução</span>
          <select
            value={pedida ?? "atual"}
            onChange={(e) => escolher(e.target.value)}
            className="h-9 max-w-[16rem] appearance-none truncate rounded-controle border border-borda bg-superficie pl-3 pr-8 text-sm text-texto hover:border-fraco"
          >
            <option value="atual">Execução mais recente</option>
            {mundo.auditorias.map((a) => (
              <option key={a.id} value={a.id}>
                {dataCurta(a.iniciada_em)} {hora(a.iniciada_em)} · {ROTULO_GATILHO[a.disparado_por]}
              </option>
            ))}
          </select>
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fraco">▼</span>
        </label>
      }
    >
      <CenaEscritorio
        chave={auditoria.id}
        eventos={eventos}
        rodando={rodando}
        fichasNaPilha={rodando ? auditoria.n_fichas : mundo.funcionarios.length}
        urgente={mundo.pendencias.some((p) => ehUrgente(p, hoje))}
        aguardandoCorrecao={mundo.pendencias.some((p) => p.destino === "tecnico" && p.status !== "fechada")}
        progressoLeitura={mundo.fonte ? 1 - (segundos ?? 0) / mundo.fonte.intervalo_s : 0}
        deslocamento={mundo.deslocamento_ms}
      />

      <Cartao className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <SeloGatilho gatilho={auditoria.disparado_por} comPrefixo />
            <span className="text-sm text-apoio">{auditoria.descricao_disparo}</span>
          </div>
          <span className="flex items-center gap-2 text-xs tabular-nums text-apoio">
            <span className={cn("size-2 rounded-full", rodando ? "animar-pulsar bg-acento" : "bg-ok-borda")} />
            {rodando ? "executando" : `concluída · ${dataCurta(auditoria.iniciada_em)} ${hora(auditoria.iniciada_em)}`}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {auditoria.modo && (
            <Selo titulo="Quem decidiu o caminho nesta execução">modo: {ROTULO_MODO[auditoria.modo]}</Selo>
          )}
          {degradados.length > 0 && (
            <span className="rounded-selo border border-risco-borda/40 bg-risco-fundo px-2 py-0.5 font-medium text-risco">
              ⚠️ modo degradado em {degradados.join(", ")}: o LLM caiu e o agente seguiu pelas regras
            </span>
          )}
          <span className="tabular-nums text-apoio">
            {eventos.length} passos · {decisoes} decisões · <span className="font-mono">{dolares(custo)}</span>
          </span>
        </div>
        <CicloPendencia modo="execucao" eventos={eventos} rodando={rodando} />
        {!rodando && (
          <p className="border-t border-borda pt-3 text-xs tabular-nums text-apoio">
            {outraRodando ? (
              <button type="button" onClick={() => escolher("atual")} className="text-acento hover:underline">
                {NOME_AGENTE} está trabalhando em outra execução agora · acompanhar
              </button>
            ) : (
              <>
                {NOME_AGENTE} vigiando · próxima leitura em <span className="text-texto">{segundos ?? "—"} s</span>
              </>
            )}
          </p>
        )}
      </Cartao>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="flex min-w-0 flex-col gap-2 lg:col-span-3">
          <h2 className="flex h-9 items-center text-label text-apoio">Passo a passo</h2>
          <LogAgente eventos={eventos} rodando={rodando} nomes={nomes} className="h-[320px] sm:h-[420px]" />
        </div>
        <section className="flex flex-col gap-2 lg:col-span-2">
          <h2 className="flex h-9 items-center justify-between text-label text-apoio">
            Achados desta execução
            <span className="text-apoio">{achados.length}</span>
          </h2>
          {achados.length === 0 ? (
            <div className="rounded-cartao border border-dashed border-borda px-4 py-10 text-center text-sm text-fraco">
              {rodando ? "Os achados aparecem aqui conforme as regras rodam." : "Nenhuma lacuna nova nesta execução."}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {achados.map((a) => (
                <CartaoAchado key={a.id} achado={a} compacto className="animar-entrar" />
              ))}
            </div>
          )}
        </section>
      </div>
    </Pagina>
  );
}
