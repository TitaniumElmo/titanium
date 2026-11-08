import { useCallback, useEffect, useState } from "react";
import { gravarArmazenado, lerArmazenado } from "./util";

export type Tema = "claro" | "escuro";

const CHAVE_TEMA = "elmo-tema";

function temaDoSistema(): Tema {
  if (typeof window === "undefined" || !window.matchMedia) return "escuro";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "claro" : "escuro";
}

function temaInicial(): Tema {
  const salvo = lerArmazenado(CHAVE_TEMA);
  return salvo === "claro" || salvo === "escuro" ? salvo : temaDoSistema();
}

export function useTema() {
  const [tema, setTema] = useState<Tema>(temaInicial);
  const [escolhido, setEscolhido] = useState(() => lerArmazenado(CHAVE_TEMA) !== null);

  useEffect(() => {
    if (escolhido) return;
    const consulta = window.matchMedia("(prefers-color-scheme: light)");
    const aoMudar = () => setTema(consulta.matches ? "claro" : "escuro");
    consulta.addEventListener("change", aoMudar);
    return () => consulta.removeEventListener("change", aoMudar);
  }, [escolhido]);

  const alternar = useCallback(() => {
    setTema((atual) => {
      const novo: Tema = atual === "escuro" ? "claro" : "escuro";
      document.documentElement.dataset.tema = novo;
      gravarArmazenado(CHAVE_TEMA, novo);
      return novo;
    });
    setEscolhido(true);
  }, []);

  return { tema, alternar };
}
