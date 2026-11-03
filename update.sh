#!/bin/sh
# Publicaties bijwerken vanuit in de browser opgeslagen Pure-bestanden.
# Zie scripts/update_from_browser.py voor de werkwijze.
cd "$(dirname "$0")" || exit 1

[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }

.venv/bin/python scripts/update_from_browser.py
status=$?
[ $status -eq 1 ] && exit 1

if git diff --quiet -- publications.json; then
  exit 0
fi

git add publications.json
git commit -q -m "Update publications" && git pull -q --rebase && git push -q \
  && echo "Gepusht. De site is over een minuut of twee bijgewerkt."
[ $status -eq 3 ] && echo "Let op: niet alle nieuwe publicaties zijn al toegevoegd (zie hierboven)."
exit 0
