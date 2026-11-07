"""Avalia a leitura de fotos contra gabaritos.

Uso:
    python -m tests.avaliar_fotos <pasta_fotos> <pasta_gabaritos> [--filtro texto] [--modelo id] [--saida resumo.json]

Gabarito (formato de Projetos/caepi/gabarito e fotos_teste/gabaritos):
    {"entregas": [{"linha": 1, "data": "AAAA-MM-DD", "ca": "..." | null, "assinatura": ...}],
     "fotos": [{"arquivo": "foto.jpg", "linhas_visiveis": "cabecalho + 1-6"}]}

"assinatura" aceita:
    null ou "ausente"                                   -> linha SEM assinatura
    "presente" ou um nome ("José Carlos")               -> linha assinada
    "iniciais" | "x" | "falhada" | "texto" | "visto" | "outro_nome"  -> AMBÍGUA

A métrica que importa: linha sem assinatura (ou ambígua) aceita como "assinado com confiança".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

LIMIAR = 0.7
AMBIGUAS = {"iniciais", "x", "falhada", "texto", "visto", "outro_nome"}


def classe_assinatura(valor) -> str:
    if valor is None or str(valor).strip().lower() == "ausente":
        return "ausente"
    if str(valor).strip().lower() in AMBIGUAS:
        return "ambigua"
    return "presente"


def _visiveis(texto: str) -> set[int]:
    """'cabecalho + 1-6' -> {1..6}; '5-8, 10' -> {5,6,7,8,10}."""
    nums: set[int] = set()
    for a, b in re.findall(r"(\d+)\s*-\s*(\d+)", texto):
        nums |= set(range(int(a), int(b) + 1))
    for n in re.findall(r"(?<![\d-])(\d+)(?![\d-])", texto):
        nums.add(int(n))
    return nums


def carregar(pasta_fotos: Path, pasta_gab: Path, filtro: str = "") -> list[tuple[Path, list[dict]]]:
    casos = []
    for g in sorted(pasta_gab.glob("*.json")):
        gab = json.loads(g.read_text())
        for foto in gab.get("fotos", []):
            caminho = pasta_fotos / foto["arquivo"]
            if caminho.exists() and filtro in caminho.name:
                visiveis = _visiveis(foto.get("linhas_visiveis", ""))
                casos.append((caminho, [e for e in gab["entregas"] if not visiveis or e["linha"] in visiveis]))
    return casos


def casar(lidas: list[dict], esperadas: list[dict]) -> list[tuple[dict, dict | None]]:
    """Casa cada linha esperada com a lida mais parecida (data, CA e posição)."""
    livres = list(lidas)
    pares = []
    for i, esp in enumerate(esperadas):
        def nota(l: dict) -> float:
            return (2 * (l.get("data") == esp.get("data")) + 2 * bool(esp.get("ca") and l.get("ca") == esp.get("ca"))
                    - abs(lidas.index(l) - i) * 0.1)
        melhor = max(livres, key=nota, default=None)
        if melhor is not None and nota(melhor) > 0:
            livres.remove(melhor)
            pares.append((esp, melhor))
        else:
            pares.append((esp, None))
    return pares


def avaliar(pasta_fotos: Path, pasta_gab: Path, filtro: str = "", verboso: bool = True) -> dict:
    from heitor.agente.foto import MODELO_VISAO, ler_foto  # depois de definir o modelo no ambiente

    t: dict = {"modelo": MODELO_VISAO, "fotos": 0, "falhas_leitura": 0, "linhas": 0, "nao_casadas": 0,
               "data": 0, "ca": 0, "ca_esperados": 0, "presente": 0, "presente_ok": 0, "alarme_falso": 0,
               "ausente": 0, "ausente_pega": 0, "deixou_passar": 0, "ambigua": 0, "ambigua_pega": 0,
               "ambigua_aceita": 0, "ca_errado_sinalizado": 0, "ca_errado_silencioso": 0, "custo": 0.0, "segundos": 0.0, "por_foto": {}}
    for foto, esperadas in carregar(pasta_fotos, pasta_gab, filtro):
        t["fotos"] += 1
        inicio = time.time()
        try:
            r = ler_foto(foto)
        except Exception as e:  # noqa: BLE001
            t["falhas_leitura"] += 1
            t["linhas"] += len(esperadas)
            t["nao_casadas"] += len(esperadas)
            print(f"\n== {foto.name}: FALHOU ({type(e).__name__}: {str(e)[:100]})")
            continue
        seg = time.time() - inicio
        t["segundos"] += seg
        t["custo"] += r["custo_usd"]
        acertos_foto = 0
        if verboso:
            print(f"\n== {foto.name}: {len(r['linhas'])} lidas, {len(esperadas)} esperadas ({seg:.0f}s, ${r['custo_usd']:.4f})")
        for esp, lida in casar(r["linhas"], esperadas):
            t["linhas"] += 1
            classe = classe_assinatura(esp.get("assinatura"))
            t[classe] += 1
            if esp.get("ca"):
                t["ca_esperados"] += 1
            if lida is None:
                t["nao_casadas"] += 1
                if verboso:
                    print(f"   ✗ linha {esp['linha']}: não casou (esp data {esp.get('data')}, CA {esp.get('ca')})")
                continue
            conf = lida["confianca"].get("assinatura", 0)
            leu = lida.get("assinatura")
            aceitou = leu is True and conf >= LIMIAR
            t["data"] += lida.get("data") == esp.get("data")
            t["ca"] += bool(esp.get("ca")) and lida.get("ca") == esp.get("ca")
            if esp.get("ca") and lida.get("ca") and lida.get("ca") != esp.get("ca"):
                if lida["confianca"].get("ca", 1.0) < LIMIAR:
                    t["ca_errado_sinalizado"] += 1
                else:
                    t["ca_errado_silencioso"] += 1
            if classe == "presente":
                t["presente_ok"] += aceitou
                t["alarme_falso"] += leu is False and conf >= LIMIAR
                ok = aceitou
            elif classe == "ausente":
                t["ausente_pega"] += not aceitou
                t["deixou_passar"] += aceitou
                ok = not aceitou
            else:
                t["ambigua_pega"] += not aceitou
                t["ambigua_aceita"] += aceitou
                ok = not aceitou
            acertos_foto += ok
            if verboso:
                marca = "✓" if ok else "✗"
                print(f"   {marca} linha {esp['linha']}: data {lida.get('data')} (esp {esp.get('data')}) | "
                      f"CA {lida.get('ca')} (esp {esp.get('ca')}) | assinatura {leu} conf {conf:.2f} "
                      f"(esp {esp.get('assinatura')}) [{lida.get('assinatura_tipo')}: {lida.get('assinatura_texto')!r}]")
        t["por_foto"][foto.name] = f"{acertos_foto}/{len(esperadas)}"
    return t


def imprimir(t: dict) -> None:
    n = t["linhas"] or 1
    print(f"\n### {t['modelo']}: {t['fotos']} fotos, {t['linhas']} linhas, {t['segundos']:.0f}s, ${t['custo']:.4f}")
    print(f"    leitura: data {t['data']}/{n} | CA {t['ca']}/{t['ca_esperados']} | não casadas {t['nao_casadas']}"
          f" | fotos que falharam {t['falhas_leitura']}")
    print(f"    assinadas aceitas: {t['presente_ok']}/{t['presente']} (alarme falso {t['alarme_falso']})")
    print(f"    SEM assinatura pegas: {t['ausente_pega']}/{t['ausente']}  ⚠️ deixou passar: {t['deixou_passar']}")
    print(f"    ambíguas pegas: {t['ambigua_pega']}/{t['ambigua']}  (aceitas como assinado: {t['ambigua_aceita']})")
    print(f"    CA lido errado: sinalizado {t['ca_errado_sinalizado']} | ⚠️ em silêncio {t['ca_errado_silencioso']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta_fotos", type=Path)
    ap.add_argument("pasta_gabaritos", type=Path)
    ap.add_argument("--filtro", default="")
    ap.add_argument("--modelo")
    ap.add_argument("--saida", type=Path)
    ap.add_argument("-q", "--quieto", action="store_true")
    a = ap.parse_args()
    if a.modelo:
        # Sem reserva: uma falha do modelo testado não pode ser mascarada por outro modelo.
        os.environ["HEITOR_MODELO_VISAO"] = os.environ["HEITOR_MODELO_VISAO_RESERVA"] = a.modelo
    t = avaliar(a.pasta_fotos, a.pasta_gabaritos, a.filtro, verboso=not a.quieto)
    imprimir(t)
    if a.saida:
        a.saida.write_text(json.dumps(t, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
