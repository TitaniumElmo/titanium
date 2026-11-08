"""Gatilho 1: o Heitor percebe sozinho que uma ficha mudou na pasta.

A cada `intervalo_s`, o vigia lista a fonte (Drive ou pasta local) e:

1. Acha arquivos novos ou alterados pela `assinatura` de cada um. Só age
   quando a assinatura aparece IGUAL em duas verificações seguidas: assim não
   lê uma planilha no meio de uma edição nem uma foto que ainda está subindo.
2. Lê só esses arquivos. Foto já lida não é lida de novo (cada leitura custa
   duas chamadas ao modelo de visão).
3. Compara o conteúdo de cada entrega (hash por linha, sem o número da linha)
   com o da última vez e descobre QUAIS funcionários mudaram.
4. Abre uma auditoria nova com a ficha inteira desses funcionários. Problema
   que já tem pendência aberta reaproveita a pendência (sem duplicar, sem aviso).
5. Quando a auditoria termina, concilia as pendências abertas deles:
   - o problema não aparece mais -> fecha ("corrigido na pasta");
   - o problema continua -> fica como está;
   - a entrega que originou o problema sumiu da ficha -> NÃO fecha: apagar
     linha antiga não corrige nada (CLAUDE.md, seção 2);
   - a auditoria nova não rodou a regra daquele problema (o LLM pulou uma
     etapa ou ela falhou) -> não fecha: ausência de prova não é correção.

Ao ver um arquivo já lido mudar, o vigia espera uma verificação para confirmar que
parou de mudar e avisa no feed global (evento "edicao_detectada", auditoria_id "vigia").
A cada ciclo ele também cobra pendências com prazo vencido (heitor/api/cobranca.py).

Nenhum passo altera a fonte. Todo trabalho disparado registra a origem
("disparado por: mudança na pasta: <arquivos>").
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from heitor.api import cobranca, config, execucao, ferramentas
from heitor.api.fotos import dono_da_foto
from heitor.api.estado import estado
from heitor.api.fontes import ArquivoFonte, Fonte, PastaDrive, PastaLocal
from heitor.contrato import Linha

log = logging.getLogger("heitor.vigia")

AUDITORIA_GLOBAL = "vigia"  # auditoria_id dos eventos do vigia que ainda não pertencem a uma auditoria
_CAMPOS_DA_ENTREGA = ("funcionario_id", "nome", "funcao", "data", "epi", "qtd", "ca", "motivo", "assinatura")


def hash_da_entrega(l: Linha) -> str:
    """Conteúdo da entrega, sem número de linha, origem ou confiança."""
    dados = l.model_dump(mode="json", include=set(_CAMPOS_DA_ENTREGA))
    return hashlib.sha1(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _juntar(linhas: list[Linha]) -> list[Linha]:
    """Linhas de um funcionário vindas de vários arquivos podem repetir número
    (linha 1 do CSV e linha 1 da foto). Nesse caso, renumera em sequência."""
    numeros = [l.linha for l in linhas]
    if len(numeros) == len(set(numeros)):
        return linhas
    ordenadas = sorted(linhas, key=lambda l: (l.origem, l.linha))
    return [l.model_copy(update={"linha": i}) for i, l in enumerate(ordenadas, start=1)]


class Vigia:
    def __init__(self, fonte: Fonte, intervalo_s: float = 10.0, pasta_trabalho: Optional[Path] = None):
        self.fonte = fonte
        self.intervalo_s = intervalo_s
        self.pasta_trabalho = Path(pasta_trabalho or config.PASTA_UPLOADS / "fonte")
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.esquecer()

    # -- estado ---------------------------------------------------------------

    def esquecer(self) -> None:
        """Volta ao zero: na próxima verificação estável, audita a pasta inteira."""
        self._processados: dict[str, str] = {}  # arquivo -> assinatura já lida
        self._candidatos: dict[str, str] = {}  # arquivo -> assinatura vista uma vez, aguardando confirmar
        self._falhas: dict[str, str] = {}  # arquivo -> assinatura que falhou ao ler (só tenta de novo se mudar)
        self._versoes: dict[str, str] = {}  # planilha do Google -> última versão vista
        self._avisado: dict[str, tuple] = {}  # arquivo -> edição já anunciada no feed (não repete)
        self._linhas: dict[str, list[Linha]] = {}  # arquivo -> linhas lidas
        self._colunas: dict[str, tuple[str, list[dict]]] = {}  # planilha -> (nome, tabela de colunas)
        # Foto de ficha de papel: não é lida como ficha (os dados vêm da planilha); só vai junto para o
        # agente conferir as assinaturas. arquivo -> (nome, assinatura, caminho baixado)
        self._fotos: dict[str, tuple[str, str, str]] = {}
        self.fotos_sem_dono: list[str] = []
        self._hashes: dict[str, Counter] = {}  # funcionário -> hashes das entregas
        self.verificacoes = 0
        self.ultima_verificacao: Optional[datetime] = None
        self.ultimo_erro: Optional[str] = None
        self.ultimo_disparo: Optional[dict[str, Any]] = None

    def status(self) -> dict[str, Any]:
        return {
            "fonte": self.fonte.descricao,
            "link": getattr(self.fonte, "link", None),  # pasta do Drive (None na pasta local)
            "conta_servico": getattr(self.fonte, "conta", None),  # com quem compartilhar a pasta
            "personalizada": personalizada,  # pasta trocada pela API (POST /fontes) e não a do .env
            "intervalo_s": self.intervalo_s,
            "rodando": bool(self._thread and self._thread.is_alive()),
            "verificacoes": self.verificacoes,
            "ultima_verificacao": self.ultima_verificacao,
            "arquivos_lidos": len(self._processados),
            "aguardando_confirmar": len(self._candidatos),
            "arquivos_com_falha": len(self._falhas),
            "funcionarios": len(self._hashes),
            "fotos": len(self._fotos),
            "fotos_sem_dono": self.fotos_sem_dono,
            # Como o Heitor entendeu cada coluna de cada planilha (só código, sem LLM aqui):
            # nome do arquivo -> [{indice, coluna, campo, campo_rotulo, confianca, origem, exemplo, situacao}]
            "colunas": {nome: tabela for nome, tabela in self._colunas.values()},
            "ultimo_erro": self.ultimo_erro,
            "ultimo_disparo": self.ultimo_disparo,
        }

    # -- laço -----------------------------------------------------------------

    def iniciar(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, name="vigia", daemon=True)
        self._thread.start()
        log.info("vigia observando %s a cada %ss", self.fonte.descricao, self.intervalo_s)

    def parar(self) -> None:
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _laco(self) -> None:
        while not self._parar.is_set():
            try:
                self.verificar()
            except Exception:  # o vigia nunca morre: tenta de novo no próximo ciclo
                log.exception("verificação falhou")
            try:
                cobranca.cobrar_atrasadas()
            except Exception:
                log.exception("cobrança de prazos vencidos falhou")
            self._parar.wait(self.intervalo_s)

    # -- uma verificação --------------------------------------------------------

    def verificar(self) -> dict[str, Any]:
        """Uma passada pela fonte. Devolve o que foi feito (para o log e os testes)."""
        with self._lock:
            self.verificacoes += 1
            self.ultima_verificacao = datetime.now()
            try:
                arquivos = self.fonte.listar()
            except Exception as exc:
                self.ultimo_erro = f"listar a fonte: {type(exc).__name__}: {exc}"
                log.warning(self.ultimo_erro)
                return {"erro": self.ultimo_erro}

            prontos = self._estaveis(arquivos)
            removidos = self._remover_ausentes({a.id for a in arquivos})
            lidos = [a for a in prontos if self._ler(a)]
            if not lidos and not removidos:
                return {"mudou": False, "aguardando_confirmar": len(self._candidatos)}

            mudaram = self._funcionarios_que_mudaram()
            if self._parar.is_set():
                # Este vigia foi parado (troca de pasta) no meio da verificação: não cria auditoria da
                # pasta antiga, que cairia no estado da pasta nova.
                return {"mudou": False, "parado": True}
            if not mudaram:
                return {"mudou": False, "arquivos": [a.nome for a in lidos], "funcionarios": []}

            nomes = [a.nome for a in lidos] or ["arquivo removido"]
            origem = f"mudança na pasta: {', '.join(nomes)}"
            auditoria_id = self._auditar(mudaram, nomes, origem)
            self.ultimo_disparo = {
                "quando": datetime.now(), "arquivos": nomes, "funcionarios": sorted(mudaram),
                "auditoria_id": auditoria_id,
            }
            return {"mudou": True, **self.ultimo_disparo}

    def _estaveis(self, arquivos: list[ArquivoFonte]) -> list[ArquivoFonte]:
        prontos = []
        for a in arquivos:
            if a.versao:
                anterior = self._versoes.get(a.id)
                self._versoes[a.id] = a.versao
                if anterior and anterior != a.versao and a.id in self._processados:
                    # Planilha do Google: a versão mudou na hora; o CSV exportado ainda pode estar
                    # velho por ~15 s. Avisa já, para a tela não ficar parada esperando o Google.
                    self._avisar_edicao(a, ("versao", a.versao))
            if self._processados.get(a.id) == a.assinatura or self._falhas.get(a.id) == a.assinatura:
                self._candidatos.pop(a.id, None)
            elif self._candidatos.get(a.id) == a.assinatura:
                prontos.append(a)  # igual em duas verificações seguidas: parou de mudar
            else:
                if a.id in self._processados:  # arquivo já lido mudou: ainda pode estar em edição
                    self._avisar_edicao(a, ("versao", a.versao) if a.versao else ("conteudo", a.assinatura))
                self._candidatos[a.id] = a.assinatura
        return prontos

    def _avisar_edicao(self, a: ArquivoFonte, marca: tuple) -> None:
        """Uma vez por edição: a versão nova e o conteúdo que chega depois são a mesma edição."""
        if self._avisado.get(a.id) != marca:
            self._avisado[a.id] = marca
            self._edicao_detectada(a)

    def _edicao_detectada(self, a: ArquivoFonte) -> None:
        """Ainda não há auditoria: o evento vai no feed global (GET /eventos) com auditoria_id "vigia"."""
        dados = {"fonte": self.fonte.descricao, "arquivo": a.nome, "aguardando_segundos": self.intervalo_s}
        execucao.emitir_evento(AUDITORIA_GLOBAL, {
            "passo": 0, "tipo": "ferramenta", "ferramenta": "edicao_detectada",
            "entrada": dict(dados), "saida": dict(dados),
        })

    def _remover_ausentes(self, ids: set[str]) -> list[str]:
        for some in [i for i in self._candidatos if i not in ids]:
            self._candidatos.pop(some)
        removidos = [i for i in self._processados if i not in ids]
        for i in removidos:
            self._processados.pop(i)
            self._linhas.pop(i, None)
            self._colunas.pop(i, None)
            self._fotos.pop(i, None)
        return removidos

    def _ler(self, a: ArquivoFonte) -> bool:
        self._candidatos.pop(a.id, None)
        try:
            pasta = self.pasta_trabalho / hashlib.sha1(a.id.encode()).hexdigest()[:12]
            caminho = self.fonte.baixar(a, pasta)
            linhas, colunas = ([], []) if a.tipo == "foto" else execucao.ler_linhas_e_colunas(str(caminho))
        except Exception as exc:
            self._falhas[a.id] = a.assinatura
            self.ultimo_erro = f"ler {a.nome}: {type(exc).__name__}: {exc}"
            log.warning(self.ultimo_erro)
            return False
        self._falhas.pop(a.id, None)
        self._processados[a.id] = a.assinatura
        if a.tipo == "foto":
            self._fotos[a.id] = (a.nome, a.assinatura, str(caminho))
            log.info("foto recebida: %s", a.nome)
        else:
            self._linhas[a.id] = linhas
            if colunas:
                self._colunas[a.id] = (a.nome, colunas)
            else:
                self._colunas.pop(a.id, None)
            log.info("lido %s: %d linhas", a.nome, len(linhas))
        return True

    def _fotos_por_funcionario(self) -> dict[str, tuple[str, str]]:
        """funcionário -> (assinatura, caminho) da foto dele. Ligação pela matrícula no nome do arquivo."""
        funcionarios = {l.funcionario_id for ls in self._linhas.values() for l in ls}
        ligadas, sem_dono = {}, []
        for nome, assinatura, caminho in self._fotos.values():
            dono = dono_da_foto(nome, funcionarios)
            if dono is None:
                sem_dono.append(nome)
            else:
                ligadas[dono] = (assinatura, caminho)
        if sem_dono != self.fotos_sem_dono and sem_dono:
            log.warning("foto sem funcionário na planilha (ponha a matrícula no nome): %s", ", ".join(sem_dono))
        self.fotos_sem_dono = sem_dono
        return ligadas

    def _linhas_por_funcionario(self) -> dict[str, list[Linha]]:
        grupos: dict[str, list[Linha]] = {}
        for linhas in self._linhas.values():
            for l in linhas:
                grupos.setdefault(l.funcionario_id, []).append(l)
        return grupos

    def _funcionarios_que_mudaram(self) -> set[str]:
        novos = {f: Counter(hash_da_entrega(l) for l in ls) for f, ls in self._linhas_por_funcionario().items()}
        for f, (assinatura, _) in self._fotos_por_funcionario().items():
            if f in novos:  # foto nova ou trocada também muda o funcionário: ele é auditado com a foto
                novos[f][f"foto:{assinatura}"] += 1
        mudaram = {f for f in novos.keys() | self._hashes.keys() if novos.get(f) != self._hashes.get(f)}
        self._hashes = novos
        return {f for f in mudaram if f in novos}  # quem sumiu da pasta não tem o que auditar

    def _auditar(self, funcionarios: set[str], arquivos: list[str], origem: str) -> str:
        grupos = self._linhas_por_funcionario()
        linhas = [l for f in sorted(funcionarios) for l in _juntar(grupos[f])]
        fotos = {f: caminho for f, (_, caminho) in self._fotos_por_funcionario().items() if f in funcionarios}
        auditoria_id = estado.novo_id("au")
        estado.criar_auditoria(
            auditoria_id, arquivos, disparado_por="alteracao_planilha", descricao_disparo=origem
        )
        execucao.em_segundo_plano(_auditar_e_conciliar, auditoria_id, linhas, origem, fotos)
        return auditoria_id


# ---------------------------------------------------------------------------
# Conciliação: a auditoria nova decide o destino das pendências abertas
# ---------------------------------------------------------------------------


def _auditar_e_conciliar(auditoria_id: str, linhas: list[Linha], origem: str, fotos: dict[str, str]) -> None:
    execucao.auditar_linhas(auditoria_id, linhas, origem, fotos=fotos)
    try:
        conciliar(auditoria_id, linhas)
    except Exception:
        log.exception("conciliação da auditoria %s falhou", auditoria_id)


# auditar_ficha (agente do PR #6) roda as regras de linha e da ficha inteira numa chamada só.
_AUDITA_TUDO = "auditar_ficha"
_REGRAS_DE_DUVIDA = {"falha_de_ferramenta", "leitura_incerta"}


def _ferramenta_da_regra(linha: Optional[int]) -> str:
    # Problema de uma entrega vem do audita_linha; da ficha inteira, do audita_funcionario.
    return "audita_linha" if linha is not None else "audita_funcionario"


def conciliar(auditoria_id: str, linhas: list[Linha]) -> list[dict[str, str]]:
    """Fecha as pendências abertas cujo problema a auditoria nova não encontrou mais."""
    aud = estado.obter_auditoria(auditoria_id)
    if aud is None or aud.status != "concluida":
        return []  # auditoria com erro não serve de prova de correção

    funcionarios = {l.funcionario_id for l in linhas}
    rodou = {(e.funcionario_id, e.ferramenta) for e in estado.eventos_desde(auditoria_id) if e.tipo != "erro"}
    problemas_atuais = {ferramentas._chave_do_problema(a) for a in estado.listar_achados(auditoria_id)}
    entregas = {
        (l.funcionario_id, str(l.data), l.epi.strip().lower(), l.ca or "") for l in estado.obter_linhas(auditoria_id)
    }

    # Dúvida não é prova de correção: se a auditoria nova deixou o funcionário em revisão (uma regra falhou) ou
    # com leitura a conferir no papel (data impossível, CA que não combina), nenhuma pendência dele fecha agora.
    em_duvida = {a.funcionario_id: a.regra for a in estado.listar_achados(auditoria_id) if a.regra in _REGRAS_DE_DUVIDA}

    resultado = []
    for f in sorted(funcionarios):
        for p in estado.listar_pendencias(funcionario_id=f):
            if p.status not in ("aberta", "reaberta") or p.auditoria_id == auditoria_id:
                continue
            achado = estado.obter_achado(p.achado_id, p.auditoria_id)
            if achado is None:
                continue
            chave = ferramentas._chave_do_problema(achado)
            if chave in problemas_atuais:
                continue  # o problema continua: a pendência fica como está
            if (f, _ferramenta_da_regra(achado.linha)) not in rodou and (f, _AUDITA_TUDO) not in rodou:
                motivo, fechar = "a auditoria nova não conferiu esta regra; pendência mantida", False
            elif f in em_duvida:
                motivo, fechar = (f"a auditoria nova deixou dúvida sobre este funcionário ({em_duvida[f]}); "
                                  "pendência mantida até conferir"), False
            elif chave[1] == "entrega" and (f, *chave[2:]) not in entregas:
                motivo, fechar = "a entrega original não está mais na ficha; apagar linha antiga não corrige", False
            else:
                motivo, fechar = f"o problema não aparece mais na auditoria {auditoria_id} ({aud.descricao_disparo or aud.disparado_por})", True

            if fechar:
                ferramentas.fechar_pendencia(p.id, True, motivo)
            execucao.emitir_evento(auditoria_id, {
                "funcionario_id": f, "passo": 0, "tipo": "ferramenta",
                "ferramenta": "fechar_pendencia" if fechar else "manter_pendencia",
                "entrada": {"pendencia_id": p.id, "regra": achado.regra},
                "saida": {"status": "fechada" if fechar else p.status, "motivo": motivo},
            })
            resultado.append({"pendencia_id": p.id, "status": "fechada" if fechar else p.status, "motivo": motivo})
    return resultado


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

vigia: Optional[Vigia] = None
personalizada = False  # True quando o time trocou a pasta pela API (POST /fontes); False = a do .env
_troca = threading.Lock()
_ESPERA_VIGIA_ANTIGO_S = 90.0  # tempo máximo esperando a verificação em curso do vigia antigo terminar


def fonte_da_config() -> Optional[Fonte]:
    """Drive se HEITOR_DRIVE_PASTA estiver no .env; senão pasta local se
    HEITOR_FONTE_PASTA estiver; senão nenhuma (só upload pela API)."""
    if config.DRIVE_PASTA:
        return PastaDrive(config.DRIVE_PASTA, config.DRIVE_CREDENCIAIS)
    if config.FONTE_PASTA:
        return PastaLocal(config.FONTE_PASTA)
    return None


def criar_da_config() -> Optional[Vigia]:
    global vigia, personalizada
    fonte = fonte_da_config()
    if fonte is None:
        return None
    vigia, personalizada = Vigia(fonte, config.VIGIA_INTERVALO_S), False
    return vigia


def abrir_drive(pasta_id: str) -> PastaDrive:
    """Pasta do Drive pronta para o vigia, com o acesso já conferido. Lança ValueError com a
    mensagem para a tela (pasta não compartilhada, não é pasta, servidor sem a chave)."""
    if not Path(config.DRIVE_CREDENCIAIS).is_file():
        raise ValueError("o servidor não tem a chave da conta de serviço do Drive (HEITOR_DRIVE_CREDENCIAIS)")
    fonte = PastaDrive(pasta_id, config.DRIVE_CREDENCIAIS)
    try:
        fonte.conferir_acesso()
    except FileNotFoundError:
        raise ValueError(f"o Drive não achou a pasta: compartilhe-a com {fonte.conta} (permissão de Leitor)") from None
    return fonte


def trocar_fonte(fonte: Fonte, *, da_config: bool = False) -> Vigia:
    """Passa a observar outra pasta. Há um vigia só (sem contas, uma pasta por vez): a troca vale
    para todos e apaga o estado em memória, como o reset da demo; a pasta nova é auditada inteira
    na próxima verificação estável. A pasta antiga não é alterada (o vigia só lê)."""
    global vigia, personalizada
    with _troca:
        antigo = vigia
        if antigo:
            antigo.parar()
            # parar() espera a thread só 5 s; uma verificação do Drive pode demorar mais. Esperar o
            # lock garante que ela terminou (ela vê o sinal de parada antes de criar auditoria) e que
            # nada dela é gravado depois da limpeza abaixo.
            if antigo._lock.acquire(timeout=_ESPERA_VIGIA_ANTIGO_S):
                antigo._lock.release()
            else:
                log.warning("vigia antigo ainda verificando após %ss; segue a troca (ele não cria mais auditorias)",
                            _ESPERA_VIGIA_ANTIGO_S)
        estado.limpar()
        novo = Vigia(fonte, antigo.intervalo_s if antigo else config.VIGIA_INTERVALO_S)
        vigia, personalizada = novo, not da_config
        novo.iniciar()
    log.info("vigia agora observa %s", fonte.descricao)
    return novo
