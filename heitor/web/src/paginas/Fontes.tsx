import { useState, type FormEvent } from "react";
import { acoes, CONTA_SERVICO, detalhesDaFonte, SUPORTA, tokenGuardado, useMundo, useProximaLeitura } from "../api";
import { Botao, Cartao } from "../componentes/base";
import { Pagina } from "../componentes/Pagina";
import { CartaoNumero } from "../componentes/ResumoHistorico";
import { Selo } from "../componentes/Selos";
import { hora, porcentagem } from "../formato";
import { NOME_AGENTE } from "../marca";
import type { Fonte } from "../tipos";
import { cn, IconeAlerta, IconeAtividade, IconeCalendario, IconeLista, IconeTomada } from "../util";

const EXEMPLO = {
  url: "https://docs.google.com/spreadsheets/d/exemplo-construtora-mandacaru",
  empresa: "Construtora Mandacaru",
};

const FUNDO_PRETO = "bg-superficie bg-[radial-gradient(120%_90%_at_100%_0%,var(--cartao-brilho),transparent_60%)]";

const CLASSE_CAMPO =
  "h-11 w-full rounded-controle border border-borda bg-superficie-2 px-3 text-sm text-texto placeholder:text-dica focus:border-acento focus:outline-none sm:text-base";

const NOME_DO_CAMPO: Record<string, string> = {
  nome: "Nome do funcionário",
  funcionario_id: "Matrícula",
  funcao: "Função",
  data: "Data da entrega",
  epi: "Equipamento (EPI)",
  ca: "Número do CA",
  qtd: "Quantidade",
  motivo: "Motivo da entrega",
  assinatura: "Assinatura",
};

function passos(api: boolean) {
  return [
    {
      titulo: "Cole o link",
      texto: api
        ? "Da pasta do Drive onde ficam a planilha de controle de EPI e as fotos das fichas de papel."
        : "Da planilha de EPI que a empresa já usa, ou da pasta do Drive com as fotos das fichas de papel.",
    },
    { titulo: "Compartilhe com o Elmo", texto: "Só com permissão de leitura. O Elmo nunca altera a planilha." },
    { titulo: "Pronto", texto: "O Elmo lê sozinho, confere cada entrega e avisa quando algo estiver errado." },
  ];
}

function CopiarConta({ conta }: { conta: string }) {
  const [copiado, setCopiado] = useState(false);
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(conta);
      setCopiado(true);
      window.setTimeout(() => setCopiado(false), 2000);
    } catch {
      setCopiado(false);
    }
  };
  return (
    <div className="flex flex-col gap-2 rounded-controle border border-borda bg-superficie-2 p-3 sm:p-4">
      <span className="text-sm text-apoio sm:text-base">
        Compartilhe com este e-mail, só com permissão de <strong className="font-medium text-texto">leitura</strong>:
      </span>
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 break-all font-mono text-sm text-texto">{conta}</span>
        <Botao variante="fantasma" onClick={copiar} className="shrink-0">
          {copiado ? "Copiado" : "Copiar"}
        </Botao>
      </div>
    </div>
  );
}

function FormularioConexao({ trocando = false, aoCancelar }: { trocando?: boolean; aoCancelar?: () => void }) {
  const api = SUPORTA.trocarPasta;
  const [url, setUrl] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [token, setToken] = useState(() => (api ? tokenGuardado() : ""));
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const { conta_servico, personalizada } = detalhesDaFonte();
  const conta = conta_servico ?? CONTA_SERVICO;

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    if (!/^https:\/\/(docs|drive)\.google\.com\//.test(url.trim())) {
      setErro(api ? "Use o link da pasta do Drive (drive.google.com/drive/folders/…)." : "Use o link de uma planilha do Google Sheets ou de uma pasta do Drive.");
      return;
    }
    if (!api && !empresa.trim()) {
      setErro("Informe o nome da empresa.");
      return;
    }
    if (api && !token.trim()) {
      setErro("Informe a senha do time.");
      return;
    }
    setErro(null);
    if (!api) {
      acoes.conectarFonte(url.trim(), empresa.trim());
      return;
    }
    setEnviando(true);
    const falha = await acoes.trocarPasta(url, token, empresa);
    setEnviando(false);
    if (falha) setErro(falha);
    else aoCancelar?.();
  };

  const voltar = async () => {
    if (!token.trim()) {
      setErro("Informe a senha do time.");
      return;
    }
    setEnviando(true);
    const falha = await acoes.voltarPastaPadrao(token);
    setEnviando(false);
    if (falha) setErro(falha);
    else aoCancelar?.();
  };

  const formulario = (
    <Cartao className={cn("sm:p-6", FUNDO_PRETO, trocando ? "lg:col-span-5" : "lg:col-span-3")}>
      <form onSubmit={enviar} className="flex flex-col gap-4">
        <h2 className="text-base font-semibold sm:text-lg">{trocando ? "Trocar a pasta do Drive" : api ? "Conectar a pasta do Drive" : "Conectar a planilha de EPI"}</h2>
        <label className="flex flex-col gap-1.5 text-sm font-medium sm:text-base">
          {api ? "Link da pasta do Drive" : "Link da planilha ou da pasta"}
          <input
            className={CLASSE_CAMPO}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={api ? "https://drive.google.com/drive/folders/…" : "https://docs.google.com/spreadsheets/d/…"}
            inputMode="url"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium sm:text-base">
          <span>
            Nome da empresa{api && <span className="ml-2 text-sm font-normal text-fraco">opcional, só para a tela</span>}
          </span>
          <input className={CLASSE_CAMPO} value={empresa} onChange={(e) => setEmpresa(e.target.value)} placeholder="Construtora…" />
        </label>
        {api && (
          <label className="flex flex-col gap-1.5 text-sm font-medium sm:text-base">
            Senha do time
            <input
              className={CLASSE_CAMPO}
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="só o time troca a pasta"
            />
          </label>
        )}
        <CopiarConta conta={conta} />
        {api && (
          <p className="rounded-controle border border-risco-borda/40 bg-risco-fundo p-3 text-sm text-risco sm:text-base">
            Uma pasta por vez: a troca vale para todos que usam este link e apaga as auditorias e pendências atuais. A pasta nova é auditada inteira em alguns
            segundos.
          </p>
        )}
        {erro && (
          <p role="alert" className="text-sm text-irregular sm:text-base">
            {erro}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Botao type="submit" variante="primario" disabled={enviando}>
            {enviando ? "Conferindo o acesso…" : trocando ? "Trocar pasta" : "Conectar"}
          </Botao>
          {api && personalizada && (
            <Botao variante="fantasma" disabled={enviando} onClick={() => void voltar()}>
              Voltar à pasta da demo
            </Botao>
          )}
          {api && !trocando && (
            <Botao variante="fantasma" disabled={enviando} onClick={() => void acoes.rodarExemplo()}>
              Auditar fichas de exemplo
            </Botao>
          )}
          {!api && (
            <Botao
              variante="fantasma"
              onClick={() => {
                setUrl(EXEMPLO.url);
                setEmpresa(EXEMPLO.empresa);
              }}
            >
              Usar planilha de exemplo
            </Botao>
          )}
          {trocando && (
            <Botao variante="fantasma" disabled={enviando} onClick={aoCancelar}>
              Cancelar
            </Botao>
          )}
        </div>
      </form>
    </Cartao>
  );

  if (trocando) return formulario;

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      {formulario}
      <Cartao className={cn("flex flex-col gap-4 sm:p-6 lg:col-span-2", FUNDO_PRETO)}>
        <h2 className="text-base font-semibold sm:text-lg">Como funciona</h2>
        <ol className="flex flex-col gap-4">
          {passos(api).map((p, i) => (
            <li key={p.titulo} className="flex gap-3">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-superficie-2 text-sm font-semibold tabular-nums">{i + 1}</span>
              <span className="min-w-0">
                <span className="block text-sm font-medium sm:text-base">{p.titulo}</span>
                <span className="block text-sm text-apoio sm:text-base">{p.texto}</span>
              </span>
            </li>
          ))}
        </ol>
      </Cartao>
    </div>
  );
}

function TabelaMapeamento({ fonte }: { fonte: Fonte }) {
  return (
    <div className="overflow-hidden rounded-controle border border-borda">
      <table className="w-full text-sm sm:text-base">
        <thead className="bg-superficie-2/60 text-left text-sm font-medium text-apoio">
          <tr>
            <th className="px-3 py-2.5 font-medium">Coluna da planilha</th>
            <th className="px-3 py-2.5 font-medium">O que o {NOME_AGENTE} entendeu</th>
            <th className="px-3 py-2.5 font-medium">Confiança</th>
          </tr>
        </thead>
        <tbody>
          {fonte.mapeamento.map((m) => {
            const baixa = m.confianca < 0.7;
            return (
              <tr key={m.coluna} className={cn("border-t border-borda", baixa && "bg-risco-fundo")}>
                <td className="px-3 py-2.5">{m.coluna}</td>
                <td className="px-3 py-2.5 text-apoio">{NOME_DO_CAMPO[m.campo] ?? m.campo}</td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-full max-w-24 overflow-hidden rounded-full bg-superficie-2">
                      <span className={cn("block h-full rounded-full", baixa ? "bg-risco-borda" : "bg-apoio")} style={{ width: porcentagem(m.confianca) }} />
                    </span>
                    <span className={cn("font-mono text-sm tabular-nums", baixa ? "text-risco" : "text-apoio")}>{porcentagem(m.confianca)}</span>
                    {baixa && (
                      <span className="inline-flex items-center gap-1 whitespace-nowrap text-sm font-medium text-risco">
                        <IconeAlerta className="size-4 shrink-0" aria-hidden />
                        <span className="hidden sm:inline">confira</span>
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FonteConectada({ fonte, lendo }: { fonte: Fonte; lendo: boolean }) {
  const [trocando, setTrocando] = useState(false);
  const segundos = useProximaLeitura();
  const { personalizada } = detalhesDaFonte();
  const total = fonte.mapeamento.length;
  const baixas = fonte.mapeamento.filter((m) => m.confianca < 0.7).length;
  const comErro = fonte.status === "erro";
  const podeTrocar = SUPORTA.trocarPasta && !trocando;

  return (
    <>
      <Cartao className={cn("flex flex-wrap items-start justify-between gap-3 sm:p-6", FUNDO_PRETO)}>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold sm:text-lg">{fonte.empresa}</h2>
            <Selo>{fonte.tipo === "planilha" ? "Planilha" : "Pasta do Drive"}</Selo>
            {personalizada && <Selo>trocada pelo time</Selo>}
          </div>
          {fonte.url && <p className="mt-1 break-all font-mono text-sm text-fraco">{fonte.url}</p>}
          <p className="mt-2 text-sm text-apoio sm:text-base">O {NOME_AGENTE} só lê esta fonte. Ele nunca altera.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {podeTrocar && (
            <Botao variante="fantasma" onClick={() => setTrocando(true)}>
              Trocar pasta
            </Botao>
          )}
          {SUPORTA.desconectarFonte && (
            <Botao variante="fantasma" onClick={acoes.desconectarFonte}>
              Desconectar
            </Botao>
          )}
        </div>
      </Cartao>

      {trocando && <FormularioConexao trocando aoCancelar={() => setTrocando(false)} />}

      <section aria-label="Situação da leitura" className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
        <CartaoNumero
          rotulo="Situação"
          valor={comErro ? "Com erro" : lendo ? "Lendo" : "Conectada"}
          detalhe={comErro ? "o Elmo não conseguiu ler" : lendo ? "conferindo agora" : "tudo certo com a leitura"}
          urgente={comErro}
          icone={<IconeTomada className="size-full" />}
        />
        <CartaoNumero rotulo="Última leitura" valor={fonte.ultima_leitura ? hora(fonte.ultima_leitura) : "—"} detalhe="horário da última conferência" icone={<IconeCalendario className="size-full" />} />
        <CartaoNumero
          rotulo="Próxima leitura"
          valor={lendo ? "agora" : `${segundos ?? "—"} s`}
          detalhe={`o ${NOME_AGENTE} confere a cada ${fonte.intervalo_s} segundos`}
          icone={<IconeAtividade className="size-full" />}
        />
        <CartaoNumero
          rotulo="Colunas entendidas"
          valor={total === 0 ? "—" : `${total - baixas} de ${total}`}
          detalhe={total === 0 ? "ainda sem leitura das colunas" : baixas > 0 ? `${baixas} com baixa confiança: confira abaixo` : "todas com boa confiança"}
          urgente={baixas > 0}
          icone={<IconeLista className="size-full" />}
        />
      </section>

      {total > 0 && (
        <Cartao className={cn("flex flex-col gap-3 sm:p-6", FUNDO_PRETO)}>
          <div>
            <h2 className="text-base font-semibold sm:text-lg">Como o {NOME_AGENTE} entendeu as colunas</h2>
            {baixas > 0 && (
              <p className="mt-1 text-sm text-apoio sm:text-base">
                {baixas === 1 ? "Uma coluna ficou" : `${baixas} colunas ficaram`} com baixa confiança. Confira se o {NOME_AGENTE} entendeu certo.
              </p>
            )}
          </div>
          <TabelaMapeamento fonte={fonte} />
        </Cartao>
      )}
    </>
  );
}

export function Fontes() {
  const mundo = useMundo();
  return (
    <Pagina titulo="Fontes conectadas">
      {mundo.fonte ? <FonteConectada fonte={mundo.fonte} lendo={mundo.execucao_atual !== null} /> : <FormularioConexao />}
    </Pagina>
  );
}
