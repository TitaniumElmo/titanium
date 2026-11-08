import { acoes, useMundo } from "../api";
import { Cartao } from "../componentes/base";
import { PainelDemo } from "../componentes/ControlesDemo";
import { Pagina } from "../componentes/Pagina";
import type { Configuracao } from "../tipos";

const CLASSE_CAMPO =
  "h-10 w-28 rounded-controle border border-borda bg-superficie-2 px-3 font-mono text-sm text-texto focus:border-acento focus:outline-none";

function CampoNumero({
  rotulo,
  ajuda,
  chave,
  unidade,
  minimo,
  maximo,
}: {
  rotulo: string;
  ajuda: string;
  chave: keyof Omit<Configuracao, "canal_aviso">;
  unidade: string;
  minimo: number;
  maximo: number;
}) {
  const mundo = useMundo();
  return (
    <label className="flex flex-wrap items-center justify-between gap-3 border-t border-borda py-4 first:border-t-0 first:pt-0">
      <span className="min-w-0">
        <span className="block text-sm">{rotulo}</span>
        <span className="block text-xs text-fraco">{ajuda}</span>
      </span>
      <span className="flex items-center gap-2">
        <input
          type="number"
          className={CLASSE_CAMPO}
          min={minimo}
          max={maximo}
          value={mundo.config[chave]}
          onChange={(e) => {
            const valor = Number(e.target.value);
            if (Number.isFinite(valor) && valor >= minimo && valor <= maximo) acoes.atualizarConfig({ [chave]: valor });
          }}
        />
        <span className="w-14 text-sm text-apoio">{unidade}</span>
      </span>
    </label>
  );
}

export function Configuracoes() {
  const mundo = useMundo();
  return (
    <Pagina titulo="Configurações">
      <Cartao className="max-w-2xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-borda pb-4">
          <span className="min-w-0">
            <span className="block text-sm">Canal do aviso ao técnico</span>
            <span className="block text-xs text-fraco">Pendências e cobranças chegam por aqui</span>
          </span>
          <span className="rounded-controle bg-superficie-2 px-3 py-2 text-label">{mundo.config.canal_aviso}</span>
        </div>
        <div className="pt-4">
          <CampoNumero
            rotulo="Prazo padrão das pendências"
            ajuda="Quantos dias o técnico ou o RH têm para responder"
            chave="prazo_padrao_dias"
            unidade="dias"
            minimo={1}
            maximo={60}
          />
          <CampoNumero
            rotulo="Antecedência do aviso de troca"
            ajuda="Conforme a durabilidade indicada pelo fabricante"
            chave="antecedencia_troca_dias"
            unidade="dias"
            minimo={1}
            maximo={90}
          />
          <CampoNumero
            rotulo="Intervalo de leitura da planilha"
            ajuda="De quanto em quanto tempo o agente confere a planilha"
            chave="intervalo_leitura_s"
            unidade="seg."
            minimo={5}
            maximo={3600}
          />
        </div>
      </Cartao>

      <Cartao className="max-w-2xl">
        <h2 className="text-label">Controles da demo</h2>
        <p className="mb-4 mt-0.5 text-xs text-fraco">Só para o time. Também abre com Ctrl+Shift+D em qualquer página.</p>
        <PainelDemo />
      </Cartao>
    </Pagina>
  );
}
