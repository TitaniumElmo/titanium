import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "@fontsource-variable/inter";
import "@fontsource-variable/archivo/wdth.css";
import "./index.css";

const raiz = document.getElementById("raiz");
if (!raiz) throw new Error("elemento #raiz ausente");

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
