#!/usr/bin/env bash
# Validate all CloudFormation templates using aws cli and optionally cfn-lint.
# Usage: ./scripts/validate-templates.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CF_DIR="$PROJECT_ROOT/cloudformation"

ERRORS=0

echo "=== Validating CloudFormation Templates ==="

# Find all YAML templates
while IFS= read -r template; do
    relative=$(realpath --relative-to="$PROJECT_ROOT" "$template")
    echo -n "  Validating $relative ... "

    if aws cloudformation validate-template --template-body "file://$template" > /dev/null 2>&1; then
        echo "OK"
    else
        echo "FAILED"
        aws cloudformation validate-template --template-body "file://$template" 2>&1 || true
        ERRORS=$((ERRORS + 1))
    fi
done < <(find "$CF_DIR" -name "*.yaml" -type f | sort)

echo ""

# Run cfn-lint if available
if command -v cfn-lint &> /dev/null; then
    echo "=== Running cfn-lint ==="
    if cfn-lint "$CF_DIR"/**/*.yaml; then
        echo "cfn-lint: All templates passed"
    else
        echo "cfn-lint: Issues found"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "cfn-lint not found, skipping (install with: pip install cfn-lint)"
fi

# Validate ASL state machine JSON
ASL="$PROJECT_ROOT/statemachine/transfer-workflow.asl.json"
if [ -f "$ASL" ]; then
    echo ""
    echo "=== Validating State Machine Definition ==="
    if python3 -m json.tool "$ASL" > /dev/null 2>&1; then
        echo "  transfer-workflow.asl.json: Valid JSON"
    else
        echo "  transfer-workflow.asl.json: Invalid JSON"
        ERRORS=$((ERRORS + 1))
    fi
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "=== All validations passed ==="
    exit 0
else
    echo "=== $ERRORS validation(s) failed ==="
    exit 1
fi
