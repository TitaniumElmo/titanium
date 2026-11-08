import { useState, type FormEvent } from "react";
import { acoes, CONTA_SERVICO, detalhesDaFonte, SUPORTA, tokenGuardado, useMundo, useProximaLeitura } from "../api";
import { Botao, Cartao } from "../componentes/base";
import { Pagina } from "../componentes/Pagina";
import { Selo } from "../componentes/Selos";
import { hora, porcentagem } from "../formato";
import { NOME_AGENTE } from "../marca";
import type { Fonte } from "../tipos";
import { cn } from "../util";

const EXEMPLO = {
  url: "https://docs.google.com/spreadsheets/d/exemplo-construtora-mandacaru",
  empresa: "Construtora Mandacaru",
};

const CLASSE_CAMPO =
  "h-10 w-full rounded-controle border border-borda bg-superficie-2 px-3 text-sm text-texto placeholder:text-dica focus:border-acento focus:outline-none";

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

  return (
    <Cartao className="max-w-2xl">
      <form onSubmit={enviar} className="flex flex-col gap-4">
        <div>
          <h2 className="text-h3">{trocando ? "Trocar a pasta do Drive" : api ? "Conectar a pasta do Drive" : "Conectar a planilha de EPI"}</h2>
          <p className="mt-1 text-sm text-apoio">
            {api
              ? "A pasta onde ficam a planilha de controle de EPI e as fotos das fichas de papel."
              : "A planilha que a empresa já usa. Fotos de fichas de papel podem ficar numa pasta do Drive."}
          </p>
        </div>
        <label className="flex flex-col gap-1.5 text-sm">
          {api ? "Link da pasta do Drive" : "Link da planilha ou da pasta"}
          <input
            className={CLASSE_CAMPO}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={api ? "https://drive.google.com/drive/folders/…" : "https://docs.google.com/spreadsheets/d/…"}
            inputMode="url"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          Empresa{api && <span className="text-xs text-fraco">opcional, só para a tela</span>}
          <input
            className={CLASSE_CAMPO}
            value={empresa}
            onChange={(e) => setEmpresa(e.target.value)}
            placeholder="Construtora…"
          />
        </label>
        {api && (
          <label className="flex flex-col gap-1.5 text-sm">
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
        <div className="rounded-controle border border-borda bg-superficie-2 p-3 text-sm text-apoio">
          Compartilhe com a conta de serviço do {NOME_AGENTE}, <span className="break-all font-mono text-xs text-texto">{conta}</span>,
          só com permissão de <strong className="font-medium text-texto">leitura</strong>. O{" "}
          {NOME_AGENTE} nunca altera a planilha.
        </div>
        {api && (
          <p className="rounded-controle border border-risco-borda/40 bg-risco-fundo p-3 text-sm text-risco">
            Uma pasta por vez: a troca vale para todos que usam este link e apaga as auditorias e pendências atuais. A
            pasta nova é auditada inteira em alguns segundos.
          </p>
        )}
        {erro && <p className="text-sm text-irregular">{erro}</p>}
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
}

function TabelaMapeamento({ fonte }: { fonte: Fonte }) {
  return (
    <div className="overflow-hidden rounded-controle border border-borda">
      <table className="w-full text-sm">
        <thead className="bg-superficie-2 text-left text-xs font-medium text-fraco">
          <tr>
            <th className="px-3 py-2 font-medium">Coluna da planilha</th>
            <th className="px-3 py-2 font-medium">Campo do {NOME_AGENTE}</th>
            <th className="px-3 py-2 font-medium">Confiança</th>
          </tr>
        </thead>
        <tbody>
          {fonte.mapeamento.map((m) => {
            const baixa = m.confianca < 0.7;
            return (
              <tr key={m.coluna} className={cn("border-t border-borda", baixa && "bg-risco-fundo")}>
                <td className="px-3 py-2">{m.coluna}</td>
                <td className="px-3 py-2 font-mono text-xs text-apoio">{m.campo}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-full max-w-28 overflow-hidden rounded-full bg-superficie-2">
                      <span
                        className={cn("block h-full rounded-full", baixa ? "bg-risco-borda" : "bg-apoio")}
                        style={{ width: porcentagem(m.confianca) }}
                      />
                    </span>
                    <span className={cn("font-mono text-xs", baixa ? "text-risco" : "text-apoio")}>{porcentagem(m.confianca)}</span>
                    {baixa && <span className="hidden whitespace-nowrap text-xs font-medium text-risco sm:inline">baixa confiança</span>}
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
  return (
    <div className="flex flex-col gap-4">
      <DadosDaFonte fonte={fonte} lendo={lendo} aoTrocar={SUPORTA.trocarPasta && !trocando ? () => setTrocando(true) : undefined} />
      {trocando && <FormularioConexao trocando aoCancelar={() => setTrocando(false)} />}
    </div>
  );
}

function DadosDaFonte({ fonte, lendo, aoTrocar }: { fonte: Fonte; lendo: boolean; aoTrocar?: () => void }) {
  const segundos = useProximaLeitura();
  const { personalizada } = detalhesDaFonte();
  return (
    <Cartao className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-h3">{fonte.empresa}</h2>
            <Selo>{fonte.tipo === "planilha" ? "Planilha" : "Pasta do Drive"}</Selo>
            {personalizada && <Selo>trocada pelo time</Selo>}
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-selo border px-2 py-0.5 text-xs font-medium",
                lendo ? "border-borda bg-superficie-2 text-texto" : "border-ok-borda/40 bg-ok-fundo text-ok",
              )}
            >
              <span className={cn("size-1.5 rounded-full", lendo ? "animar-pulsar bg-acento" : "bg-ok-borda")} />
              {lendo ? "lendo agora" : "conectada"}
            </span>
          </div>
          {fonte.url && <p className="mt-1 break-all font-mono text-xs text-fraco">{fonte.url}</p>}
        </div>
        {aoTrocar && (
          <Botao variante="fantasma" onClick={aoTrocar}>
            Trocar pasta
          </Botao>
        )}
        {SUPORTA.desconectarFonte && (
          <Botao variante="fantasma" onClick={acoes.desconectarFonte}>
            Desconectar
          </Botao>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-controle bg-superficie-2 px-3 py-2.5">
          <div className="text-xs text-fraco">Última leitura</div>
          <div className="font-mono text-sm">{fonte.ultima_leitura ? hora(fonte.ultima_leitura) : "—"}</div>
        </div>
        <div className="rounded-controle bg-superficie-2 px-3 py-2.5 sm:col-span-2">
          <div className="text-xs text-fraco">
            O {NOME_AGENTE} confere esta planilha a cada {fonte.intervalo_s} segundos
          </div>
          <div className="text-sm font-medium tabular-nums">{lendo ? "lendo agora…" : `próxima leitura em ${segundos ?? "—"} s`}</div>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-label">Colunas que o agente encontrou</h3>
        <TabelaMapeamento fonte={fonte} />
      </div>
    </Cartao>
  );
}

export function Fontes() {
  const mundo = useMundo();
  return (
    <Pagina titulo="Fontes conectadas" descricao="A planilha de controle de EPI que a empresa já usa.">
      {mundo.fonte ? <FonteConectada fonte={mundo.fonte} lendo={mundo.execucao_atual !== null} /> : <FormularioConexao />}
    </Pagina>
  );
}
