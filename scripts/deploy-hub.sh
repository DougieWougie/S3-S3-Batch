#!/usr/bin/env bash
# Deploy hub account stack.
# Usage: ./scripts/deploy-hub.sh <stack-name> <params-file>
#
# Example params file (JSON):
# [
#   {"ParameterKey": "SourceRoleArn", "ParameterValue": "arn:aws:iam::111:role/SourceReader"},
#   ...
# ]

set -euo pipefail

STACK_NAME="${1:?Usage: deploy-hub.sh <stack-name> <params-file>}"
PARAMS_FILE="${2:?Usage: deploy-hub.sh <stack-name> <params-file>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ ! -f "$PARAMS_FILE" ]; then
    echo "Error: Parameters file not found: $PARAMS_FILE"
    exit 1
fi

echo "=== Deploying Hub Account Stack ==="
echo "Stack: $STACK_NAME"
echo "Parameters: $PARAMS_FILE"
echo ""

# Package Lambdas first
echo "--- Packaging Lambda functions ---"
"$SCRIPT_DIR/package-lambdas.sh" "$PROJECT_ROOT/deployment"

# Upload Lambda packages
LAMBDA_BUCKET=$(python3 -c "
import json
params = json.load(open('$PARAMS_FILE'))
for p in params:
    if p['ParameterKey'] == 'LambdaCodeBucket':
        print(p['ParameterValue'])
        break
")

LAMBDA_PREFIX=$(python3 -c "
import json
params = json.load(open('$PARAMS_FILE'))
for p in params:
    if p['ParameterKey'] == 'LambdaCodePrefix':
        print(p['ParameterValue'])
        break
else:
    print('lambda/')
")

echo ""
echo "--- Uploading Lambda packages to s3://$LAMBDA_BUCKET/$LAMBDA_PREFIX ---"
for zip_file in "$PROJECT_ROOT/deployment/"*.zip; do
    filename=$(basename "$zip_file")
    aws s3 cp "$zip_file" "s3://$LAMBDA_BUCKET/${LAMBDA_PREFIX}${filename}"
    echo "  Uploaded: $filename"
done

# Upload CloudFormation templates
TEMPLATE_BUCKET=$(python3 -c "
import json
params = json.load(open('$PARAMS_FILE'))
for p in params:
    if p['ParameterKey'] == 'TemplateBucket':
        print(p['ParameterValue'])
        break
")

TEMPLATE_PREFIX=$(python3 -c "
import json
params = json.load(open('$PARAMS_FILE'))
for p in params:
    if p['ParameterKey'] == 'TemplatePrefix':
        print(p['ParameterValue'])
        break
else:
    print('cloudformation/hub-account/')
")

echo ""
echo "--- Uploading CF templates to s3://$TEMPLATE_BUCKET/$TEMPLATE_PREFIX ---"
for template in "$PROJECT_ROOT/cloudformation/hub-account/"*.yaml; do
    filename=$(basename "$template")
    aws s3 cp "$template" "s3://$TEMPLATE_BUCKET/${TEMPLATE_PREFIX}${filename}"
    echo "  Uploaded: $filename"
done

# Upload state machine definition
echo ""
echo "--- Uploading state machine definition ---"
aws s3 cp "$PROJECT_ROOT/statemachine/transfer-workflow.asl.json" \
    "s3://$TEMPLATE_BUCKET/statemachine/transfer-workflow.asl.json"

# Deploy stack
echo ""
echo "--- Deploying CloudFormation stack ---"
aws cloudformation deploy \
    --template-file "$PROJECT_ROOT/cloudformation/hub-account/main.yaml" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides "file://$PARAMS_FILE" \
    --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
    --tags Purpose=S3CrossAccountTransfer ManagedBy=CloudFormation

echo ""
echo "=== Deployment Complete ==="
aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs' --output table
