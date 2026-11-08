import { useEffect, useRef, useState } from "react";
import { dolares } from "../formato";
import type { Evento } from "../tipos";
import { cn } from "../util";
import { CABINES, type Cabine, ContornoAtivo, Divisorias, Escurecimento, FundoCabines, NumeroDoChao, PlacaCabine } from "./Cabines";
import { larguraTexto, TextoPixel } from "./TextoPixel";

const LARGURA = 540;
const ALTURA = 180;
const PES_CORREDOR = 174;
const PES_MESA = 138;
const ESPERA_OCIOSA_MS = 3000;
const DISTANCIA_MINIMA = 40;
const TOLERANCIA_FILEIRA = 20;
const PASSO_AO_LADO = 42;
const LIMITE_ESQUERDO = 24;
const LIMITE_DIREITO = 514;
const ENTRADA_ELMOS = [26, 74, 122];
const PORTA_E = 478;
const PORTA_D = 395;
const LUGAR_ENGENHEIRO = 377;
const MESA_TECNICA = 420;
const PES_TECNICA_MESA = 134;
const SAIDA_MESA = 466;
const LADO_OPERARIA = 478;
const POSICAO_OPERARIA = 518;
const POSICAO_RH = 340;
const TEXTO_AGUARDANDO = "AGUARDANDO:\ncorreção na planilha";
const RECORTE_MESA_D = "inset(88px 78px 40px 404px)";
const ENGENHEIRO_PRESENTE_MS = 4000;
const ELMOS = ["elmo0", "elmo1", "elmo2"] as const;

const URLS = import.meta.glob("../assets/cenario/**/*.png", { eager: true, query: "?url", import: "default" }) as Record<
  string,
  string
>;

function arte(caminho: string): string {
  return URLS[`../assets/cenario/${caminho}`] ?? "";
}

const PONTO_ELMO: Record<Cabine, number> = { A: 100, B: 180, C: 260, F: 340, D: 420, E: PORTA_E };

type Personagem =
  | "01_elmo"
  | "03_tecnica_cacheada"
  | "04_operaria"
  | "05_operaria_protetor_ficha"
  | "06_engenheiro"
  | "07_assistente_rh"
  | "08_operaria_protetor";

const LARGURA_SPRITE: Record<Personagem, number> = {
  "01_elmo": 58,
  "03_tecnica_cacheada": 75,
  "04_operaria": 60,
  "05_operaria_protetor_ficha": 68,
  "06_engenheiro": 56,
  "07_assistente_rh": 78,
  "08_operaria_protetor": 60,
};

const PES_SPRITE: Record<Personagem, number> = {
  "01_elmo": 72,
  "03_tecnica_cacheada": 72,
  "04_operaria": 72,
  "05_operaria_protetor_ficha": 72,
  "06_engenheiro": 72,
  "07_assistente_rh": 75,
  "08_operaria_protetor": 72,
};

type EstadoOperaria = "trabalhando" | "assinando" | "protegida";
const SPRITE_OPERARIA: Record<EstadoOperaria, Personagem> = {
  trabalhando: "04_operaria",
  assinando: "05_operaria_protetor_ficha",
  protegida: "08_operaria_protetor",
};

function quadros(p: Personagem) {
  return {
    parado: [arte(`personagens/${p}/idle_1.png`), arte(`personagens/${p}/idle_2.png`)],
    piscando: arte(`personagens/${p}/blink.png`),
    andando: [1, 2, 3, 4].map((i) => arte(`personagens/${p}/walk_${i}.png`)),
  };
}

type Ator = {
  personagem: Personagem;
  x: number;
  pesY: number;
  deX: number;
  alvoX: number;
  dePes: number;
  alvoPes: number;
  atras: boolean;
  t0: number;
  duracao: number;
  andando: boolean;
  direcao: 1 | -1;
  fase: number;
  visivel: boolean;
  aoChegar?: () => void;
};

type Selo = { id: number; tipo: "ok" | "alerta" | "erro" };

function cabineDoEvento(e: Evento): Cabine | null {
  if (e.tipo !== "ferramenta") return null;
  switch (e.ferramenta) {
    case "ler_fonte":
    case "mapear_colunas":
    case "extrair_ficha":
    case "reextrair_campo":
    case "historico_da_empresa":
      return "A";
    case "consulta_ca":
    case "buscar_ca_proximo":
    case "exigencia_funcao":
    case "audita_linha":
    case "auditar_ficha":
    case "calcula_exposicao":
    case "gerar_relatorio":
      return "B";
    case "conferir_ficha_de_papel":
      return "C";
    case "criar_pendencia":
      return e.entrada.destino === "rh" ? "F" : "D";
    case "cobrar_atraso":
      return "D";
    case "fechar_pendencia":
      return "E";
    default:
      return null;
  }
}

function seloDoEvento(e: Evento): Selo["tipo"] {
  const r = e.saida.resumo.toLowerCase();
  if (r.includes("não localizada") || r.includes("sem assinatura")) return "erro";
  if (r.includes("dúvida")) return "alerta";
  return "ok";
}

function textoBalao(e: Evento): string {
  let t: string;
  if (e.tipo === "decisao") t = `PENSANDO: ${e.saida.pensamento ?? e.saida.resumo}`;
  else if (e.tipo === "erro") t = e.ferramenta === "modelo_indisponivel" ? "⚠️ MODO DEGRADADO: seguindo pelas regras" : `⚠️ ${e.saida.resumo}`;
  else t = `${e.ferramenta}: ${e.saida.resumo}`;
  return t.length > 48 ? `${t.slice(0, 47)}…` : t;
}

function ehAuditoria(e: Evento): boolean {
  return e.tipo === "ferramenta" && (e.ferramenta === "auditar_ficha" || e.ferramenta === "audita_linha");
}

function nivelBandeja(auditadas: number): number {
  if (auditadas <= 0) return 0;
  if (auditadas <= 2) return 1;
  if (auditadas <= 4) return 2;
  return 3;
}

function useEscuro(): boolean {
  const ler = () => {
    return document.documentElement.dataset.tema !== "claro";
  };
  const [escuro, setEscuro] = useState(ler);
  useEffect(() => {
    const atualizar = () => setEscuro(ler());
    const obs = new MutationObserver(atualizar);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-tema"] });
    return () => {
      obs.disconnect();
    };
  }, []);
  return escuro;
}

function Img({ src, x, y, z = 2, className }: { src: string; x: number; y: number; z?: number; className?: string }) {
  return (
    <img
      src={src}
      alt=""
      draggable={false}
      className={cn("pointer-events-none absolute select-none", className)}
      style={{ left: x, top: y, zIndex: z, imageRendering: "pixelated" }}
    />
  );
}

export function CenaEscritorio({
  chave,
  eventos,
  rodando,
  fichasNaPilha,
  urgente,
  aguardandoCorrecao,
  progressoLeitura,
  deslocamento,
  className,
}: {
  chave: string;
  eventos: Evento[];
  rodando: boolean;
  fichasNaPilha: number;
  urgente: boolean;
  aguardandoCorrecao: boolean;
  progressoLeitura: number;
  deslocamento: number;
  className?: string;
}) {
  const escuro = useEscuro();
  const caixa = useRef<HTMLDivElement>(null);
  const [escala, setEscala] = useState(2);
  const semMovimento = useRef(false);

  const [cabineAtiva, setCabineAtiva] = useState<Cabine | null>(null);
  const [gaveta, setGaveta] = useState(false);
  const [auditadas, setAuditadas] = useState(0);
  const [selos, setSelos] = useState<Selo[]>([]);
  const [porta, setPorta] = useState(false);
  const [estadoOperaria, setEstadoOperaria] = useState<EstadoOperaria>("trabalhando");
  const [pegas, setPegas] = useState(0);
  const [giro, setGiro] = useState(0);
  const [relogioRapido, setRelogioRapido] = useState(0);

  const atores = useRef<Record<string, Ator>>({});
  const elementos = useRef<Record<string, HTMLImageElement | null>>({});
  const balao = useRef<HTMLDivElement>(null);
  const textoBalaoRef = useRef<HTMLSpanElement>(null);
  const fila = useRef<Evento[]>([]);
  const vistos = useRef<{ chave: string; total: number; funcionarios: Set<string> }>({ chave: "", total: 0, funcionarios: new Set() });
  const ultimaAtividade = useRef(0);
  const esperando = useRef(true);
  const timers = useRef<number[]>([]);
  const elmoDoFuncionario = useRef<Map<string, number>>(new Map());
  const elmoDoBalao = useRef(0);
  const aguardando = useRef(aguardandoCorrecao);
  const tecnicaFora = useRef(false);
  aguardando.current = aguardandoCorrecao;

  const depois = (ms: number, fn: () => void) => {
    timers.current.push(window.setTimeout(fn, semMovimento.current ? 0 : ms));
  };

  if (Object.keys(atores.current).length === 0) {
    const novo = (personagem: Personagem, x: number, pesY = PES_CORREDOR, opcoes: { visivel?: boolean; atras?: boolean } = {}): Ator => ({
      personagem,
      x,
      pesY,
      deX: x,
      alvoX: x,
      dePes: pesY,
      alvoPes: pesY,
      atras: opcoes.atras ?? false,
      t0: 0,
      duracao: 0,
      andando: false,
      direcao: 1,
      fase: Math.random() * 4000,
      visivel: opcoes.visivel ?? true,
    });
    atores.current = {
      rh: novo("07_assistente_rh", POSICAO_RH, PES_MESA),
      tecnica: novo("03_tecnica_cacheada", MESA_TECNICA, PES_TECNICA_MESA, { atras: true }),
      operaria: novo("04_operaria", POSICAO_OPERARIA),
      engenheiro: novo("06_engenheiro", PORTA_D, PES_MESA + 2, { visivel: false }),
      elmo0: novo("01_elmo", ENTRADA_ELMOS[0] ?? 22),
      elmo1: novo("01_elmo", ENTRADA_ELMOS[1] ?? 58),
      elmo2: novo("01_elmo", ENTRADA_ELMOS[2] ?? 94),
    };
    const operaria = atores.current.operaria;
    if (operaria) operaria.direcao = -1;
  }

  const mover = (id: string, alvo: number, aoChegar?: () => void, pes?: number) => {
    const a = atores.current[id];
    if (!a) return;
    const agora = performance.now();
    a.deX = a.x;
    a.alvoX = alvo;
    a.dePes = a.pesY;
    a.alvoPes = pes ?? a.pesY;
    a.t0 = agora;
    const distancia = Math.hypot(alvo - a.x, a.alvoPes - a.pesY);
    a.duracao = semMovimento.current || distancia < 1 ? 0 : Math.min(1100, Math.max(320, (distancia / 150) * 1000));
    if (Math.abs(alvo - a.x) >= 1) a.direcao = alvo > a.x ? 1 : -1;
    a.andando = true;
    a.aoChegar = aoChegar;
  };

  const posicoesDosOutros = (id: string) =>
    Object.entries(atores.current)
      .filter(([outro, a]) => outro !== id && a.visivel && Math.abs(a.pesY - (atores.current[id]?.pesY ?? PES_CORREDOR)) < TOLERANCIA_FILEIRA)
      .map(([, a]) => (a.andando ? a.alvoX : a.x));

  const livre = (id: string, desejado: number) => {
    const outros = posicoesDosOutros(id);
    for (let i = 0; i < 16; i++) {
      const candidato = desejado + Math.ceil(i / 2) * PASSO_AO_LADO * (i % 2 ? 1 : -1);
      if (candidato < LIMITE_ESQUERDO || candidato > LIMITE_DIREITO) continue;
      if (outros.every((o) => Math.abs(o - candidato) >= DISTANCIA_MINIMA)) return candidato;
    }
    return desejado;
  };

  const desobstruir = (primeiro?: string) => {
    const ordem = primeiro && ELMOS.some((e) => e === primeiro) ? [primeiro, ...ELMOS.filter((e) => e !== primeiro)] : ELMOS;
    for (const id of ordem) {
      const a = atores.current[id];
      if (!a || !a.visivel || a.andando) continue;
      const colide = posicoesDosOutros(id).some((o) => Math.abs(o - a.x) < DISTANCIA_MINIMA);
      if (!colide) continue;
      const destino = livre(id, a.x);
      if (Math.abs(destino - a.x) >= 1) mover(id, destino);
    }
  };

  const moverElmo = (indice: number, alvo: number) => {
    const id = ELMOS[indice] ?? "elmo0";
    mover(id, livre(id, alvo));
  };

  const elmoDoEvento = (e: Evento) => {
    if (!e.funcionario_id) return elmoDoBalao.current;
    const mapa = elmoDoFuncionario.current;
    let indice = mapa.get(e.funcionario_id);
    if (indice === undefined) {
      indice = mapa.size % ELMOS.length;
      mapa.set(e.funcionario_id, indice);
    }
    return indice;
  };

  const algumElmoAndando = () => ELMOS.some((id) => atores.current[id]?.andando);

  const mostrarBalao = (texto: string | null) => {
    if (textoBalaoRef.current) textoBalaoRef.current.textContent = texto ?? "";
    if (balao.current) balao.current.dataset.visivel = texto ? "sim" : "nao";
  };

  const posicionarOcioso = (teletransportar: boolean) => {
    elmoDoBalao.current = 0;
    ELMOS.forEach((id, indice) => {
      const alvo = indice === 0 && aguardando.current ? PORTA_E : (ENTRADA_ELMOS[indice] ?? 22);
      const a = atores.current[id];
      if (!a) return;
      if (teletransportar) {
        a.x = alvo;
        a.alvoX = alvo;
        a.andando = false;
        a.direcao = 1;
      } else {
        mover(id, alvo);
      }
    });
    mostrarBalao(aguardando.current ? TEXTO_AGUARDANDO : null);
  };

  const historiaDoCanteiro = () => {
    const tecnica = atores.current.tecnica;
    if (!tecnica || tecnicaFora.current) return;
    tecnicaFora.current = true;
    mover(
      "tecnica",
      SAIDA_MESA,
      () => {
        tecnica.atras = false;
        mover(
          "tecnica",
          LADO_OPERARIA,
          () =>
            depois(600, () => {
              setEstadoOperaria("assinando");
              depois(1800, () => {
                setEstadoOperaria("protegida");
                mover(
                  "tecnica",
                  SAIDA_MESA,
                  () => {
                    tecnica.atras = true;
                    mover(
                      "tecnica",
                      MESA_TECNICA,
                      () => {
                        tecnica.direcao = 1;
                        tecnicaFora.current = false;
                      },
                      PES_TECNICA_MESA,
                    );
                  },
                  PES_MESA,
                );
              });
            }),
          PES_CORREDOR,
        );
      },
      PES_MESA,
    );
  };

  const escalada = () => {
    const eng = atores.current.engenheiro;
    if (!eng || eng.visivel) return;
    setPorta(true);
    depois(300, () => {
      eng.visivel = true;
      eng.x = PORTA_D;
      eng.pesY = PES_MESA + 2;
      eng.andando = false;
      mover(
        "engenheiro",
        LUGAR_ENGENHEIRO,
        () =>
          depois(ENGENHEIRO_PRESENTE_MS, () =>
            mover(
              "engenheiro",
              PORTA_D,
              () => {
                eng.visivel = false;
                depois(250, () => setPorta(false));
              },
              PES_MESA + 2,
            ),
          ),
        PES_CORREDOR,
      );
    });
  };

  const processar = (e: Evento) => {
    ultimaAtividade.current = performance.now();
    esperando.current = false;
    if (e.funcionario_id && !vistos.current.funcionarios.has(e.funcionario_id)) {
      vistos.current.funcionarios.add(e.funcionario_id);
      setPegas((n) => n + 1);
    }
    const indice = elmoDoEvento(e);
    elmoDoBalao.current = indice;
    const cabine = cabineDoEvento(e);
    mostrarBalao(textoBalao(e));
    if (!cabine) return;
    setCabineAtiva(cabine);
    setGaveta(e.ferramenta === "historico_da_empresa");
    if (ehAuditoria(e)) setAuditadas((n) => n + 1);
    if (e.ferramenta === "conferir_ficha_de_papel") {
      setSelos((s) => [...s.slice(-2), { id: e.passo, tipo: seloDoEvento(e) }]);
    }
    if (e.ferramenta === "cobrar_atraso" && /escal/i.test(e.saida.resumo)) escalada();
    if (e.ferramenta === "fechar_pendencia") historiaDoCanteiro();
    moverElmo(indice, PONTO_ELMO[cabine]);
  };

  useEffect(() => {
    if (vistos.current.chave === chave) {
      if (eventos.length > vistos.current.total) {
        fila.current.push(...eventos.slice(vistos.current.total));
        vistos.current.total = eventos.length;
      }
      return;
    }
    const funcionarios = new Set(eventos.map((e) => e.funcionario_id).filter((f): f is string => Boolean(f)));
    vistos.current = { chave, total: eventos.length, funcionarios };
    fila.current = [];
    setAuditadas(eventos.filter(ehAuditoria).length);
    setSelos(
      eventos
        .filter((e) => e.ferramenta === "conferir_ficha_de_papel")
        .slice(-3)
        .map((e) => ({ id: e.passo, tipo: seloDoEvento(e) })),
    );
    setPegas(funcionarios.size || (eventos.length ? 1 : 0));
    setGaveta(false);
    const ultimo = eventos[eventos.length - 1];
    const cabine = rodando && ultimo ? cabineDoEvento(ultimo) : null;
    elmoDoFuncionario.current = new Map();
    setCabineAtiva(cabine);
    esperando.current = !cabine;
    ultimaAtividade.current = performance.now();
    posicionarOcioso(true);
    if (cabine && ultimo) {
      const indice = elmoDoEvento(ultimo);
      const id = ELMOS[indice] ?? "elmo0";
      const a = atores.current[id];
      if (a) {
        a.x = livre(id, PONTO_ELMO[cabine]);
        a.alvoX = a.x;
      }
      elmoDoBalao.current = indice;
      mostrarBalao(textoBalao(ultimo));
    }
  }, [chave, eventos, rodando]);

  useEffect(() => {
    if (esperando.current) posicionarOcioso(false);
  }, [aguardandoCorrecao]);

  useEffect(() => {
    if (!urgente || semMovimento.current) return;
    const id = window.setInterval(() => setGiro((g) => 1 - g), 150);
    return () => window.clearInterval(id);
  }, [urgente]);

  useEffect(() => {
    if (!deslocamento) return;
    setRelogioRapido(1);
    const id = window.setTimeout(() => setRelogioRapido(0), 1600);
    return () => window.clearTimeout(id);
  }, [deslocamento]);

  const [ponteiro, setPonteiro] = useState(0);
  useEffect(() => {
    if (!relogioRapido || semMovimento.current) {
      setPonteiro(Math.floor(progressoLeitura * 12) % 12);
      return;
    }
    const id = window.setInterval(() => setPonteiro((p) => (p + 1) % 12), 60);
    return () => window.clearInterval(id);
  }, [relogioRapido, progressoLeitura]);

  useEffect(() => {
    const el = caixa.current;
    if (!el) return;
    const ajustar = () => setEscala(el.clientWidth >= 600 ? 2 : 1);
    ajustar();
    const obs = new ResizeObserver(ajustar);
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    semMovimento.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let quadro = 0;
    const passo = (agora: number) => {
      const lista = atores.current;
      for (const [id, a] of Object.entries(lista)) {
        if (a.andando) {
          const t = a.duracao === 0 ? 1 : Math.min(1, (agora - a.t0) / a.duracao);
          a.x = a.deX + (a.alvoX - a.deX) * t;
          a.pesY = a.dePes + (a.alvoPes - a.dePes) * t;
          if (t >= 1) {
            a.andando = false;
            const fn = a.aoChegar;
            a.aoChegar = undefined;
            fn?.();
            desobstruir(id);
          }
        }
        const el = elementos.current[id];
        if (!el) continue;
        const personagem = id === "operaria" ? SPRITE_OPERARIA[(el.dataset.estado as EstadoOperaria | undefined) ?? "trabalhando"] : a.personagem;
        const q = quadros(personagem);
        const pisca = !semMovimento.current && (agora + a.fase) % 4200 < 140;
        const src = a.andando
          ? (q.andando[Math.floor(agora / 150) % 4] ?? q.parado[0])
          : pisca
            ? q.piscando
            : (q.parado[semMovimento.current ? 0 : Math.floor((agora + a.fase) / 700) % 2] ?? "");
        if (el.dataset.src !== src) {
          el.src = src ?? "";
          el.dataset.src = src ?? "";
        }
        const largura = LARGURA_SPRITE[personagem];
        el.style.transform = `translate(${Math.round(a.x - largura / 2)}px, ${a.pesY - PES_SPRITE[personagem]}px) scaleX(${a.direcao})`;
        el.style.visibility = a.visivel ? "visible" : "hidden";
        el.style.zIndex = id === "rh" ? "3" : a.atras ? "2" : "5";
      }

      if (!algumElmoAndando() && fila.current.length) {
        const proximo = fila.current.shift();
        if (proximo) processar(proximo);
      } else if (!algumElmoAndando() && !esperando.current && agora - ultimaAtividade.current > ESPERA_OCIOSA_MS) {
        esperando.current = true;
        setCabineAtiva(null);
        setGaveta(false);
        posicionarOcioso(false);
      }
      const elmo = lista[ELMOS[elmoDoBalao.current] ?? "elmo0"];
      if (elmo) {
        if (balao.current) {
          const largura = balao.current.offsetWidth;
          const esquerda = Math.min(Math.max(elmo.x - largura / 2, 2), LARGURA - largura - 2);
          balao.current.style.left = `${Math.round(esquerda)}px`;
        }
        const el = caixa.current;
        if (el && el.scrollWidth > el.clientWidth) {
          const desejado = elmo.x * (el.scrollWidth / LARGURA) - el.clientWidth / 2;
          el.scrollLeft += (desejado - el.scrollLeft) * (semMovimento.current ? 1 : 0.08);
        }
      }
      quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    const pendentes = timers.current;
    return () => {
      cancelAnimationFrame(quadro);
      pendentes.forEach((t) => window.clearTimeout(t));
    };
  }, []);

  const custos = eventos.map((e) => e.custo_usd);
  const total = custos.reduce((s, c) => s + c, 0);
  const restantes = Math.max(0, fichasNaPilha - (rodando ? pegas : 0));
  const textoContador = `${restantes} ${restantes === 1 ? "FICHA" : "FICHAS"}`;

  return (
    <div
      ref={caixa}
      className={cn(
        "relative overflow-x-auto overflow-y-hidden rounded-cartao border border-borda bg-log-fundo [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className,
      )}
      role="img"
      aria-label={`Cena do agente: ${cabineAtiva ? `trabalhando na cabine ${cabineAtiva}` : aguardandoCorrecao ? "aguardando a correção na porta do canteiro" : "esperando na entrada"}`}
    >
      <div className="relative mx-auto" style={{ width: LARGURA * escala, height: ALTURA * escala }}>
        <div className="absolute left-0 top-0 origin-top-left" style={{ width: LARGURA, height: ALTURA, transform: `scale(${escala})` }}>
          <Img src={arte(escuro ? "fundo_escuro.png" : "fundo_claro.png")} x={0} y={0} z={0} />
          <FundoCabines />
          {CABINES.map((c) => (
            <NumeroDoChao key={c.id} cabine={c.id} />
          ))}
          <Img src={arte("props_tras.png")} x={0} y={0} className={escuro ? "brightness-[.85]" : undefined} />
          {gaveta && <Img src={arte("estados/A_gaveta_aberta.png")} x={70} y={94} />}
          {nivelBandeja(auditadas) > 0 && <Img src={arte(`estados/B_bandeja_${nivelBandeja(auditadas)}.png`)} x={200} y={102} />}
          {cabineAtiva === "C" && <Img src={arte("estados/C_luminaria_acesa.png")} x={234} y={86} />}
          {porta && <Img src={arte("estados/D_porta_aberta.png")} x={385} y={69} />}
          <Img src={arte(`estados/D_relogio_ponteiro_${String(ponteiro).padStart(2, "0")}.png`)} x={422} y={42} />
          <img
            src={arte("props_tras.png")}
            alt=""
            draggable={false}
            className={cn("pointer-events-none absolute left-0 top-0 select-none", escuro && "brightness-[.85]")}
            style={{ zIndex: 3, clipPath: RECORTE_MESA_D, imageRendering: "pixelated" }}
          />
          {urgente && <Img src={arte(`estados/D_giroflex_${giro + 1}.png`)} x={431} y={99} z={3} />}

          {(["rh", "tecnica", "operaria", "engenheiro", ...ELMOS] as const).map((id) => (
            <img
              key={id}
              ref={(el) => {
                elementos.current[id] = el;
              }}
              data-estado={id === "operaria" ? estadoOperaria : undefined}
              alt=""
              draggable={false}
              className="pointer-events-none absolute left-0 top-0 origin-bottom select-none"
              style={{ imageRendering: "pixelated" }}
            />
          ))}

          <Divisorias />
          <Escurecimento ativa={cabineAtiva} rodando={rodando} />
          <ContornoAtivo ativa={cabineAtiva} rodando={rodando} />
          {CABINES.map((c) => (
            <PlacaCabine
              key={c.id}
              cabine={c.id}
              acesa={rodando && c.id === cabineAtiva}
              imagem={arte(rodando && c.id === cabineAtiva ? "estados/placa_acesa.png" : "estados/placa_apagada.png")}
            />
          ))}
          <Img src={arte("estados/contador_fichas.png")} x={3} y={54} z={6} />
          <TextoPixel texto={textoContador} x={3 + Math.floor((44 - larguraTexto(textoContador)) / 2)} y={57} cor="var(--cena-contador)" />

          {selos.map((s, i) => (
            <span key={`${s.id}-${i}`} className="animar-selo absolute" style={{ left: 284, top: 89 + i * 8, zIndex: 6 }}>
              <Img src={arte(`estados/selo_${s.tipo}.png`)} x={0} y={0} />
            </span>
          ))}

          <div
            ref={balao}
            data-visivel="sim"
            className="pointer-events-none absolute z-10 transition-opacity data-[visivel=nao]:opacity-0"
            style={{ top: 101, left: ENTRADA_ELMOS[0], zIndex: 10 }}
          >
            <div
              className="whitespace-pre rounded-selo border border-log-borda bg-log-fundo px-1 font-mono text-log-terminal"
              style={{ fontSize: `${12 / escala}px`, lineHeight: 1.4, transform: "translateY(-100%)" }}
            >
              <span ref={textoBalaoRef} />
            </div>
          </div>
        </div>
        {escala === 2 && (
          <div
            className="pointer-events-none absolute z-20 w-40 rounded-selo border border-log-borda bg-log-fundo/90 px-2 py-1.5 font-mono text-xs leading-4 text-log-apoio"
            style={{ left: 6, top: 42 }}
          >
            <div className="flex justify-between">
              <span>passos</span>
              <span className="text-log-texto">{eventos.length}</span>
            </div>
            <div className="flex justify-between">
              <span>custo</span>
              <span className="text-log-texto">{dolares(total)}</span>
            </div>
            <div className="flex items-center gap-1.5 text-log-fraco">
              <span className={cn("size-1.5 rounded-full", rodando ? "animar-pulsar bg-acento" : "bg-log-fraco")} />
              {rodando ? "executando" : "vigiando"}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
