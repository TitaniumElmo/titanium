# Kit de interface

> **Referência, não parte oficial do site.** Nada aqui está ligado ao Heitor: são peças para consulta, que podem ser usadas, adaptadas ou descartadas.

Peças trazidas do front do sistema Carvalho & Felinto, sem as cores de lá e sem dependências além do React. Funcionam com React 19 e Tailwind v4.

| Arquivo | O que é |
|---|---|
| `FundoOndas.tsx` | Fundo animado em ondas (WebGL puro). Cores pela prop `cores` |
| `LoginDeslizante.tsx` | Dois painéis que trocam de lado com corte diagonal + brilho que segue o mouse |
| `BlocoFoto.tsx` | Avatar clicável com câmera, trocar/remover foto, confirmação no lugar |
| `AjustarFoto.tsx` | Janela de enquadrar a foto (arrastar, pinça, roda do mouse, setas, + e -) |
| `foto.ts` | Recorta a foto no navegador em JPEG 256x256 e detecta canvas bloqueado |
| `Avatar.tsx` | Foto redonda, com as iniciais enquanto carrega ou se falhar |
| `util.tsx` | `cn`, `iniciais` e os ícones em SVG |
| `kit.css` | Tokens de cor (neutros, para trocar) e a animação de entrada |

## Ligar no projeto

```css
/* src/index.css */
@import "tailwindcss";
@import "./kit/kit.css";
```

Troque as cores do bloco `@theme` em `kit.css` pelas do Heitor.

## Exemplos

```tsx
<div className="relative h-80">
  <FundoOndas cores={["#escuro", "#medio", "#brilho"]} className="absolute inset-0" />
</div>
```

```tsx
<BlocoFoto
  nome={usuario.nome}
  fotoUrl={usuario.fotoUrl}
  onEnviar={async (foto) => {
    const corpo = new FormData();
    corpo.append("foto", foto);
    const r = await fetch("/api/minha-foto", { method: "PUT", body: corpo });
    if (!r.ok) throw new Error("Não foi possível enviar a foto.");
  }}
  onRemover={async () => { await fetch("/api/minha-foto", { method: "DELETE" }); }}
/>
```

`LoginDeslizante` tem um exemplo de uso no comentário do topo do arquivo.

## Cuidados

- Na `FundoOndas`, a 3ª cor é a das cristas da onda: use a mais clara ou viva.
- Não use `opacity` na `FundoOndas`: em algumas placas de vídeo o canvas fica branco (cinza, se estiver por cima de um fundo escuro). Pra deixar o efeito mais fraco, ponha por cima uma camada escura semitransparente.
- Com "reduzir movimento" ligado no sistema, as ondas ficam paradas e a troca de painéis não anima.
- O backend recebe um JPEG pronto, então não precisa de biblioteca de imagem.
