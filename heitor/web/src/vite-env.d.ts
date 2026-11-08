/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Endereço da API (ex.: http://localhost:8000). Vazio = interface com dados simulados (mock.ts). */
  readonly VITE_API_URL?: string;
  readonly VITE_EMPRESA?: string;
  /** Link da planilha do Google que o vigia observa (botão "abrir a planilha"). */
  readonly VITE_URL_PLANILHA?: string;
  readonly VITE_CONTA_SERVICO?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
