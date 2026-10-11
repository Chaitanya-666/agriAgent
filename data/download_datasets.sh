#!/usr/bin/env bash
# Downloads representative cotton and sugar beet field imagery and annotations
# Requires: pip install kaggle, and: export KAGGLE_API_TOKEN=... or ~/.kaggle/kaggle.json
set -euo pipefail

cd "$(dirname "$0")/.."

COTTON="yuzhenlu/cottonweeddet3"
BEET="wangyongkun/sugarbeetsandweeds"
N=50

TARGET_COTTON="tests/fixtures/cotton"
TARGET_BEET="tests/fixtures/sugarbeet"
TARGET_ANNOTATIONS="tests/fixtures/annotations"
TARGET_MANIFESTS="data/manifests"

mkdir -p "$TARGET_COTTON" "$TARGET_BEET" "$TARGET_ANNOTATIONS/cotton" "$TARGET_ANNOTATIONS/sugarbeet" "$TARGET_MANIFESTS"

echo "=== AgriAgent Dataset Downloader ==="
echo "Target directories initialized:"
echo " - Cotton Images      : $TARGET_COTTON"
echo " - Sugar Beet Images  : $TARGET_BEET"
echo " - Annotations        : $TARGET_ANNOTATIONS"
echo " - Manifests          : $TARGET_MANIFESTS"

if ! command -v kaggle >/dev/null 2>&1; then
  echo "WARNING: kaggle CLI is not installed or not in PATH."
  echo "Install via: pip install kaggle"
  echo "Ensure credentials exist in ~/.kaggle/kaggle.json or via KAGGLE_USERNAME / KAGGLE_KEY."
  exit 0
fi

# Check credentials
if [ ! -f ~/.kaggle/kaggle.json ] && [ -z "${KAGGLE_USERNAME:-}" ]; then
  echo "WARNING: Kaggle credentials not detected in ~/.kaggle/kaggle.json or environment variables."
  echo "Skipping live download. Existing fixtures will be retained."
  exit 0
fi

echo "== Downloading Cotton field photos & annotation JSONs =="
COTTON_LIST="/tmp/agriagent_cotton_annotations.txt"
kaggle datasets files "$COTTON" --page-size 200 | awk '{print $1}' \
  | grep 'annotations/.*\.json$' | head -"$N" > "$COTTON_LIST" || true

if [ -s "$COTTON_LIST" ]; then
  while read -r anno_path; do
    [ -z "$anno_path" ] && continue
    base_name=$(basename "$anno_path" .json)
    
    # 1. Download annotation JSON
    if [ ! -f "$TARGET_ANNOTATIONS/cotton/$base_name.json" ]; then
      kaggle datasets download -d "$COTTON" -f "$anno_path" -p "$TARGET_ANNOTATIONS/cotton" --unzip >/dev/null 2>&1 || true
    fi

    # 2. Download corresponding image
    if [ ! -f "$TARGET_COTTON/$base_name.jpg" ] && [ ! -f "$TARGET_COTTON/$base_name.png" ]; then
      for ext in jpg jpeg png JPG; do
        if kaggle datasets download -d "$COTTON" -f "CottonWeedDet3/images/$base_name.$ext" -p "$TARGET_COTTON" --unzip >/dev/null 2>&1; then
          break
        fi
      done
    fi
  done < "$COTTON_LIST"
  rm -f "$COTTON_LIST"
else
  echo "Note: No cotton annotation list retrieved from Kaggle (check rate limits/network)."
fi

echo "== Downloading Sugar beet field photos & annotations =="
BEET_LIST="/tmp/agriagent_beet_files.txt"
kaggle datasets files "$BEET" --page-size 200 | awk '{print $1}' > "$BEET_LIST" || true

if [ -s "$BEET_LIST" ]; then
  # Download images
  grep -Ei '\.(jpg|jpeg|png)$' "$BEET_LIST" | head -"$N" | while read -r img_path; do
    [ -z "$img_path" ] && continue
    base_name=$(basename "$img_path")
    if [ ! -f "$TARGET_BEET/$base_name" ]; then
      kaggle datasets download -d "$BEET" -f "$img_path" -p "$TARGET_BEET" --unzip >/dev/null 2>&1 || true
    fi
  done

  # Download annotations/masks if present in dataset
  grep -Ei '(annotation|label|mask|xml|json).*\.(json|xml|png)$' "$BEET_LIST" | head -"$N" | while read -r anno_path; do
    [ -z "$anno_path" ] && continue
    kaggle datasets download -d "$BEET" -f "$anno_path" -p "$TARGET_ANNOTATIONS/sugarbeet" --unzip >/dev/null 2>&1 || true
  done
  rm -f "$BEET_LIST"
else
  echo "Note: No sugar beet file list retrieved from Kaggle."
fi

echo "=== Download Summary ==="
echo "Cotton photos        : $(find "$TARGET_COTTON" -maxdepth 1 -type f 2>/dev/null | wc -l)"
echo "Cotton annotations   : $(find "$TARGET_ANNOTATIONS/cotton" -maxdepth 1 -type f 2>/dev/null | wc -l)"
echo "Sugar beet photos    : $(find "$TARGET_BEET" -maxdepth 1 -type f 2>/dev/null | wc -l)"
echo "Sugar beet annos/masks: $(find "$TARGET_ANNOTATIONS/sugarbeet" -maxdepth 1 -type f 2>/dev/null | wc -l)"
