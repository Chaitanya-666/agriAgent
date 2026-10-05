#!/usr/bin/env bash
# Downloads 50 cotton + 50 sugar beet PHOTOS into tests/fixtures/
# Needs: pip install kaggle, and: export KAGGLE_API_TOKEN=...
cd "$(dirname "$0")/.."

COTTON=yuzhenlu/cottonweeddet3
BEET=wangyongkun/sugarbeetsandweeds
N=50
mkdir -p tests/fixtures/cotton tests/fixtures/sugarbeet

echo "== Cotton photos =="
kaggle datasets files $COTTON --page-size 200 | awk '{print $1}' \
  | grep 'annotations/.*\.json$' | head -$N > /tmp/cotton_names.txt
while read -r p; do
  n=$(basename "$p" .json)
  [ -f "tests/fixtures/cotton/$n.jpg" ] && continue
  for ext in jpg jpeg png; do
    if kaggle datasets download -d $COTTON -f "CottonWeedDet3/images/$n.$ext" -p tests/fixtures/cotton --unzip >/dev/null 2>&1; then
      break
    fi
  done
  ls tests/fixtures/cotton/$n.* >/dev/null 2>&1 || echo "FAILED $n"
done < /tmp/cotton_names.txt

echo "== Sugar beet photos =="
kaggle datasets files $BEET --page-size 200 | awk '{print $1}' \
  | grep -Ei '\.(jpg|jpeg|png)$' | head -$N > /tmp/beet_imgs.txt
while read -r p; do
  kaggle datasets download -d $BEET -f "$p" -p tests/fixtures/sugarbeet --unzip >/dev/null 2>&1 || echo "FAILED $p"
done < /tmp/beet_imgs.txt

echo "Cotton photos:    $(ls tests/fixtures/cotton | grep -Ei '\.(jpg|jpeg|png)$' | wc -l)"
echo "Sugarbeet photos: $(ls tests/fixtures/sugarbeet | grep -Ei '\.(jpg|jpeg|png)$' | wc -l)"
