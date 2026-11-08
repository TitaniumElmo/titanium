import csv
import itertools
import os
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from heitor.contrato import Achado

PERIODICIDADE_MESES = 12

_ids = itertools.count(1)


def exames_ligado() -> bool:
    return os.environ.get("HEITOR_EXAMES", "") == "1"


class ExameASO(BaseModel):
    funcionario_id: str
    nome: str
    funcao: str
    linha: int
    ativo: bool = True
    data_admissao: Optional[date] = None
    tipo_exame: Optional[str] = None
    data_exame: Optional[date] = None
    resultado: Optional[str] = None
    medico_nome: Optional[str] = None
    medico_crm: Optional[str] = None
    assinatura_medico: Optional[str] = None

    @property
    def tem_exame(self) -> bool:
        return bool(self.tipo_exame and self.data_exame)


def soma_meses(d: date, meses: int) -> date:
    total = d.year * 12 + (d.month - 1) + meses
    ano, mes = divmod(total, 12)
    return date(ano, mes + 1, min(d.day, monthrange(ano, mes + 1)[1]))


def _achado(f, linha, regra, gravidade, tipo, evidencia, acao):
    return Achado.model_construct(
        id=f"a-aso-{next(_ids)}", funcionario_id=f, linha=linha, regra=regra,
        gravidade=gravidade, tipo=tipo, evidencia=evidencia, acao_sugerida=acao,
        auditoria_id=None, norma="NR-7", exposicao_rs=None,
    )


def _br(d: date) -> str:
    return f"{d:%d/%m/%Y}"


def _achados_do_exame(e: ExameASO):
    f, n, tipo = e.funcionario_id, e.linha, e.tipo_exame
    achados = []
    if not (e.medico_nome or "").strip() or not (e.medico_crm or "").strip():
        achados.append(_achado(
            f, n, "aso_sem_medico", "risco", "prova",
            f"linha {n}, ASO {tipo} de {_br(e.data_exame)} sem nome ou CRM do médico",
            "pedir à clínica a via do ASO com os dados do médico"))
    ass = (e.assinatura_medico or "").strip().lower()
    if ass in ("nao", "não"):
        achados.append(_achado(
            f, n, "aso_sem_assinatura_medico", "irregular", "prova",
            f"linha {n}, ASO {tipo} de {_br(e.data_exame)} sem assinatura do médico",
            "pedir à clínica a via assinada do ASO"))
    elif ass == "ilegivel":
        achados.append(_achado(
            f, n, "aso_sem_assinatura_medico", "risco", "prova",
            f"linha {n}, assinatura do médico ilegível no ASO {tipo} de {_br(e.data_exame)}; conferir",
            "conferir a assinatura na via física do ASO"))
    if tipo == "admissional" and e.data_admissao and e.data_exame > e.data_admissao:
        achados.append(_achado(
            f, n, "aso_admissional_tardio", "irregular", "passivo",
            f"linha {n}, admissional feito em {_br(e.data_exame)}, depois do início em {_br(e.data_admissao)}",
            "registrar no relatório (não tem conserto)"))
    return achados


def _achados_do_funcionario(exames: list[ExameASO], hoje: date, meses: int):
    base = exames[0]
    f = base.funcionario_id
    feitos = sorted((e for e in exames if e.tem_exame), key=lambda e: e.data_exame)
    achados = []
    for e in feitos:
        achados += _achados_do_exame(e)
    if not base.ativo:
        return achados
    if not feitos:
        achados.append(_achado(
            f, None, "aso_ausente", "irregular", "corrigivel",
            f"{base.nome} está ativo e não tem nenhum ASO registrado",
            "agendar o exame médico ocupacional"))
        return achados
    ultimo = feitos[-1]
    venc = soma_meses(ultimo.data_exame, meses)
    if hoje > venc:
        achados.append(_achado(
            f, None, "aso_periodico_vencido", "irregular", "corrigivel",
            f"último ASO em {_br(ultimo.data_exame)}; periodicidade de {meses} meses venceu em {_br(venc)}",
            "agendar o exame periódico"))
    if (ultimo.resultado or "").strip().lower() == "inapto":
        achados.append(_achado(
            f, None, "aso_inapto_em_atividade", "irregular", "corrigivel",
            f"último ASO ({_br(ultimo.data_exame)}) indica inapto e o funcionário segue ativo sem novo ASO apto",
            "levar o caso ao médico do trabalho e definir a conduta antes de manter o funcionário na função"))
    return achados


def audita_aso(exames: list[ExameASO], hoje: Optional[date] = None, meses: int = PERIODICIDADE_MESES) -> list[Achado]:
    hoje = hoje or date.today()
    por_func: dict[str, list[ExameASO]] = {}
    for e in exames:
        por_func.setdefault(e.funcionario_id, []).append(e)
    achados = []
    for grupo in por_func.values():
        achados += _achados_do_funcionario(grupo, hoje, meses)
    return achados


def _data(valor):
    valor = (valor or "").strip()
    return date.fromisoformat(valor) if valor else None


def ler_aso_csv(caminho) -> list[ExameASO]:
    exames = []
    with open(Path(caminho), encoding="utf-8", newline="") as f:
        for n, r in enumerate(csv.DictReader(f), start=2):
            exames.append(ExameASO(
                funcionario_id=r["funcionario_id"].strip(), nome=r["nome"].strip(), funcao=r["funcao"].strip(),
                linha=n, ativo=r.get("situacao", "ativo").strip().lower() != "desligado",
                data_admissao=_data(r.get("data_admissao")),
                tipo_exame=(r.get("tipo_exame") or "").strip() or None, data_exame=_data(r.get("data_exame")),
                resultado=(r.get("resultado") or "").strip() or None,
                medico_nome=(r.get("medico_nome") or "").strip() or None,
                medico_crm=(r.get("medico_crm") or "").strip() or None,
                assinatura_medico=(r.get("assinatura_medico") or "").strip() or None,
            ))
    return exames


def audita_aso_csv(caminho, hoje: Optional[date] = None) -> list[dict]:
    return [a.model_dump(mode="json") for a in audita_aso(ler_aso_csv(caminho), hoje)]
