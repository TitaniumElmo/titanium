export type Gravidade = "irregular" | "risco" | "ok";
export type TipoAchado = "corrigivel" | "prova" | "passivo";
export type Destino = "tecnico" | "rh";
export type StatusPendencia = "aberta" | "aguardando" | "fechada" | "reaberta";
export type Ator = "agente" | "tecnico" | "rh";
export type Prioridade = "normal" | "alta";

export type Gatilho =
  | "alteracao_planilha"
  | "upload"
  | "manual"
  | "prazo_vencido"
  | "vencimento_futuro"
  | "nova_base_caepi"
  | "email"
  | "funcionario_novo"
  | "rotina";

export type Etapa =
  | "encontrar"
  | "buscar_prova"
  | "pedir_correcao"
  | "corrigir"
  | "comprovar"
  | "conferir"
  | "cobrar_atraso";

export type Ferramenta =
  | "ler_fonte"
  | "mapear_colunas"
  | "extrair_ficha"
  | "reextrair_campo"
  | "consulta_ca"
  | "buscar_ca_proximo"
  | "exigencia_funcao"
  | "audita_linha"
  | "calcula_exposicao"
  | "criar_pendencia"
  | "fechar_pendencia"
  | "cobrar_atraso"
  | "gerar_relatorio"
  | "auditar_ficha"
  | "conferir_ficha_de_papel"
  | "historico_da_empresa"
  | "edicao_detectada";

export type TipoEvento = "ferramenta" | "decisao" | "erro";
export type ErroAgente = "modelo_indisponivel" | "resposta_invalida" | "pendencia_recusada";
export type ModoAuditoria = "llm" | "misto" | "deterministico";

export type Linha = {
  funcionario_id: string;
  nome: string;
  funcao: string;
  linha: number;
  data: string;
  epi: string;
  qtd: number;
  ca: string | null;
  motivo: string;
  assinatura: boolean | null;
  confianca: Record<string, number>;
  origem: string;
  na_ficha?: boolean | null;
};

export type ForaDaPlanilha = { funcionario_id: string; data: string; epi: string };

export type Achado = {
  id: string;
  funcionario_id: string;
  nome: string;
  funcao: string;
  linha: number;
  regra: string;
  gravidade: Gravidade;
  tipo: TipoAchado;
  evidencia: string;
  acao_sugerida: string;
  auditoria_id: string;
  ts: string;
  exposicao?: number;
};

export type EntradaHistorico = {
  etapa: Etapa;
  ator: Ator;
  ts: string;
  detalhe: string;
};

export type Pendencia = {
  id: string;
  achado_id: string;
  funcionario_id: string;
  funcionario_nome: string;
  destino: Destino;
  acao: string;
  motivo: string;
  prazo: string;
  status: StatusPendencia;
  historico: EntradaHistorico[];
  disparado_por: Gatilho;
  cobrancas: number;
  escalada: boolean;
  prioridade: Prioridade;
};

export type SaidaEvento = { resumo: string; pensamento?: string; erro?: string } & Record<string, unknown>;

export type Evento = {
  auditoria_id: string;
  funcionario_id?: string | null;
  passo: number;
  tipo: TipoEvento;
  ferramenta: Ferramenta | ErroAgente | null;
  entrada: Record<string, unknown>;
  saida: SaidaEvento;
  custo_usd: number;
  ts: string;
};

export type ColunaMapeada = { coluna: string; campo: string; confianca: number };

export type Fonte = {
  id: string;
  url: string;
  empresa: string;
  tipo: "planilha" | "pasta";
  status: "conectada" | "lendo" | "erro";
  ultima_leitura: string | null;
  mapeamento: ColunaMapeada[];
  intervalo_s: number;
  proxima_leitura: string;
};

export type StatusAuditoria = "processando" | "concluida" | "erro";

export type Auditoria = {
  id: string;
  fonte_id: string;
  status: StatusAuditoria;
  iniciada_em: string;
  contagem: { irregular: number; risco: number; ok: number };
  exposicao_total: number;
  disparado_por: Gatilho;
  descricao_disparo: string;
  n_fichas: number;
  modo?: ModoAuditoria;
  modo_por_funcionario?: Record<string, "llm" | "degradado">;
};

export type ItemAtividade = {
  id: string;
  ts: string;
  disparado_por: Gatilho;
  resumo: string;
  auditoria_id: string;
  pendencias_abertas: string[];
  pendencias_fechadas: string[];
};

export type Funcionario = {
  funcionario_id: string;
  nome: string;
  funcao: string;
  status: Gravidade;
  achados_abertos: number;
  pendencias_abertas: number;
  ultima_entrega: string;
  proxima_troca: string;
};

export type Configuracao = {
  canal_aviso: string;
  prazo_padrao_dias: number;
  antecedencia_troca_dias: number;
  intervalo_leitura_s: number;
};

export type TipoCronograma = "troca_epi" | "ca_vencendo" | "treinamento" | "dds" | "prazo_pendencia";
export type StatusCronograma = "previsto" | "atrasado" | "feito";

export type ItemCronograma = {
  id: string;
  tipo: TipoCronograma;
  funcionario_id: string | null;
  nome: string | null;
  funcao: string | null;
  titulo: string;
  descricao?: string;
  afetados?: string[];
  data: string;
  status: StatusCronograma;
  origem: "agente";
  pendencia_id: string | null;
};

export type Relatorio = {
  serie: { data: string; irregular: number; risco: number; ok: number }[];
  por_tipo: Record<TipoAchado, number>;
  pendencias: { abertas: number; fechadas: number; reabertas: number; tempo_medio_dias: number };
  exposicao_total: number;
  exposicao_por_funcao: { funcao: string; valor: number }[];
  custo_medio_ficha_usd: number;
  passos_medios: number;
  acerto: { precisao: number; recall: number } | null;
};
