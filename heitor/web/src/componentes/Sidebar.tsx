import { useEffect, useState, type ComponentType, type SVGProps } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useEstado } from "../estado";
import { useTema } from "../tema";
import {
  cn,
  IconeAjustes,
  IconeAlerta,
  IconeAtividade,
  IconeCalendario,
  IconeCasa,
  IconeDocumento,
  IconeFechar,
  IconeGrade,
  IconeLista,
  IconeLua,
  IconeMenu,
  IconeOlho,
  IconePessoas,
  IconeSol,
  IconeTomada,
} from "../util";
import { LogoCompleta } from "./Logo";

type ItemNavegacao = {
  rota: string;
  rotulo: string;
  icone: ComponentType<SVGProps<SVGSVGElement>>;
  marcador?: "ao-vivo" | "contador";
};

type GrupoNavegacao = { titulo?: string; itens: ItemNavegacao[] };

const GRUPOS: GrupoNavegacao[] = [
  { itens: [{ rota: "/", rotulo: "Início", icone: IconeCasa }] },
  {
    titulo: "Auditoria",
    itens: [
      { rota: "/agente", rotulo: "Agente ao vivo", icone: IconeOlho, marcador: "ao-vivo" },
      { rota: "/achados", rotulo: "Achados", icone: IconeAlerta },
      { rota: "/pendencias", rotulo: "Pendências", icone: IconeLista, marcador: "contador" },
      { rota: "/historico", rotulo: "Histórico", icone: IconeAtividade },
    ],
  },
  {
    titulo: "Equipe",
    itens: [
      { rota: "/funcionarios", rotulo: "Funcionários", icone: IconePessoas },
      { rota: "/cronograma", rotulo: "Cronograma", icone: IconeCalendario },
    ],
  },
  {
    titulo: "Relatórios",
    itens: [
      { rota: "/visao-geral", rotulo: "Visão geral", icone: IconeGrade },
      { rota: "/relatorio", rotulo: "Relatório", icone: IconeDocumento },
    ],
  },
];

const RODAPE: ItemNavegacao[] = [
  { rota: "/fontes", rotulo: "Fontes conectadas", icone: IconeTomada },
  { rota: "/configuracoes", rotulo: "Configurações", icone: IconeAjustes },
];

function LinkNavegacao({ item }: { item: ItemNavegacao }) {
  const { pendenciasAbertas, auditoriaRodando } = useEstado();
  const Icone = item.icone;
  return (
    <NavLink
      to={item.rota}
      end={item.rota === "/"}
      className={({ isActive }) =>
        cn(
          "group flex h-9 items-center gap-3 rounded-controle px-3 text-sm font-medium transition-colors",
          isActive ? "bg-acento-suave text-acento" : "text-apoio hover:bg-superficie-2 hover:text-texto",
        )
      }
    >
      <Icone className="size-4 shrink-0" />
      <span className="flex-1 truncate">{item.rotulo}</span>
      {item.marcador === "ao-vivo" && auditoriaRodando && (
        <span className="animar-pulsar size-2 rounded-full bg-acento" aria-label="auditoria rodando" />
      )}
      {item.marcador === "contador" && pendenciasAbertas > 0 && (
        <span className="min-w-5 rounded-full bg-superficie-2 px-1.5 text-center font-mono text-xs leading-5 text-texto">
          {pendenciasAbertas}
        </span>
      )}
    </NavLink>
  );
}

function BotaoTema() {
  const { tema, alternar } = useTema();
  const escuro = tema === "escuro";
  return (
    <button
      type="button"
      onClick={alternar}
      className="flex h-9 w-full items-center gap-3 rounded-controle px-3 text-sm font-medium text-apoio transition-colors hover:bg-superficie-2 hover:text-texto"
    >
      {escuro ? <IconeSol className="size-4" /> : <IconeLua className="size-4" />}
      <span>{escuro ? "Tema claro" : "Tema escuro"}</span>
    </button>
  );
}

function ConteudoSidebar() {
  return (
    <div className="flex h-full flex-col gap-6 px-3 py-5">
      <div className="px-2">
        <LogoCompleta />
      </div>
      <nav className="flex flex-1 flex-col gap-5 overflow-y-auto" aria-label="Navegação principal">
        {GRUPOS.map((grupo, i) => (
          <div key={grupo.titulo ?? i} className="flex flex-col gap-0.5">
            {grupo.titulo && (
              <span className="mb-1 px-3 text-xs font-medium text-fraco">
                {grupo.titulo}
              </span>
            )}
            {grupo.itens.map((item) => (
              <LinkNavegacao key={item.rota} item={item} />
            ))}
          </div>
        ))}
      </nav>
      <div className="flex flex-col gap-0.5 border-t border-borda pt-4">
        {RODAPE.map((item) => (
          <LinkNavegacao key={item.rota} item={item} />
        ))}
        <BotaoTema />
      </div>
    </div>
  );
}

export function Sidebar() {
  const [aberta, setAberta] = useState(false);
  const local = useLocation();

  useEffect(() => setAberta(false), [local.pathname]);

  useEffect(() => {
    if (!aberta) return;
    const aoTeclar = (e: KeyboardEvent) => e.key === "Escape" && setAberta(false);
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [aberta]);

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-borda bg-superficie menu:block">
        <ConteudoSidebar />
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-borda bg-superficie/90 px-4 backdrop-blur menu:hidden">
        <LogoCompleta comSubtitulo={false} />
        <button
          type="button"
          onClick={() => setAberta(true)}
          className="flex size-9 items-center justify-center rounded-controle text-apoio hover:bg-superficie-2"
          aria-label="Abrir menu"
          aria-expanded={aberta}
        >
          <IconeMenu className="size-5" />
        </button>
      </header>

      {aberta && (
        <div className="fixed inset-0 z-40 menu:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            className="absolute inset-0 bg-fundo/70 backdrop-blur-sm"
            aria-label="Fechar menu"
            onClick={() => setAberta(false)}
          />
          <aside className="animar-entrar absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-borda bg-superficie">
            <button
              type="button"
              onClick={() => setAberta(false)}
              className="absolute right-3 top-4 flex size-9 items-center justify-center rounded-controle text-apoio hover:bg-superficie-2"
              aria-label="Fechar menu"
            >
              <IconeFechar className="size-5" />
            </button>
            <ConteudoSidebar />
          </aside>
        </div>
      )}
    </>
  );
}
