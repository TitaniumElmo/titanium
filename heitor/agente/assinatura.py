"""Confere o que está escrito na coluna Assinatura contra o nome do funcionário (sem LLM).

O modelo de visão transcreve a célula; aqui o código decide o que aquilo é:
    nome_confere  "Fábio", "sim José" (com "sim" riscado), "Falio" (leitura imperfeita)
    iniciais      "LAM" para Lucas Andrade Melo
    outro_nome    "Marcos" na ficha do Fábio; "Marcelo" na ficha do Marcos
    texto         "entregue", "ok", "recebido": palavra que não é assinatura
    marca         "✓", "x": sinal, não assinatura
    vazio         célula em branco
    ilegivel      o modelo não conseguiu ler
"""

from __future__ import annotations

import difflib
import re
import unicodedata

SIMILARIDADE_MINIMA = 0.8  # "marcelo" x "marcos" = 0,77 (não confere); "falio" x "fabio" = 0,8 (confere)

PALAVRAS_NAO_ASSINATURA = {
    "entregue", "entregues", "entregou", "recebido", "recebi", "recebeu", "ok", "sim", "nao", "conferido",
    "visto", "pago", "feito", "assinado", "assinatura", "funcionario",
}
MARCAS = {"✓", "✔", "√", "v", "x", "×", "✗", "*", "check", "visto", "tick", "checkmark"}
# Pontinho ou traço sozinho conta como célula vazia (gabarito: "pontinho de caneta não conta").
VAZIOS = {"", "vazio", "em branco", "branco", "null", "none", "nenhuma", "sem assinatura"}
ILEGIVEIS = {"ilegivel", "?", "rabisco ilegivel"}


def _norm(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9✓✔√×✗ ]", " ", s)).strip()


def _parecido(a: str, b: str) -> float:
    """Similaridade, aceitando o nome contido na escrita ("tayabio" contém algo como "fabio")."""
    melhor = difflib.SequenceMatcher(None, a, b).ratio()
    if len(a) > len(b) >= 4:
        for tam in (len(b) - 1, len(b), len(b) + 1):
            for i in range(0, len(a) - tam + 1):
                melhor = max(melhor, difflib.SequenceMatcher(None, a[i:i + tam], b).ratio())
    return melhor


def classificar_linhas(textos: list[str | None], nome_cabecalho: str | None) -> list[str]:
    """Classifica a coluna inteira de uma vez.

    O nome do cabeçalho também é manuscrito e pode ser lido errado ("Manoel" no lugar de "Marcos").
    As assinaturas se repetem: o nome que aparece em pelo menos 2 linhas também vale como referência.
    "Outro nome" é só o que destoa do cabeçalho E da maioria.
    """
    primeiros = []
    for t in textos:
        if t is None or str(t).strip().lower() in MARCAS or _norm(str(t)) in VAZIOS | ILEGIVEIS:
            continue  # "vazio" não pode virar o "nome mais repetido" da coluna
        tokens = [x for x in _norm(str(t)).split() if x not in PALAVRAS_NAO_ASSINATURA and len(x) > 2]
        if tokens:
            primeiros.append(tokens[0])
    maioria = None
    if primeiros:
        candidato = max(set(primeiros), key=lambda p: sum(_parecido(q, p) >= SIMILARIDADE_MINIMA for q in primeiros))
        if sum(_parecido(q, candidato) >= SIMILARIDADE_MINIMA for q in primeiros) >= 2:
            maioria = candidato
    referencia = " ".join(x for x in (nome_cabecalho, maioria) if x)
    return [classificar(t, referencia) for t in textos]


def classificar(texto: str | None, nome_funcionario: str | None) -> str:
    if texto is None:
        return "ilegivel"
    bruto = str(texto).strip()
    if bruto.lower() in MARCAS:  # antes de normalizar: a normalização apaga símbolos como ✓
        return "marca"
    n = _norm(bruto)
    if n in VAZIOS:
        return "vazio"
    if n in ILEGIVEIS:
        return "ilegivel"
    if n in MARCAS:
        return "marca"
    tokens = [t for t in n.split() if t not in PALAVRAS_NAO_ASSINATURA]
    if not tokens:
        return "texto"  # só palavras como "entregue", "ok"
    nome = [t for t in _norm(nome_funcionario or "").split() if len(t) > 2]
    if not nome:
        return "nome_confere"  # sem nome no cabeçalho não há com o que comparar: fica a presença
    junto = "".join(tokens)
    iniciais = "".join(t[0] for t in nome)
    so_letras = re.sub(r"[^A-Za-z]", "", bruto)
    if 2 <= len(junto) <= 4 and junto.isalpha() and (
        junto in (iniciais, iniciais[:2], iniciais[0] + iniciais[-1])
        or (so_letras.isupper() and junto[0] == iniciais[0])  # "LAM" quando só se conhece "Lucas"
    ):
        return "iniciais"
    if any(_parecido(t, p) >= SIMILARIDADE_MINIMA for t in tokens if len(t) > 2 for p in nome):
        return "nome_confere"
    if len(junto) <= 2:
        return "marca"
    return "outro_nome"


# Como cada tipo vira assinatura e confiança na Linha do contrato.
# Confiança < 0,7 vira "risco" na auditoria; "texto" com confiança alta vira "irregular".
EFEITO = {
    "texto": (False, 0.9),
    "marca": (False, 0.5),
    "iniciais": (False, 0.5),
    "outro_nome": (False, 0.5),
}

EXPLICACAO = {
    "texto": "na coluna de assinatura há texto ('{t}'), não uma assinatura",
    "marca": "na coluna de assinatura há só uma marca ('{t}')",
    "iniciais": "assinatura só com iniciais ('{t}')",
    "outro_nome": "assinado '{t}', diferente do nome do funcionário",
    "sem_linha_na_ficha": "entrega registrada na planilha sem linha na ficha de papel (falta a prova da entrega)",
}
