#!/usr/bin/env bash
# Package Lambda functions and common layer for deployment.
# Usage: ./scripts/package-lambdas.sh <output-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAMBDA_SRC="$PROJECT_ROOT/src/lambda"
OUTPUT_DIR="${1:-$PROJECT_ROOT/deployment}"

echo "=== Packaging Lambda Functions ==="
echo "Source: $LAMBDA_SRC"
echo "Output: $OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Package common layer
echo "--- Packaging common layer ---"
LAYER_DIR=$(mktemp -d)
LAYER_PYTHON="$LAYER_DIR/python"
mkdir -p "$LAYER_PYTHON/common"
cp "$LAMBDA_SRC/common/"*.py "$LAYER_PYTHON/common/"

# Install requirements into layer
if [ -f "$LAMBDA_SRC/requirements.txt" ]; then
    pip install -r "$LAMBDA_SRC/requirements.txt" -t "$LAYER_PYTHON" --quiet
fi

(cd "$LAYER_DIR" && zip -r "$OUTPUT_DIR/common-layer.zip" python/ -q)
rm -rf "$LAYER_DIR"
echo "  Created: common-layer.zip"

# Package each Lambda function
for func_dir in list_objects transfer_object validate_transfer generate_report; do
    echo "--- Packaging $func_dir ---"
    FUNC_DIR=$(mktemp -d)
    cp -r "$LAMBDA_SRC/$func_dir" "$FUNC_DIR/"

    (cd "$FUNC_DIR" && zip -r "$OUTPUT_DIR/${func_dir//_/-}.zip" "$func_dir/" -q)
    rm -rf "$FUNC_DIR"
    echo "  Created: ${func_dir//_/-}.zip"
done

echo ""
echo "=== Packaging Complete ==="
ls -lh "$OUTPUT_DIR"/*.zip
