"""Assinatura por linha SEM modelo de linguagem: grade do formulário (OpenCV) + YOLO ou tinta.

Só funciona em ficha impressa com grade. Passos:
  1. endireita a foto (ângulo das linhas impressas, via Hough);
  2. acha as linhas horizontais e verticais da tabela -> faixas de cada linha e a coluna Assinatura;
  3. método YOLO: detecções de assinatura na folha inteira, contadas na linha onde cai o centro
     (só as que caem dentro da coluna Assinatura);
  4. método tinta: fração de pixels escuros na célula de assinatura (sem as linhas da grade).

Fora do requirements.txt (só este script usa): pip install onnxruntime opencv-python-headless numpy

Uso:
    python -m tests.avaliar_yolo <pasta_fotos> <pasta_modelos_onnx> <pasta_gabaritos> [mais pastas de gabarito...]
Imagens de depuração vão para --debug <pasta>.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from tests.avaliar_fotos import classe_assinatura

LIMIAR_YOLO = 0.25


# ------------------------------------------------------------------ grade ---

def endireitar(img: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bordas = cv2.Canny(g, 50, 150)
    H, W = g.shape
    linhas = cv2.HoughLinesP(bordas, 1, np.pi / 720, threshold=150, minLineLength=W // 4, maxLineGap=10)
    if linhas is None:
        return img
    angulos = []
    for x1, y1, x2, y2 in np.asarray(linhas).reshape(-1, 4):  # formato muda entre versões do OpenCV
        a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -45 < a < 45:
            angulos.append(a)
    if not angulos:
        return img
    a = float(np.median(angulos))
    M = cv2.getRotationMatrix2D((W / 2, H / 2), a, 1.0)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))


def _agrupar(posicoes: np.ndarray, distancia: int = 6) -> list[int]:
    grupos: list[list[int]] = []
    for p in posicoes:
        if grupos and p - grupos[-1][-1] <= distancia:
            grupos[-1].append(int(p))
        else:
            grupos.append([int(p)])
    return [int(np.mean(g)) for g in grupos]


def grade(img: np.ndarray) -> dict | None:
    """-> {"faixas": [(y1, y2)...] das linhas de dados, "coluna": (x1, x2), "mascara_grade": bin, "tinta": bin}"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = g.shape
    # Linhas do formulário são cinza-claro: limiar adaptativo mais sensível.
    tinta = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 7)
    ver = cv2.morphologyEx(tinta, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, H // 12)))
    xs = [x for x in _agrupar(np.where(ver.sum(axis=0) > 255 * H * 0.1)[0]) if 4 < x < W - 4]
    # Layout do formulário: a coluna Assinatura começa na última vertical antes de 80% da largura
    # e vai até a vertical seguinte (ou a borda da foto, se a tabela foi cortada).
    esquerdas = [x for x in xs if x < 0.8 * W]
    if len(esquerdas) < 3:
        return None
    x1 = esquerdas[-1]
    x2 = next((x for x in xs if x > x1 + 0.1 * W), W - 1)
    # topo e base da tabela: onde existe a vertical Motivo|Assinatura
    col = ver[:, max(0, x1 - 3): x1 + 4].max(axis=1)
    ys_col = np.where(col > 0)[0]
    if ys_col.size == 0:
        return None
    topo, base = int(ys_col.min()), int(ys_col.max())
    larg = x2 - x1
    hor = cv2.morphologyEx(tinta, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, larg // 2), 1)))
    ys = _agrupar(np.where(hor[:, x1:x2].sum(axis=1) > 255 * larg * 0.5)[0])
    ys = [y for y in ys if topo - 8 <= y <= base + 8]
    if len(ys) < 4:
        return None
    faixas = list(zip(ys[1:-1], ys[2:]))  # pula a faixa do cabeçalho ("Assinatura do funcionário")
    return {"faixas": faixas, "coluna": (x1, x2), "grade": cv2.bitwise_or(hor, ver), "tinta": tinta}


def tinta_na_celula(info: dict, faixa: tuple[int, int]) -> float:
    (y1, y2), (x1, x2) = faixa, info["coluna"]
    my, mx = max(3, (y2 - y1) // 10), max(4, (x2 - x1) // 30)
    cel = info["tinta"][y1 + my: y2 - my, x1 + mx: x2 - mx]
    linhas = cv2.dilate(info["grade"], np.ones((5, 5), np.uint8))[y1 + my: y2 - my, x1 + mx: x2 - mx]
    so_tinta = cv2.bitwise_and(cel, cv2.bitwise_not(linhas))
    return float((so_tinta > 0).mean()) if so_tinta.size else 0.0


# ------------------------------------------------------------------- YOLO ---

def yolo(sess, img: np.ndarray) -> list[tuple[float, float, float, float, float]]:
    """-> [(x1, y1, x2, y2, conf)] em coordenadas da imagem. Pré-processamento do handler.py oficial."""
    H, W = img.shape[:2]
    rgb = cv2.cvtColor(cv2.resize(img, (640, 640)), cv2.COLOR_BGR2RGB)
    x = rgb.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0].T
    conf = out[:, 4:].max(1)
    keep = conf > LIMIAR_YOLO
    caixas, conf = out[keep, :4], conf[keep]
    rx, ry = W / 640, H / 640
    xyxy = [((cx - w / 2) * rx, (cy - h / 2) * ry, (cx + w / 2) * rx, (cy + h / 2) * ry)
            for cx, cy, w, h in caixas]
    idx = cv2.dnn.NMSBoxes([[a, b, c - a, d - b] for a, b, c, d in xyxy], conf.tolist(), LIMIAR_YOLO, 0.45)
    return [(*xyxy[i], float(conf[i])) for i in np.array(idx).flatten()]


def yolo_por_faixa(caixas, info: dict) -> list[float]:
    (cx1, cx2) = info["coluna"]
    resultado = []
    for y1, y2 in info["faixas"]:
        confs = [c for a, b, d, e, c in caixas if cx1 - 20 <= (a + d) / 2 <= cx2 and y1 <= (b + e) / 2 <= y2]
        resultado.append(max(confs, default=0.0))
    return resultado


# -------------------------------------------------------------- avaliação ---

def main() -> None:
    import onnxruntime as ort

    ap = argparse.ArgumentParser()
    ap.add_argument("pasta_fotos", type=Path)
    ap.add_argument("pasta_modelos", type=Path)
    ap.add_argument("gabaritos", type=Path, nargs="+")
    ap.add_argument("--debug", type=Path)
    ap.add_argument("--saida", type=Path)
    a = ap.parse_args()

    modelos = {p.stem: ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
               for p in sorted(a.pasta_modelos.glob("*.onnx"))}
    registros = []  # (foto, linha, classe, tinta, {modelo: conf})
    for pasta in a.gabaritos:
        for gfile in sorted(pasta.glob("*.json")):
            gab = json.loads(gfile.read_text())
            for foto in gab.get("fotos", []):
                caminho = a.pasta_fotos / foto["arquivo"]
                if not caminho.exists():
                    continue
                img = endireitar(cv2.imread(str(caminho)))
                info = grade(img)
                if not info:
                    print(f"{caminho.name}: sem grade de formulário, pulando")
                    continue
                confs = {m: yolo_por_faixa(yolo(s, img), info) for m, s in modelos.items()}
                print(f"\n== {caminho.name}: {len(info['faixas'])} faixas na tabela")
                for e in gab["entregas"]:
                    i = e.get("linha_fisica", e["linha"]) - 1
                    if i >= len(info["faixas"]):
                        continue
                    t = tinta_na_celula(info, info["faixas"][i])
                    c = {m: confs[m][i] for m in modelos}
                    cl = classe_assinatura(e.get("assinatura"))
                    registros.append((caminho.name, e["linha"], cl, t, c))
                    print(f"   linha {e['linha']:>2} {cl:8} ({e.get('assinatura')!s:10}) tinta {t:.3f} | "
                          + " | ".join(f"{m} {v:.2f}" for m, v in c.items()))
                if a.debug:
                    a.debug.mkdir(parents=True, exist_ok=True)
                    d = img.copy()
                    x1, x2 = info["coluna"]
                    for y1, y2 in info["faixas"]:
                        cv2.rectangle(d, (x1, y1), (x2, y2), (0, 200, 0), 2)
                    for (bx1, by1, bx2, by2, c) in yolo(modelos[next(iter(modelos))], img):
                        cv2.rectangle(d, (int(bx1), int(by1)), (int(bx2), int(by2)), (0, 0, 255), 2)
                    cv2.imwrite(str(a.debug / caminho.name), d)

    print("\n### Resumo (presente deve ser aceito; ausente e ambígua NÃO)")
    metodos = {f"yolo {m}": (lambda r, m=m: r[4][m] >= LIMIAR_YOLO) for m in modelos}
    for limiar in (0.01, 0.02, 0.03, 0.05):
        metodos[f"tinta > {limiar}"] = lambda r, l=limiar: r[3] > l
    for nome, aceita in metodos.items():
        n = {c: sum(1 for r in registros if r[2] == c) for c in ("presente", "ausente", "ambigua")}
        ok_p = sum(1 for r in registros if r[2] == "presente" and aceita(r))
        pega_a = sum(1 for r in registros if r[2] == "ausente" and not aceita(r))
        pega_m = sum(1 for r in registros if r[2] == "ambigua" and not aceita(r))
        print(f"  {nome:22} assinadas aceitas {ok_p}/{n['presente']} | SEM pegas {pega_a}/{n['ausente']} "
              f"| ambíguas pegas {pega_m}/{n['ambigua']}")
    if a.saida:
        a.saida.write_text(json.dumps(registros, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
