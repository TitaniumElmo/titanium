import { BotaoLink, EstadoVazio } from "../componentes/base";
import { Pagina } from "../componentes/Pagina";
import { IconeCaixa } from "../util";

export function NaoEncontrada() {
  return (
    <Pagina titulo="Página não encontrada">
      <EstadoVazio
        icone={IconeCaixa}
        titulo="Este endereço não existe"
        acao={<BotaoLink para="/">Voltar para o início</BotaoLink>}
      />
    </Pagina>
  );
}
