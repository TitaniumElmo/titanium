"""Avalia a leitura de fotos contra gabaritos.

Uso:
    python -m tests.avaliar_fotos <pasta_fotos> <pasta_gabaritos> [filtro]

Formato do gabarito (o mesmo de Projetos/caepi/gabarito):
    {"ficha_id": "...", "entregas": [{"linha": 1, "data": "AAAA-MM-DD", "epi": "...", "ca": "..." | null,
     "assinatura": "Nome" | null}], "fotos": [{"arquivo": "foto.jpg", "linhas_visiveis": "..."}]}

A métrica que importa: linhas SEM assinatura que o Heitor deixou passar como "assinado com confiança".
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from heitor.agente.foto import ler_foto

LIMIAR = 0.7


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


def _visiveis(texto: str) -> set[int]:
    """'cabecalho + 1-6' -> {1..6}; '5-8, 10' -> {5,6,7,8,10}."""
    nums: set[int] = set()
    for a, b in re.findall(r"(\d+)\s*-\s*(\d+)", texto):
        nums |= set(range(int(a), int(b) + 1))
    for n in re.findall(r"(?<![\d-])(\d+)(?![\d-])", texto):
        nums.add(int(n))
    return nums


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


def main() -> None:
    pasta_fotos, pasta_gab = Path(sys.argv[1]), Path(sys.argv[2])
    filtro = sys.argv[3] if len(sys.argv) > 3 else ""
    tot = {"linhas": 0, "data": 0, "ca": 0, "ass_certa": 0, "sem": 0, "sem_pega": 0, "deixou_passar": 0,
           "alarme_falso": 0, "custo": 0.0}
    for foto, esperadas in carregar(pasta_fotos, pasta_gab, filtro):
        t = time.time()
        r = ler_foto(foto)
        tot["custo"] += r["custo_usd"]
        print(f"\n== {foto.name}: {len(r['linhas'])} linhas lidas, {len(esperadas)} esperadas "
              f"({time.time() - t:.0f}s, ${r['custo_usd']:.4f})")
        pares = casar(r["linhas"], esperadas)
        usadas = {id(l) for _, l in pares if l}
        for l in r["linhas"]:
            if id(l) not in usadas:
                print(f"   · lida e não casada: data {l.get('data')} | {l.get('epi')} | CA {l.get('ca')}")
        for esp, lida in pares:
            tot["linhas"] += 1
            assinou = esp.get("assinatura") is not None
            if not assinou:
                tot["sem"] += 1
            if lida is None:
                print(f"   ✗ linha {esp['linha']}: não casou (esp data {esp.get('data')}, CA {esp.get('ca')})")
                continue
            conf = lida["confianca"].get("assinatura", 0)
            tot["data"] += lida.get("data") == esp.get("data")
            tot["ca"] += lida.get("ca") == esp.get("ca")
            tot["ass_certa"] += lida.get("assinatura") == assinou
            if not assinou and (lida.get("assinatura") is False or conf < LIMIAR):
                tot["sem_pega"] += 1
            if not assinou and lida.get("assinatura") is True and conf >= LIMIAR:
                tot["deixou_passar"] += 1
            if assinou and lida.get("assinatura") is False and conf >= LIMIAR:
                tot["alarme_falso"] += 1
            marca = "✓" if lida.get("assinatura") == assinou else ("?" if conf < LIMIAR else "✗")
            print(f"   {marca} linha {esp['linha']}: data {lida.get('data')} (esp {esp.get('data')}) | "
                  f"CA {lida.get('ca')} (esp {esp.get('ca')}) | assinatura {lida.get('assinatura')} "
                  f"conf {conf:.2f} A/B {list((lida.get('leitura_assinatura') or {}).values())} (esp {assinou})")
    n = tot["linhas"] or 1
    print(f"\n### {tot['linhas']} linhas | data {tot['data']}/{n} | CA {tot['ca']}/{n} | "
          f"assinatura {tot['ass_certa']}/{n} | custo ${tot['custo']:.4f}")
    print(f"    sem assinatura pegas (sem ou baixa confiança): {tot['sem_pega']}/{tot['sem']}")
    print(f"    ⚠️  deixou passar (disse assinado com confiança): {tot['deixou_passar']}")
    print(f"    alarme falso (disse sem assinatura com confiança): {tot['alarme_falso']}")


if __name__ == "__main__":
    main()
