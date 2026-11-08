import { useCallback, useState } from "react";
import { gravarArmazenado, lerArmazenado } from "./util";

export type Tema = "claro" | "escuro";

const CHAVE_TEMA = "elmo-tema";

function temaInicial(): Tema {
  const salvo = lerArmazenado(CHAVE_TEMA);
  return salvo === "claro" || salvo === "escuro" ? salvo : "escuro";
}

export function useTema() {
  const [tema, setTema] = useState<Tema>(temaInicial);
  
  const alternar = useCallback(() => {
    setTema((atual) => {
      const novo: Tema = atual === "escuro" ? "claro" : "escuro";
      document.documentElement.dataset.tema = novo;
      gravarArmazenado(CHAVE_TEMA, novo);
      return novo;
    });
  }, []);

  return { tema, alternar };
}
