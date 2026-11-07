"""Stubs das funções da Sofia (agente) e do Gustavo (dados).

Mesmas assinaturas do CLAUDE.md. Servem só para a API e a interface andarem
antes da integração. As regras aqui são uma versão mínima e NÃO são as regras
oficiais: quem decide a verdade é `audita_linha`, do Gustavo.

As datas de validade de CA abaixo são de mentira, exceto os vencimentos
conferidos no CLAUDE.md (28499 e 21245).
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from heitor.api import config
from heitor.api.estado import estado
from heitor.api.ferramentas import criar_pendencia, fechar_pendencia
from heitor.contrato import Achado, Evento, Linha

# ---------------------------------------------------------------------------
# Gustavo: dados
# ---------------------------------------------------------------------------

_FIM = date(2030, 12, 31)  # fim de validade de mentira
# CA -> períodos em que o CA vale (início, fim). None = desde sempre.
_CAS: dict[str, list[tuple[Optional[date], date]]] = {
    "29637": [(None, _FIM)],
    "9182": [(None, _FIM)],
    "12844": [(None, _FIM)],
    "10344": [(None, _FIM)],
    "17664": [(None, _FIM)],
    "21245": [(None, date(2024, 4, 29)), (date(2024, 6, 24), _FIM)],
    "28499": [(None, date(2020, 10, 2))],
}

_EXIGENCIAS = {
    "pedreiro": {"agente": "ruído", "epi": ["protetor auditivo"], "grau": 0.20},
    "servente": {"agente": "ruído", "epi": ["protetor auditivo"], "grau": 0.20},
}

SALARIO_MINIMO_STUB = 1518.00


def consulta_ca(numero: str, data: date) -> dict[str, Any]:
    periodos = _CAS.get(str(numero))
    if periodos is None:
        return {"numero": str(numero), "encontrado": False, "valido": None, "validade": None, "stub": True}
    vigente = next((p for p in periodos if (p[0] is None or p[0] <= data) and data <= p[1]), None)
    vencidos = [fim for _, fim in periodos if fim < data]
    validade = vigente[1] if vigente else (max(vencidos) if vencidos else None)
    return {
        "numero": str(numero),
        "encontrado": True,
        "valido": vigente is not None,
        "validade": validade.isoformat() if validade else None,
        "stub": True,
    }


def exigencia_funcao(funcao: str) -> dict[str, Any]:
    return _EXIGENCIAS.get(funcao.lower(), {"agente": None, "epi": [], "grau": None})


# ---------------------------------------------------------------------------
# Sofia: extração
# ---------------------------------------------------------------------------

_VERDADEIRO = {"sim", "s", "true", "1", "x"}
_FALSO = {"nao", "não", "n", "false", "0"}


def _bool(valor: str) -> Optional[bool]:
    v = (valor or "").strip().lower()
    return True if v in _VERDADEIRO else False if v in _FALSO else None


def extrair_ficha(arquivo: str) -> list[Linha]:
    """Lê CSV com as colunas do contrato. Foto/PDF: o stub devolve lista vazia."""
    caminho = Path(arquivo)
    if caminho.suffix.lower() != ".csv":
        return []
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        linhas = []
        for n, reg in enumerate(csv.DictReader(f), start=1):
            linhas.append(
                Linha(
                    funcionario_id=reg["funcionario_id"].strip(),
                    nome=reg["nome"].strip(),
                    funcao=reg["funcao"].strip().lower(),
                    linha=n,
                    data=reg.get("data") or None,
                    epi=reg["epi"].strip(),
                    qtd=int(reg.get("qtd") or 1),
                    ca=(reg.get("ca") or "").strip() or None,
                    motivo=(reg.get("motivo") or "").strip() or None,
                    assinatura=_bool(reg.get("assinatura", "")),
                    confianca={c: 1.0 for c in ("data", "epi", "ca", "assinatura")},
                    origem=caminho.name,
                )
            )
    return linhas


# ---------------------------------------------------------------------------
# Sofia: agente
# ---------------------------------------------------------------------------


@dataclass
class _Falha:
    regra: str
    linha: Optional[int]
    gravidade: str
    tipo: str
    evidencia: str
    acao: str
    destino: str
    prazo_dias: int
    norma: str
    exposicao_rs: Optional[float] = None


def _meses_desde(d: date) -> int:
    hoje = date.today()
    return max(0, (hoje.year - d.year) * 12 + hoje.month - d.month)


def _falhas_da_linha(l: Linha) -> list[_Falha]:
    falhas = []
    if l.assinatura is False:
        grau = exigencia_funcao(l.funcao).get("grau") or 0.20
        meses = min(_meses_desde(l.data), 60) if l.data else 60
        falhas.append(_Falha(
            "assinatura_ausente", l.linha, "irregular", "passivo",
            f"linha {l.linha}, entrega de {l.epi} sem assinatura",
            "colher assinatura nas próximas entregas", "tecnico", 7,
            "Súmula 289 do TST", round(grau * SALARIO_MINIMO_STUB * meses, 2),
        ))
    if not l.ca:
        falhas.append(_Falha(
            "ca_ausente", l.linha, "risco", "prova",
            f"linha {l.linha}, campo CA vazio ({l.epi})",
            "pedir nota fiscal ao RH", "rh", 5, "NR-6; Súmula 80 do TST",
        ))
    elif l.data:
        r = consulta_ca(l.ca, l.data)
        if r["encontrado"] and not r["valido"]:
            falhas.append(_Falha(
                "ca_vencido", l.linha, "risco", "prova",
                f"linha {l.linha}, CA {l.ca} vencido em {r['validade']} na data da entrega {l.data}",
                "pedir nota fiscal ao RH (critério adotado: CA válido na data da compra)", "rh", 5,
                "NR-6; Nota Técnica 146/2015 do MTE",
            ))
    return falhas


def _falhas_do_funcionario(funcao: str, linhas: list[Linha]) -> list[_Falha]:
    falhas = []
    for epi in exigencia_funcao(funcao)["epi"]:
        if not any(epi in l.epi.lower() for l in linhas):
            falhas.append(_Falha(
                "epi_inadequado", None, "irregular", "corrigivel",
                f"função {funcao} exige {epi}; nenhuma entrega registrada",
                f"entregar {epi} e colher assinatura", "tecnico", 3, "NR-6; Súmula 80 do TST",
            ))
    return falhas


def _avaliar(linhas: list[Linha]) -> list[_Falha]:
    falhas = [f for l in linhas for f in _falhas_da_linha(l)]
    if linhas:
        falhas += _falhas_do_funcionario(linhas[0].funcao, linhas)
    return falhas


def _por_funcionario(linhas: list[Linha]) -> dict[str, list[Linha]]:
    grupos: dict[str, list[Linha]] = {}
    for l in linhas:
        grupos.setdefault(l.funcionario_id, []).append(l)
    return grupos


def rodar_auditoria(auditoria_id: str, linhas: list[Linha], emitir_evento: Callable[[Evento], None]) -> list[Achado]:
    """Agente falso: um episódio por funcionário, com eventos parecidos com os reais."""
    achados: list[Achado] = []
    for func_id, linhas_func in _por_funcionario(linhas).items():
        passo = 0

        def emitir(tipo: str, ferramenta: Optional[str], entrada: dict, saida: Any, custo: float = 0.0) -> None:
            nonlocal passo
            passo += 1
            emitir_evento(Evento(
                auditoria_id=auditoria_id, funcionario_id=func_id, passo=passo, tipo=tipo,
                ferramenta=ferramenta, entrada=entrada, saida=saida, custo_usd=custo, ts=datetime.now(),
            ))
            time.sleep(config.STUB_ATRASO_S)

        emitir("decisao", None, {}, f"auditar {linhas_func[0].nome} ({len(linhas_func)} linhas)", 0.0003)
        for l in linhas_func:
            if l.ca and l.data:
                emitir("ferramenta", "consulta_ca", {"numero": l.ca, "data": l.data.isoformat()}, consulta_ca(l.ca, l.data))
        emitir("ferramenta", "exigencia_funcao", {"funcao": linhas_func[0].funcao}, exigencia_funcao(linhas_func[0].funcao))

        for l in linhas_func:
            emitir("ferramenta", "audita_linha", {"linha": l.linha}, [f.regra for f in _falhas_da_linha(l)])
        funcao = linhas_func[0].funcao
        emitir("ferramenta", "audita_funcionario", {"funcao": funcao},
               [f.regra for f in _falhas_do_funcionario(funcao, linhas_func)])

        for f in _avaliar(linhas_func):
            achado = Achado(
                id=estado.novo_id("a"), auditoria_id=auditoria_id, funcionario_id=func_id, linha=f.linha,
                regra=f.regra, gravidade=f.gravidade, tipo=f.tipo, evidencia=f.evidencia,
                acao_sugerida=f.acao, norma=f.norma, exposicao_rs=f.exposicao_rs,
            )
            p = criar_pendencia(achado, f.destino, f.acao, date.today() + timedelta(days=f.prazo_dias))
            emitir("ferramenta", "criar_pendencia", {"achado_id": achado.id, "destino": f.destino}, {"pendencia_id": p["id"]})
            achados.append(achado)

        emitir("decisao", None, {}, "terminei", 0.0004)
    return achados


def reauditar(pendencia_id: str, linhas: list[Linha], emitir_evento: Optional[Callable[[Evento], None]] = None) -> list[Achado]:
    """Reaplica as regras às linhas novas e fecha ou reabre a pendência.

    Documento que não é ficha (nota fiscal, lista de presença) chega como
    lista vazia: para pendência do RH, o stub aceita sem conferir o conteúdo.
    """
    p = estado.obter_pendencia(pendencia_id)
    achado = estado.obter_achado(p.achado_id, p.auditoria_id)

    if not linhas and p.destino == "rh":
        fechar_pendencia(p, True, "documento recebido (stub: conteúdo não conferido)")
        return []

    do_funcionario = [l for l in linhas if l.funcionario_id == achado.funcionario_id]
    ainda = [f for f in _avaliar(do_funcionario) if f.regra == achado.regra and f.linha == achado.linha]
    linha_sumiu = achado.linha is not None and not any(l.linha == achado.linha for l in do_funcionario)
    if not do_funcionario or linha_sumiu:
        fechar_pendencia(p, False, "a ficha devolvida não contém as linhas originais deste funcionário")
    else:
        fechar_pendencia(p, not ainda)
    return []


def gerar_relatorio(achados: list[dict], exposicao: Optional[dict] = None) -> dict[str, Any]:
    """Mesmo formato do relatório da Sofia, simplificado: {"texto": markdown}."""
    if not achados:
        return {"texto": "# Relatório do Heitor\n\nNenhuma lacuna encontrada na prova documental.\n"}
    partes = ["# Relatório do Heitor (stub)\n"]
    for a in achados:
        partes.append(
            f"- **{a['regra']}** ({a['gravidade']}, {a['tipo']}), funcionário {a['funcionario_id']}: "
            f"{a['evidencia']}. Base: {a.get('norma') or '-'}. Ação: {a['acao_sugerida']}."
        )
    total = sum(a.get("exposicao_rs") or 0 for a in achados)
    if total:
        partes.append(
            f"\nExposição potencial máxima, se a perícia confirmar a insalubridade: "
            f"R$ {total:,.2f} (salário mínimo usado: R$ {SALARIO_MINIMO_STUB:,.2f})."
        )
    return {"texto": "\n".join(partes) + "\n"}
