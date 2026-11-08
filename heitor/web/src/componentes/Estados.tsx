import { Component, type ReactNode } from "react";
import { Botao } from "./base";

export function Carregando({ rotulo = "Carregando" }: { rotulo?: string }) {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8" aria-busy="true" aria-live="polite">
      <span className="sr-only">{rotulo}</span>
      <div className="h-9 w-48 animate-pulse rounded-controle bg-superficie-2" />
      <div className="h-72 animate-pulse rounded-cartao border border-borda bg-superficie" />
      <div className="grid gap-4 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-40 animate-pulse rounded-cartao border border-borda bg-superficie" />
        ))}
      </div>
    </div>
  );
}

type Estado = { erro: Error | null };

export class LimiteDeErro extends Component<{ children: ReactNode; chave: string }, Estado> {
  state: Estado = { erro: null };

  static getDerivedStateFromError(erro: Error): Estado {
    return { erro };
  }

  componentDidUpdate(anterior: { chave: string }) {
    if (anterior.chave !== this.props.chave && this.state.erro) this.setState({ erro: null });
  }

  render() {
    if (!this.state.erro) return this.props.children;
    return (
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-6 sm:px-8 sm:py-8">
        <div role="alert" className="rounded-cartao border border-irregular-borda/40 bg-irregular-fundo p-5">
          <h1 className="text-h3 text-irregular">Esta tela não carregou</h1>
          <p className="mt-1 text-sm text-apoio">
            O agente continua trabalhando. Tente de novo; se repetir, recarregue a página.
          </p>
          <p className="mt-2 font-mono text-xs text-fraco">{this.state.erro.message}</p>
          <Botao className="mt-4" onClick={() => this.setState({ erro: null })}>
            Tentar de novo
          </Botao>
        </div>
      </div>
    );
  }
}
