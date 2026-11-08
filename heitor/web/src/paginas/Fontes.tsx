import { useState, type FormEvent } from "react";
import { acoes, CONTA_SERVICO, useMundo, useProximaLeitura } from "../api";
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

function FormularioConexao() {
  const [url, setUrl] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const enviar = (e: FormEvent) => {
    e.preventDefault();
    if (!/^https:\/\/(docs|drive)\.google\.com\//.test(url.trim())) {
      setErro("Use o link de uma planilha do Google Sheets ou de uma pasta do Drive.");
      return;
    }
    if (!empresa.trim()) {
      setErro("Informe o nome da empresa.");
      return;
    }
    setErro(null);
    acoes.conectarFonte(url.trim(), empresa.trim());
  };

  return (
    <Cartao className="max-w-2xl">
      <form onSubmit={enviar} className="flex flex-col gap-4">
        <div>
          <h2 className="text-h3">Conectar a planilha de EPI</h2>
          <p className="mt-1 text-sm text-apoio">
            A planilha que a empresa já usa. Fotos de fichas de papel podem ficar numa pasta do Drive.
          </p>
        </div>
        <label className="flex flex-col gap-1.5 text-sm">
          Link da planilha ou da pasta
          <input
            className={CLASSE_CAMPO}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://docs.google.com/spreadsheets/d/…"
            inputMode="url"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          Empresa
          <input
            className={CLASSE_CAMPO}
            value={empresa}
            onChange={(e) => setEmpresa(e.target.value)}
            placeholder="Construtora…"
          />
        </label>
        <div className="rounded-controle border border-borda bg-superficie-2 p-3 text-sm text-apoio">
          Compartilhe com a conta de serviço do {NOME_AGENTE}, <span className="break-all font-mono text-xs text-texto">{CONTA_SERVICO}</span>,
          só com permissão de <strong className="font-medium text-texto">leitura</strong> nas abas da empresa. O{" "}
          {NOME_AGENTE} nunca altera a planilha.
        </div>
        {erro && <p className="text-sm text-irregular">{erro}</p>}
        <div className="flex flex-wrap gap-2">
          <Botao type="submit" variante="primario">
            Conectar
          </Botao>
          <Botao
            variante="fantasma"
            onClick={() => {
              setUrl(EXEMPLO.url);
              setEmpresa(EXEMPLO.empresa);
            }}
          >
            Usar planilha de exemplo
          </Botao>
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
  const segundos = useProximaLeitura();
  return (
    <Cartao className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-h3">{fonte.empresa}</h2>
            <Selo>{fonte.tipo === "planilha" ? "Planilha" : "Pasta do Drive"}</Selo>
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
          <p className="mt-1 break-all font-mono text-xs text-fraco">{fonte.url}</p>
        </div>
        <Botao variante="fantasma" onClick={acoes.desconectarFonte}>
          Desconectar
        </Botao>
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
