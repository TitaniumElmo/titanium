#!/usr/bin/env bash
# Rode na sua branch antes de abrir PR:  scripts/antes_do_pr.sh        (sem IA, grátis)
#                                        scripts/antes_do_pr.sh --ia   (inclui o E2E com IA e foto)
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
falhou=0

echo "== 1/3 branch atualizada com a main?"
git fetch -q origin main && atras=$(git rev-list --count HEAD..origin/main)
if [ "$atras" -gt 0 ]; then echo "   ⚠️  sua branch está $atras commit(s) atrás da main: rode 'git pull origin main' antes do PR"; falhou=1; else echo "   ok"; fi

echo "== 2/3 testes + E2E do roteiro da demo (sem IA)"
HEITOR_LLM=off $PY -m pytest -q -p no:logging || falhou=1
if ! ls dados/RelatorioCA_*.csv >/dev/null 2>&1; then
  echo "   (sem a base CAEPI em dados/: o E2E rodou com os stubs de regras; testes que exigem a base foram pulados)"
fi

if [ "${1:-}" = "--ia" ]; then
  echo "== 3/3 E2E com IA e foto real"
  HEITOR_E2E=1 $PY -m pytest -q -p no:logging -m e2e || falhou=1
else
  echo "== 3/3 E2E com IA: pulado (use --ia)"
fi

if [ $falhou -eq 0 ]; then echo; echo "✅ pode abrir o PR"; else echo; echo "❌ resolva antes de abrir o PR"; fi
exit $falhou
