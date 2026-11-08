import { Link, useParams } from "react-router-dom";
import { useAgora, useMundo } from "../api";
import { Avatar } from "../componentes/Avatar";
import { BotaoLink, Cartao, EstadoVazio } from "../componentes/base";
import { CartaoAchado } from "../componentes/CartaoAchado";
import { CicloPendencia } from "../componentes/CicloPendencia";
import { Pagina } from "../componentes/Pagina";
import { SeloDestino, SeloGravidade, SeloStatus } from "../componentes/Selos";
import { achadoAberto, resumoFuncionarios, statusPapel, trocasPrevistas, type StatusPapel } from "../derivados";
import { data, dataCurta, isoDia } from "../formato";
import { cn, IconePessoas } from "../util";

const PAPEL: Record<StatusPapel, { rotulo: string; dica: string; classe: string }> = {
  conferido: {
    rotulo: "✅ conferido com a ficha",
    dica: "Assinatura compatível com o nome do funcionário",
    classe: "border-ok-borda/40 bg-ok-fundo text-ok",
  },
  duvida: {
    rotulo: "⚠️ em dúvida",
    dica: "A leitura da assinatura não foi conclusiva: vai para conferência humana",
    classe: "border-risco-borda/40 bg-risco-fundo text-risco",
  },
  sem_assinatura: {
    rotulo: "❌ sem assinatura",
    dica: "A entrega está na ficha de papel, mas sem assinatura",
    classe: "border-irregular-borda/40 bg-irregular-fundo text-irregular",
  },
  nao_localizada: {
    rotulo: "🔍 não está no papel",
    dica: "Está na planilha e não foi localizada na ficha de papel (entrega_sem_ficha)",
    classe: "border-risco-borda/40 bg-risco-fundo text-risco",
  },
  nao_conferida: { rotulo: "—", dica: "Sem foto da ficha de papel para conferir", classe: "border-transparent text-fraco" },
};

function SeloPapel({ status }: { status: StatusPapel }) {
  const p = PAPEL[status];
  return (
    <span title={p.dica} className={cn("inline-flex whitespace-nowrap rounded-selo border px-2 py-0.5 text-xs font-medium", p.classe)}>
      {p.rotulo}
    </span>
  );
}

export function FichaFuncionario() {
  const { id } = useParams();
  const mundo = useMundo();
  const hoje = isoDia(useAgora(60_000));
  const resumo = resumoFuncionarios(mundo, hoje).find((f) => f.funcionario_id === id);

  if (!resumo) {
    return (
      <Pagina titulo="Funcionário">
        <EstadoVazio
          icone={IconePessoas}
          titulo="Funcionário não encontrado"
          acao={<BotaoLink para="/funcionarios">Voltar para a lista</BotaoLink>}
        />
      </Pagina>
    );
  }

  const linhas = mundo.linhas.filter((l) => l.funcionario_id === id).sort((a, b) => a.linha - b.linha);
  const achados = mundo.achados.filter((a) => a.funcionario_id === id);
  const pendencias = mundo.pendencias.filter((p) => p.funcionario_id === id);
  const trocas = trocasPrevistas(linhas).filter((t) => t.ultima >= isoDia(new Date(`${hoje}T12:00:00`).getTime() - 365 * 86_400_000));
  const achadoDaLinha = (n: number) => achados.find((a) => a.linha === n);
  const foraDaPlanilha = mundo.fora_da_planilha.filter((f) => f.funcionario_id === id);
  const conferidas = linhas.filter((l) => statusPapel(l) !== "nao_conferida");
  const contaPapel = (s: StatusPapel) => conferidas.filter((l) => statusPapel(l) === s).length;

  return (
    <Pagina titulo={resumo.nome} descricao={`${resumo.funcao} · matrícula ${resumo.funcionario_id}`}>
      <Link to="/funcionarios" className="-mt-3 self-start text-label text-apoio hover:text-texto">
        ← todos os funcionários
      </Link>

      <Cartao className="flex flex-wrap items-center gap-4">
        <Avatar nome={resumo.nome} tamanho="lg" />
        <div className="flex flex-1 flex-wrap gap-x-8 gap-y-3 text-sm">
          <div>
            <div className="text-xs text-fraco">Status geral</div>
            <SeloGravidade gravidade={resumo.status} />
          </div>
          <div>
            <div className="text-xs text-fraco">Achados abertos</div>
            <div className="font-mono">{resumo.achados_abertos}</div>
          </div>
          <div>
            <div className="text-xs text-fraco">Pendências abertas</div>
            <div className="font-mono">{resumo.pendencias_abertas}</div>
          </div>
          <div>
            <div className="text-xs text-fraco">Próxima troca</div>
            <div className={cn("font-mono", resumo.proxima_troca && resumo.proxima_troca < hoje && "text-irregular")}>
              {resumo.proxima_troca ? data(resumo.proxima_troca) : "—"}
            </div>
          </div>
        </div>
      </Cartao>

      <section className="flex flex-col gap-2">
        <h2 className="text-label text-apoio">Linhas da ficha</h2>
        <div className="overflow-x-auto rounded-cartao border border-borda bg-superficie">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-superficie-2 text-left text-xs font-medium text-fraco">
              <tr>
                <th className="px-3 py-2 text-right font-medium">Linha</th>
                <th className="px-3 py-2 font-medium">Data</th>
                <th className="px-3 py-2 font-medium">EPI</th>
                <th className="px-3 py-2 font-medium">CA</th>
                <th className="px-3 py-2 text-right font-medium">Qtd</th>
                <th className="px-3 py-2 font-medium">Assinatura</th>
                <th className="px-3 py-2 font-medium">Ficha de papel</th>
                <th className="px-3 py-2 font-medium">Achado</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l) => {
                const achado = achadoDaLinha(l.linha);
                return (
                  <tr key={l.linha} className="border-t border-borda">
                    <td className="px-3 py-2 text-right font-mono text-xs text-fraco">{l.linha}</td>
                    <td className="px-3 py-2 font-mono text-xs">{data(l.data)}</td>
                    <td className="px-3 py-2">{l.epi}</td>
                    <td className="px-3 py-2 font-mono text-xs">{l.ca ?? <span className="text-risco">vazio</span>}</td>
                    <td className="px-3 py-2 text-right font-mono text-xs">{l.qtd}</td>
                    <td className="px-3 py-2 text-xs">
                      {l.assinatura === null ? (
                        <span className="text-fraco">—</span>
                      ) : l.assinatura ? (
                        <span className="text-apoio">sim</span>
                      ) : (
                        <span className="text-irregular">não</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <SeloPapel status={statusPapel(l)} />
                    </td>
                    <td className="px-3 py-2">{achado && <SeloGravidade gravidade={achado.gravidade} />}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-fraco">
          Somente leitura. O agente nunca altera a ficha.
          {conferidas.length > 0 &&
            ` Ficha de papel: ${contaPapel("conferido")} de ${conferidas.length} entregas com assinatura compatível com o nome do funcionário, ${contaPapel("duvida")} em dúvida, ${contaPapel("sem_assinatura")} sem assinatura, ${contaPapel("nao_localizada")} não localizada no papel.`}
        </p>
        {foraDaPlanilha.length > 0 && (
          <div className="rounded-cartao border border-risco-borda/40 bg-risco-fundo p-4">
            <h3 className="text-label text-risco">Só na ficha de papel (ficha_sem_planilha)</h3>
            <p className="mt-0.5 text-xs text-apoio">Entregas que estão no papel e não aparecem na planilha. Achado de risco: lançar na planilha se a entrega aconteceu.</p>
            <ul className="mt-2 flex flex-col gap-1">
              {foraDaPlanilha.map((f) => (
                <li key={`${f.data}-${f.epi}`} className="flex gap-3 text-sm">
                  <span className="font-mono text-xs">{data(f.data)}</span>
                  <span>{f.epi}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="flex flex-col gap-2">
          <h2 className="text-label text-apoio">Achados</h2>
          {achados.length === 0 ? (
            <p className="rounded-cartao border border-dashed border-borda px-4 py-6 text-center text-sm text-fraco">Nenhuma lacuna na ficha.</p>
          ) : (
            achados.map((a) => (
              <CartaoAchado
                key={a.id}
                achado={a}
                pendencia={mundo.pendencias.find((p) => p.achado_id === a.id)}
                className={cn(!achadoAberto(a, mundo.pendencias) && "opacity-60")}
              />
            ))
          )}
        </section>

        <div className="flex flex-col gap-6">
          <section className="flex flex-col gap-2">
            <h2 className="text-label text-apoio">Pendências</h2>
            {pendencias.length === 0 ? (
              <p className="rounded-cartao border border-dashed border-borda px-4 py-6 text-center text-sm text-fraco">Nenhuma pendência.</p>
            ) : (
              pendencias.map((p) => (
                <Link
                  key={p.id}
                  to={`/pendencias?p=${p.id}`}
                  className="flex flex-col gap-2 rounded-cartao border border-borda bg-superficie p-4 transition-colors hover:border-fraco"
                >
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-fraco">{p.id}</span>
                    <SeloStatus status={p.status} />
                    <SeloDestino destino={p.destino} />
                    <span className="ml-auto font-mono text-xs text-apoio">até {dataCurta(p.prazo)}</span>
                  </span>
                  <span className="text-sm">{p.acao}</span>
                  <CicloPendencia modo="compacto" pendencia={p} />
                </Link>
              ))
            )}
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="text-label text-apoio">Próximas trocas</h2>
            <ul className="rounded-cartao border border-borda bg-superficie">
              {trocas.map((t) => (
                <li key={t.epi} className="flex items-center justify-between gap-3 border-t border-borda px-4 py-2.5 text-sm first:border-t-0">
                  <span>{t.epi}</span>
                  <span className={cn("font-mono text-xs", t.vence < hoje ? "text-irregular" : "text-apoio")}>
                    {t.vence < hoje ? "venceu " : ""}
                    {data(t.vence)}
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-fraco">Conforme a durabilidade indicada pelo fabricante.</p>
          </section>
        </div>
      </div>
    </Pagina>
  );
}
