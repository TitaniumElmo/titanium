import { useEffect, useRef, useState } from "react";
import { dolares } from "../formato";
import type { Evento } from "../tipos";
import { cn } from "../util";
import { larguraTexto, TextoPixel } from "./TextoPixel";

const LARGURA = 540;
const ALTURA = 180;
const PES_CORREDOR = 174;
const ESPERA_OCIOSA_MS = 3000;

const URLS = import.meta.glob("../assets/cenario/**/*.png", { eager: true, query: "?url", import: "default" }) as Record<
  string,
  string
>;

function arte(caminho: string): string {
  return URLS[`../assets/cenario/${caminho}`] ?? "";
}

type Cabine = "A" | "B" | "C" | "F" | "D" | "E";
const CABINES: { id: Cabine; x: number; nome: string }[] = [
  { id: "A", x: 60, nome: "A PLANILHA" },
  { id: "B", x: 140, nome: "B AUDITORIA" },
  { id: "C", x: 220, nome: "C FICHA PAPEL" },
  { id: "F", x: 300, nome: "F RH" },
  { id: "D", x: 380, nome: "D TECNICO" },
  { id: "E", x: 460, nome: "E CANTEIRO" },
];
const PONTO_ELMO: Record<Cabine | "entrada", number> = { entrada: 30, A: 100, B: 180, C: 260, F: 340, D: 395, E: 445 };

type Personagem =
  | "01_operario_amarelo"
  | "02_tecnico"
  | "03_tecnica_cacheada"
  | "04_operaria"
  | "05_operaria_protetor_ficha"
  | "06_engenheiro"
  | "07_assistente_rh";

const LARGURA_SPRITE: Record<Personagem, number> = {
  "01_operario_amarelo": 58,
  "02_tecnico": 56,
  "03_tecnica_cacheada": 75,
  "04_operaria": 60,
  "05_operaria_protetor_ficha": 68,
  "06_engenheiro": 56,
  "07_assistente_rh": 78,
};

const PES_SPRITE: Record<Personagem, number> = {
  "01_operario_amarelo": 72,
  "02_tecnico": 72,
  "03_tecnica_cacheada": 72,
  "04_operaria": 72,
  "05_operaria_protetor_ficha": 72,
  "06_engenheiro": 72,
  "07_assistente_rh": 75,
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
    const tema = document.documentElement.dataset.tema;
    if (tema) return tema === "escuro";
    return !window.matchMedia("(prefers-color-scheme: light)").matches;
  };
  const [escuro, setEscuro] = useState(ler);
  useEffect(() => {
    const atualizar = () => setEscuro(ler());
    const obs = new MutationObserver(atualizar);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-tema"] });
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    mq.addEventListener("change", atualizar);
    return () => {
      obs.disconnect();
      mq.removeEventListener("change", atualizar);
    };
  }, []);
  return escuro;
}

function Img({ src, x, y, className }: { src: string; x: number; y: number; className?: string }) {
  return (
    <img
      src={src}
      alt=""
      draggable={false}
      className={cn("pointer-events-none absolute select-none", className)}
      style={{ left: x, top: y, imageRendering: "pixelated" }}
    />
  );
}

export function CenaEscritorio({
  chave,
  eventos,
  rodando,
  fichasNaPilha,
  urgente,
  progressoLeitura,
  deslocamento,
  className,
}: {
  chave: string;
  eventos: Evento[];
  rodando: boolean;
  fichasNaPilha: number;
  urgente: boolean;
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
  const [comProtetor, setComProtetor] = useState(false);
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

  const depois = (ms: number, fn: () => void) => {
    timers.current.push(window.setTimeout(fn, semMovimento.current ? 0 : ms));
  };

  if (Object.keys(atores.current).length === 0) {
    const novo = (personagem: Personagem, x: number, pesY = PES_CORREDOR, visivel = true): Ator => ({
      personagem,
      x,
      pesY,
      deX: x,
      alvoX: x,
      t0: 0,
      duracao: 0,
      andando: false,
      direcao: 1,
      fase: Math.random() * 4000,
      visivel,
    });
    atores.current = {
      rh: novo("07_assistente_rh", 356, 138),
      tecnico: novo("02_tecnico", 445),
      tecnica: novo("03_tecnica_cacheada", 402),
      operaria: novo("04_operaria", 500),
      engenheiro: novo("06_engenheiro", 396, PES_CORREDOR, false),
      elmo: novo("01_operario_amarelo", PONTO_ELMO.entrada),
    };
    const tecnica = atores.current.tecnica;
    if (tecnica) tecnica.direcao = 1;
  }

  const mover = (id: string, alvo: number, aoChegar?: () => void) => {
    const a = atores.current[id];
    if (!a) return;
    const agora = performance.now();
    a.deX = a.x;
    a.alvoX = alvo;
    a.t0 = agora;
    const distancia = Math.abs(alvo - a.x);
    a.duracao = semMovimento.current || distancia < 1 ? 0 : Math.min(1100, Math.max(320, (distancia / 150) * 1000));
    if (distancia >= 1) a.direcao = alvo > a.x ? 1 : -1;
    a.andando = true;
    a.aoChegar = aoChegar;
  };

  const mostrarBalao = (texto: string | null) => {
    if (textoBalaoRef.current) textoBalaoRef.current.textContent = texto ?? "";
    if (balao.current) balao.current.dataset.visivel = texto ? "sim" : "nao";
  };

  const historiaDoCanteiro = () => {
    mover("tecnica", 462, () => {
      depois(700, () => {
        setComProtetor(true);
        depois(1100, () =>
          mover("tecnica", 498, () => {
            depois(1500, () => mover("tecnica", 402));
          }),
        );
      });
    });
  };

  const escalada = () => {
    setPorta(true);
    depois(300, () => {
      const eng = atores.current.engenheiro;
      if (!eng) return;
      eng.visivel = true;
      eng.x = 396;
      mover("engenheiro", 368, () =>
        depois(2600, () =>
          mover("engenheiro", 396, () => {
            eng.visivel = false;
            depois(250, () => setPorta(false));
          }),
        ),
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
    mover("elmo", PONTO_ELMO[cabine]);
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
    const elmo = atores.current.elmo;
    if (elmo) {
      elmo.x = cabine ? PONTO_ELMO[cabine] : PONTO_ELMO.entrada;
      elmo.alvoX = elmo.x;
      elmo.andando = false;
    }
    setCabineAtiva(cabine);
    esperando.current = !rodando;
    ultimaAtividade.current = performance.now();
    mostrarBalao(rodando && ultimo ? textoBalao(ultimo) : "AGUARDANDO: correção na planilha");
  }, [chave, eventos, rodando]);

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
          if (t >= 1) {
            a.andando = false;
            const fn = a.aoChegar;
            a.aoChegar = undefined;
            fn?.();
          }
        }
        const el = elementos.current[id];
        if (!el) continue;
        const personagem = id === "operaria" && el.dataset.protetor === "sim" ? "05_operaria_protetor_ficha" : a.personagem;
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
      }

      const elmo = lista.elmo;
      if (elmo) {
        if (!elmo.andando && fila.current.length) {
          const proximo = fila.current.shift();
          if (proximo) processar(proximo);
        } else if (!elmo.andando && !esperando.current && agora - ultimaAtividade.current > ESPERA_OCIOSA_MS) {
          esperando.current = true;
          setCabineAtiva(null);
          setGaveta(false);
          mostrarBalao("AGUARDANDO: correção na planilha");
          mover("elmo", PONTO_ELMO.entrada);
        }
        if (balao.current) {
          const fracao = elmo.x / LARGURA;
          balao.current.style.left = `${elmo.x}px`;
          balao.current.style.transform = `translateX(${fracao > 0.7 ? -90 : fracao < 0.25 ? -10 : -50}%)`;
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
      aria-label={`Cena do agente: ${cabineAtiva ? `trabalhando na cabine ${cabineAtiva}` : "esperando na entrada"}`}
    >
      <div className="relative mx-auto" style={{ width: LARGURA * escala, height: ALTURA * escala }}>
        <div className="absolute left-0 top-0 origin-top-left" style={{ width: LARGURA, height: ALTURA, transform: `scale(${escala})` }}>
          <Img src={arte(escuro ? "fundo_escuro.png" : "fundo_claro.png")} x={0} y={0} />
          <Img src={arte("props_tras.png")} x={0} y={0} className={escuro ? "brightness-[.85]" : undefined} />
          {gaveta && <Img src={arte("estados/A_gaveta_aberta.png")} x={70} y={94} />}
          {nivelBandeja(auditadas) > 0 && <Img src={arte(`estados/B_bandeja_${nivelBandeja(auditadas)}.png`)} x={200} y={102} />}
          {cabineAtiva === "C" && <Img src={arte("estados/C_luminaria_acesa.png")} x={234} y={86} />}
          {porta && <Img src={arte("estados/D_porta_aberta.png")} x={385} y={69} />}
          {urgente && <Img src={arte(`estados/D_giroflex_${giro + 1}.png`)} x={431} y={99} />}
          <Img src={arte(`estados/D_relogio_ponteiro_${String(ponteiro).padStart(2, "0")}.png`)} x={422} y={42} />

          <img
            ref={(el) => {
              elementos.current.rh = el;
            }}
            alt=""
            draggable={false}
            className="pointer-events-none absolute left-0 top-0 origin-bottom select-none"
            style={{ imageRendering: "pixelated" }}
          />
          <Img src={arte("props_frente.png")} x={0} y={0} className={escuro ? "brightness-[.85]" : undefined} />

          {(["tecnico", "tecnica", "operaria", "engenheiro", "elmo"] as const).map((id) => (
            <img
              key={id}
              ref={(el) => {
                elementos.current[id] = el;
              }}
              data-protetor={id === "operaria" && comProtetor ? "sim" : "nao"}
              alt=""
              draggable={false}
              className="pointer-events-none absolute left-0 top-0 origin-bottom select-none"
              style={{ imageRendering: "pixelated" }}
            />
          ))}

          {CABINES.map((c) => {
            const acesa = c.id === cabineAtiva;
            return (
              <div key={c.id}>
                <Img src={arte(acesa ? "estados/placa_acesa.png" : "estados/placa_apagada.png")} x={c.x + 4} y={5} />
                <TextoPixel
                  texto={c.nome}
                  x={c.x + 4 + Math.floor((72 - larguraTexto(c.nome)) / 2)}
                  y={10}
                  cor={acesa ? "var(--cena-placa-acesa)" : "var(--cena-placa-apagada)"}
                />
              </div>
            );
          })}
          <Img src={arte("estados/contador_fichas.png")} x={3} y={54} />
          <TextoPixel texto={textoContador} x={3 + Math.floor((44 - larguraTexto(textoContador)) / 2)} y={57} cor="var(--cena-contador)" />

          {selos.map((s, i) => (
            <span key={`${s.id}-${i}`} className="animar-selo absolute" style={{ left: 284, top: 89 + i * 8 }}>
              <Img src={arte(`estados/selo_${s.tipo}.png`)} x={0} y={0} />
            </span>
          ))}

          <div
            ref={balao}
            data-visivel="sim"
            className="pointer-events-none absolute z-10 transition-opacity data-[visivel=nao]:opacity-0"
            style={{ top: 78, left: PONTO_ELMO.entrada }}
          >
            <div
              className="whitespace-nowrap rounded-selo border border-log-borda bg-log-fundo px-1 font-mono text-log-terminal"
              style={{ fontSize: `${12 / escala}px`, lineHeight: 1.4, transform: "translateY(-100%)" }}
            >
              <span ref={textoBalaoRef} />
            </div>
          </div>
        </div>
      </div>
      <div className="pointer-events-none sticky bottom-2 left-2 z-20 -mt-[58px] ml-2 hidden w-40 sm:block rounded-selo border border-log-borda bg-log-fundo/90 px-2 py-1.5 font-mono text-xs leading-4 text-log-apoio">
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
    </div>
  );
}
