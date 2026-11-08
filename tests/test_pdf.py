"""PDF como ficha (o RH pode mandar a ficha arquivada assim) e documento que não é ficha.

A leitura de cada página é a da foto (modelo de visão); aqui ela é trocada por uma falsa, sem rede.
"""

import os

os.environ["HEITOR_LLM"] = "off"

from PIL import Image  # noqa: E402

from heitor.agente import ferramentas as F, foto  # noqa: E402
from heitor.agente.extracao import extrair_ficha, paginas_do_pdf  # noqa: E402
from heitor.agente.grafo import reauditar  # noqa: E402
from heitor.contrato import Linha  # noqa: E402


def _pdf(caminho, paginas):
    imgs = [Image.new("RGB", (600, 400), "white") for _ in range(paginas)]
    imgs[0].save(caminho, "PDF", save_all=True, append_images=imgs[1:])
    return caminho


def _leitura_falsa(por_pagina):
    """por_pagina: {n_da_pagina: [(epi, data)]}; página 1 com cabeçalho, as outras sem (continuação)."""
    def ler_foto(png):
        n = int(png.stem.rsplit("_p", 1)[1])
        fid = "0310" if n == 1 else png.stem  # sem cabeçalho, a leitura real usa o nome do arquivo
        linhas = [{"funcionario_id": fid, "nome": "Fábio" if n == 1 else "", "funcao": "pedreiro" if n == 1 else "",
                   "linha": i, "data": d, "epi": e, "qtd": 1, "ca": "17664", "motivo": None, "assinatura": True,
                   "confianca": {}, "origem": png.name} for i, (e, d) in enumerate(por_pagina.get(n, []), start=1)]
        return {"linhas": linhas, "cabecalho": {"nome": "Fábio"} if n == 1 else {}, "custo_usd": 0.001, "modelo": "falso"}
    return ler_foto


def test_pdf_vira_paginas(tmp_path):
    pngs = paginas_do_pdf(_pdf(tmp_path / "ficha.pdf", 6))
    assert [p.name for p in pngs] == [f"ficha_p{i}.png" for i in range(1, 5)]  # no máximo 4 páginas
    assert all(p.exists() for p in pngs)


def test_pdf_de_ficha_le_todas_as_paginas_como_uma_ficha(tmp_path, monkeypatch):
    monkeypatch.setattr(foto, "ler_foto", _leitura_falsa({
        1: [("protetor auditivo", "2026-01-10"), ("capacete", "2026-01-10")],
        2: [("protetor auditivo", "2026-07-10")],
    }))
    r = extrair_ficha(str(_pdf(tmp_path / "ficha_0310.pdf", 2)))
    linhas = r["linhas"]
    assert [l["linha"] for l in linhas] == [1, 2, 3]
    assert {l["funcionario_id"] for l in linhas} == {"0310"}  # a página 2 continua a ficha da 1
    assert r["mapeamento"]["origem"] == "pdf" and r["mapeamento"]["paginas"] == 2
    for l in linhas:
        Linha.model_validate(l)


def _leitura_da_nota(png):
    """O que o Qwen2.5-VL leu de verdade numa nota fiscal de teste (08/11): os itens viram "linhas" sem dono."""
    itens = [("Botina de segurança bico PVC", "28499"), ("Protetor auditivo plug silicone", "17664")]
    return {"linhas": [{"funcionario_id": png.stem, "nome": "", "funcao": "", "linha": i, "data": None, "epi": e,
                        "qtd": 1, "ca": ca, "motivo": None, "assinatura": False, "confianca": {}, "origem": png.name}
                       for i, (e, ca) in enumerate(itens, start=1)],
            "cabecalho": {}, "custo_usd": 0.004, "modelo": "falso"}


def test_documento_sem_ficha_fica_aguardando_e_nao_reabre(tmp_path, monkeypatch):
    """Nota fiscal em PDF: nenhuma entrega DESTE funcionário. Reabrir diria "não corrigiu" sem saber."""
    monkeypatch.setattr(foto, "ler_foto", _leitura_da_nota)
    linhas = extrair_ficha(str(_pdf(tmp_path / "nota_fiscal.pdf", 1)))["linhas"]
    assert len(linhas) == 2 and all(l["funcionario_id"] != "0402" for l in linhas)

    achado = {"id": "a-1", "funcionario_id": "0402", "linha": 1, "regra": "ca_vencido", "gravidade": "risco",
              "tipo": "prova", "evidencia": "CA vencido na entrega", "acao_sugerida": "pedir nota fiscal ao RH"}
    achado["auditoria_id"] = "au-pdf"
    p = F.IMPL["criar_pendencia"](achado, "rh", "pedir nota fiscal ao RH", "2026-11-12")
    r = reauditar(p["id"], linhas)
    assert r["status"] not in ("reaberta", "fechada")
    assert "conferência humana" in r["motivo"]

