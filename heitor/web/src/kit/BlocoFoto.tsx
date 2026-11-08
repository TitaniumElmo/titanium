// REFERÊNCIA — não é parte oficial do site. Trazido do sistema Carvalho & Felinto como inspiração; pode ser usado, adaptado ou descartado.
//
// Bloco de foto de perfil: avatar grande clicável (com a câmera no canto pra deixar claro que dá
// pra clicar), botão "Enviar/Trocar foto" embaixo pra quem não percebe, e "Remover" discreto que
// vira a confirmação "Remover a foto?" ali mesmo, sem abrir janela.
//
// Fluxo: escolher arquivo → confere tipo/tamanho → carregarFoto (detecta canvas bloqueado) →
// janela AjustarFoto → recortarFoto (JPEG 256x256) → onEnviar(arquivo). O envio pro backend fica
// por conta de quem usa: passe uma função que faça o upload e lance erro se falhar.
import { useRef, useState, type ChangeEvent } from "react";
import { AjustarFoto } from "./AjustarFoto";
import { Avatar } from "./Avatar";
import { CanvasBloqueado, FotoIlegivel, carregarFoto, recortarFoto, type AreaDoRecorte } from "./foto";
import { IconeCamera, IconeLixeira, cn } from "./util";

const TIPOS_ACEITOS = ["image/jpeg", "image/png", "image/webp"];
// limite só do arquivo ORIGINAL (o que sobe é o recorte pequeno), pra não travar a aba
const MAX_BYTES_ORIGINAL = 15 * 1024 * 1024;

const BOTAO_CONTORNO =
  "inline-flex h-10 items-center gap-2 rounded-xl border border-border px-4 text-sm font-semibold text-primary hover:bg-secondary disabled:opacity-60";
const BOTAO_DISCRETO =
  "inline-flex h-10 items-center gap-2 rounded-xl px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/5 hover:text-destructive disabled:opacity-60";

function mensagemDeErro(erro: unknown): string {
  if (erro instanceof CanvasBloqueado)
    return "Seu navegador bloqueou o processamento da imagem. Permita o acesso ou use outro navegador.";
  if (erro instanceof FotoIlegivel) return "Não foi possível ler essa imagem. Tente outra.";
  if (erro instanceof Error && erro.message) return erro.message;
  return "Não foi possível enviar a foto.";
}

export function BlocoFoto({
  nome,
  fotoUrl,
  onEnviar,
  onRemover,
  somenteLeitura = false,
  className,
}: {
  nome: string;
  fotoUrl?: string | null;
  /** Recebe o JPEG já recortado. Lance erro se o upload falhar (a mensagem aparece embaixo). */
  onEnviar: (foto: File) => Promise<void>;
  /** Sem ela, o botão "Remover" não aparece */
  onRemover?: () => Promise<void>;
  somenteLeitura?: boolean;
  className?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  // foto escolhida esperando o ajuste do enquadramento (janela AjustarFoto aberta)
  const [ajuste, setAjuste] = useState<{ bitmap: ImageBitmap; url: string } | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [removendo, setRemovendo] = useState(false);
  const [confirmandoRemocao, setConfirmandoRemocao] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const ocupado = salvando || removendo;

  function fecharAjuste() {
    if (ajuste) {
      ajuste.bitmap.close();
      URL.revokeObjectURL(ajuste.url);
    }
    setAjuste(null);
  }

  async function aoEscolherArquivo(evento: ChangeEvent<HTMLInputElement>) {
    const arquivo = evento.target.files?.[0];
    // limpa na hora pra escolher o mesmo arquivo de novo disparar o onChange outra vez
    evento.target.value = "";
    if (!arquivo) return;
    setErro(null);
    if (!TIPOS_ACEITOS.includes(arquivo.type)) return setErro("Envie uma imagem JPG, PNG ou WEBP.");
    if (arquivo.size > MAX_BYTES_ORIGINAL) return setErro("A imagem pode ter no máximo 15 MB.");
    try {
      const bitmap = await carregarFoto(arquivo);
      setAjuste({ bitmap, url: URL.createObjectURL(arquivo) });
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  async function salvarAjuste(area: AreaDoRecorte) {
    if (!ajuste) return;
    setSalvando(true);
    try {
      const foto = await recortarFoto(ajuste.bitmap, area);
      await onEnviar(foto);
      fecharAjuste();
    } catch (e) {
      // se o envio falhar a janela continua aberta, com o mesmo enquadramento, pra tentar de novo
      setErro(mensagemDeErro(e));
    } finally {
      setSalvando(false);
    }
  }

  async function remover() {
    if (!onRemover) return;
    setRemovendo(true);
    setErro(null);
    try {
      await onRemover();
      setConfirmandoRemocao(false);
    } catch {
      setErro("Não foi possível remover a foto.");
    } finally {
      setRemovendo(false);
    }
  }

  const escolherFoto = () => inputRef.current?.click();

  return (
    <div className={cn("flex flex-col items-center gap-3 text-center", className)}>
      {ajuste && (
        <AjustarFoto
          bitmap={ajuste.bitmap}
          url={ajuste.url}
          salvando={salvando}
          onCancelar={fecharAjuste}
          onSalvar={(area) => void salvarAjuste(area)}
        />
      )}

      {somenteLeitura ? (
        <Avatar nome={nome} fotoUrl={fotoUrl} tamanho="lg" className="size-28 text-3xl" />
      ) : (
        <button
          type="button"
          onClick={escolherFoto}
          disabled={ocupado}
          aria-label={fotoUrl ? "Trocar foto" : "Enviar foto"}
          className="group relative rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <Avatar
            nome={nome}
            fotoUrl={fotoUrl}
            tamanho="lg"
            className={cn(
              "size-28 text-3xl transition-opacity group-hover:opacity-90",
              ocupado && "opacity-60",
            )}
          />
          <span className="absolute bottom-0 right-0 grid size-8 place-items-center rounded-full border border-border bg-card text-primary shadow-sm">
            <IconeCamera className="size-4" />
          </span>
        </button>
      )}

      {somenteLeitura ? null : confirmandoRemocao ? (
        <div className="flex flex-col items-center gap-1">
          <span className="text-sm text-foreground">Remover a foto?</span>
          <div className="flex gap-2">
            <button
              type="button"
              className="inline-flex h-10 items-center rounded-xl px-3 text-sm font-semibold text-destructive hover:bg-destructive/5"
              onClick={() => void remover()}
              disabled={ocupado}
            >
              {removendo ? "Removendo…" : "Remover"}
            </button>
            <button
              type="button"
              className="inline-flex h-10 items-center rounded-xl px-3 text-sm font-medium text-muted-foreground hover:bg-secondary hover:text-foreground"
              onClick={() => setConfirmandoRemocao(false)}
              disabled={ocupado}
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap justify-center gap-2">
          <button type="button" className={BOTAO_CONTORNO} onClick={escolherFoto} disabled={ocupado}>
            <IconeCamera className="size-4" />
            {salvando ? "Enviando…" : fotoUrl ? "Trocar foto" : "Enviar foto"}
          </button>
          {fotoUrl && onRemover && (
            <button
              type="button"
              className={BOTAO_DISCRETO}
              onClick={() => setConfirmandoRemocao(true)}
              disabled={ocupado}
            >
              <IconeLixeira className="size-4" />
              Remover
            </button>
          )}
        </div>
      )}

      {erro && (
        <p role="alert" className="text-sm text-destructive">
          {erro}
        </p>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={TIPOS_ACEITOS.join(",")}
        className="hidden"
        onChange={(e) => void aoEscolherArquivo(e)}
      />
    </div>
  );
}
