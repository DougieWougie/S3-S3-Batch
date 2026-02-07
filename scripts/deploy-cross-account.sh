#!/usr/bin/env bash
# Deploy cross-account stacks to source and destination accounts.
# Usage: ./scripts/deploy-cross-account.sh <source|destination> <stack-name> <params-file>

set -euo pipefail

ACCOUNT_TYPE="${1:?Usage: deploy-cross-account.sh <source|destination> <stack-name> <params-file>}"
STACK_NAME="${2:?Usage: deploy-cross-account.sh <source|destination> <stack-name> <params-file>}"
PARAMS_FILE="${3:?Usage: deploy-cross-account.sh <source|destination> <stack-name> <params-file>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

case "$ACCOUNT_TYPE" in
    source)
        TEMPLATE="$PROJECT_ROOT/cloudformation/source-account/cross-account-access.yaml"
        ;;
    destination)
        TEMPLATE="$PROJECT_ROOT/cloudformation/destination-account/cross-account-access.yaml"
        ;;
    *)
        echo "Error: Account type must be 'source' or 'destination'"
        exit 1
        ;;
esac

if [ ! -f "$PARAMS_FILE" ]; then
    echo "Error: Parameters file not found: $PARAMS_FILE"
    exit 1
fi

echo "=== Deploying $ACCOUNT_TYPE Account Stack ==="
echo "Template: $TEMPLATE"
echo "Stack: $STACK_NAME"
echo "Parameters: $PARAMS_FILE"
echo ""

# Validate template first
echo "--- Validating template ---"
aws cloudformation validate-template --template-body "file://$TEMPLATE"

echo ""
echo "--- Deploying stack ---"
aws cloudformation deploy \
    --template-file "$TEMPLATE" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides "file://$PARAMS_FILE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --tags Purpose=S3CrossAccountTransfer ManagedBy=CloudFormation AccountType="$ACCOUNT_TYPE"

echo ""
echo "=== Deployment Complete ==="
aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs' --output table

echo ""
echo "IMPORTANT: Remember to update KMS key policies manually."
echo "See the KmsKeyPolicyStatement output above for the required policy statement."
