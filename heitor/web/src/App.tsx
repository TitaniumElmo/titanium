import { lazy, Suspense, useState, type ReactNode } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Carregando, LimiteDeErro } from "./componentes/Estados";
import { IntroElmo } from "./componentes/IntroElmo";
import { AvisoConferindo } from "./componentes/AvisoConferindo";
import { ControlesDemo, FaixaDemo } from "./componentes/ControlesDemo";
import { Sidebar } from "./componentes/Sidebar";
import { ProvedorEstado } from "./estado";
import { Achados } from "./paginas/Achados";
import { AgenteAoVivo } from "./paginas/AgenteAoVivo";
import { Historico } from "./paginas/Historico";
import { Inicio } from "./paginas/Inicio";
import { Configuracoes } from "./paginas/Configuracoes";
import { Cronograma } from "./paginas/Cronograma";
import { FichaFuncionario } from "./paginas/FichaFuncionario";
import { Fontes } from "./paginas/Fontes";
import { Funcionarios } from "./paginas/Funcionarios";
import { NaoEncontrada } from "./paginas/NaoEncontrada";
import { Pendencias } from "./paginas/Pendencias";
import { VisaoGeral } from "./paginas/VisaoGeral";

const Relatorio = lazy(() => import("./paginas/Relatorio").then((m) => ({ default: m.Relatorio })));

function Conteudo({ children }: { children: ReactNode }) {
  const local = useLocation();
  return (
    <LimiteDeErro chave={local.pathname}>
      <Suspense fallback={<Carregando />}>{children}</Suspense>
    </LimiteDeErro>
  );
}

export function App() {
  const [intro, setIntro] = useState(true);
  return (
    <BrowserRouter>
      {intro && <IntroElmo aoTerminar={() => setIntro(false)} />}
      <ProvedorEstado>
        <Sidebar />
        <main className="min-h-dvh menu:pl-60">
          <FaixaDemo />
          <AvisoConferindo />
          <Conteudo>
          <Routes>
            <Route path="/" element={<Inicio />} />
            <Route path="/historico" element={<Historico />} />
            <Route path="/agente" element={<AgenteAoVivo />} />
            <Route path="/achados" element={<Achados />} />
            <Route path="/pendencias" element={<Pendencias />} />
            <Route path="/funcionarios" element={<Funcionarios />} />
            <Route path="/funcionarios/:id" element={<FichaFuncionario />} />
            <Route path="/cronograma" element={<Cronograma />} />
            <Route path="/visao-geral" element={<VisaoGeral />} />
            <Route path="/relatorio" element={<Relatorio />} />
            <Route path="/fontes" element={<Fontes />} />
            <Route path="/configuracoes" element={<Configuracoes />} />
            <Route path="*" element={<NaoEncontrada />} />
          </Routes>
          </Conteudo>
        </main>
        <ControlesDemo />
      </ProvedorEstado>
    </BrowserRouter>
  );
}
