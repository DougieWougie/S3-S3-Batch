# Deployment Guide

## Prerequisites

1. **AWS Accounts**: Hub, Source, and Destination accounts with appropriate admin access
2. **AWS CLI** configured with profiles for each account
3. **S3 Buckets**: Source and destination buckets already created with KMS CMK encryption
4. **Python 3.12+** for packaging Lambda functions
5. **S3 Buckets in Hub Account**: For Lambda code and CloudFormation templates

## Deployment Order

Deploy in this order to resolve cross-account dependencies:

```
1. Hub Account IAM (get Lambda execution role ARN)
         |
    +----+----+
    v         v
2. Source   3. Destination
   Account     Account
    |         |
    +----+----+
         |
4. Hub Account (full stack)
         |
5. Service Catalog (optional)
```

## Step 1: Deploy Source Account Stack

Switch to source account credentials:

```bash
export AWS_PROFILE=source-account

./scripts/deploy-cross-account.sh source s3-transfer-source params/source-params.json
```

Example `source-params.json`:
```json
[
  {"ParameterKey": "HubAccountId", "ParameterValue": "000000000000"},
  {"ParameterKey": "DestinationRoleArn", "ParameterValue": "arn:aws:iam::222222222222:role/s3-transfer-dest-DestWriterRole"},
  {"ParameterKey": "SourceBucketName", "ParameterValue": "my-source-bucket"},
  {"ParameterKey": "SourceKmsKeyArn", "ParameterValue": "arn:aws:kms:us-east-1:111111111111:key/abc-123"},
  {"ParameterKey": "ExternalId", "ParameterValue": "transfer-ext-id-2024"},
  {"ParameterKey": "LambdaExecutionRoleArn", "ParameterValue": "arn:aws:iam::000000000000:role/s3-transfer-hub-LambdaExecRole"}
]
```

**Important**: After deployment, add the KMS key policy statement from the stack output to your source KMS key.

## Step 2: Deploy Destination Account Stack

Switch to destination account credentials:

```bash
export AWS_PROFILE=destination-account

./scripts/deploy-cross-account.sh destination s3-transfer-dest params/dest-params.json
```

Example `dest-params.json`:
```json
[
  {"ParameterKey": "HubAccountId", "ParameterValue": "000000000000"},
  {"ParameterKey": "SourceBucketName", "ParameterValue": "my-source-bucket"},
  {"ParameterKey": "DestinationBucketName", "ParameterValue": "my-dest-bucket"},
  {"ParameterKey": "SourceKmsKeyArn", "ParameterValue": "arn:aws:kms:us-east-1:111111111111:key/abc-123"},
  {"ParameterKey": "DestinationKmsKeyArn", "ParameterValue": "arn:aws:kms:us-east-1:222222222222:key/def-456"},
  {"ParameterKey": "ExternalId", "ParameterValue": "transfer-ext-id-2024"},
  {"ParameterKey": "LambdaExecutionRoleArn", "ParameterValue": "arn:aws:iam::000000000000:role/s3-transfer-hub-LambdaExecRole"}
]
```

**Important**: Add the KMS key policy statements to both source and destination KMS keys.

## Step 3: Deploy Hub Account Stack

Switch to hub account credentials:

```bash
export AWS_PROFILE=hub-account

./scripts/deploy-hub.sh s3-transfer-hub params/hub-params.json
```

Example `hub-params.json`:
```json
[
  {"ParameterKey": "SourceRoleArn", "ParameterValue": "arn:aws:iam::111111111111:role/s3-transfer-source-SourceReaderRole"},
  {"ParameterKey": "DestinationRoleArn", "ParameterValue": "arn:aws:iam::222222222222:role/s3-transfer-dest-DestWriterRole"},
  {"ParameterKey": "ExternalId", "ParameterValue": "transfer-ext-id-2024"},
  {"ParameterKey": "SourceBucket", "ParameterValue": "my-source-bucket"},
  {"ParameterKey": "DestinationBucket", "ParameterValue": "my-dest-bucket"},
  {"ParameterKey": "SourcePrefix", "ParameterValue": "data/"},
  {"ParameterKey": "DestinationPrefix", "ParameterValue": "transferred/"},
  {"ParameterKey": "SourceKmsKeyId", "ParameterValue": "arn:aws:kms:us-east-1:111111111111:key/abc-123"},
  {"ParameterKey": "DestinationKmsKeyId", "ParameterValue": "arn:aws:kms:us-east-1:222222222222:key/def-456"},
  {"ParameterKey": "LambdaCodeBucket", "ParameterValue": "my-deployment-bucket"},
  {"ParameterKey": "TemplateBucket", "ParameterValue": "my-deployment-bucket"},
  {"ParameterKey": "EnableSchedule", "ParameterValue": "true"},
  {"ParameterKey": "ScheduleExpression", "ParameterValue": "rate(1 day)"},
  {"ParameterKey": "NotificationEmail", "ParameterValue": "ops@example.com"},
  {"ParameterKey": "TransferConcurrencyLimit", "ParameterValue": "50"}
]
```

## Step 4: Deploy Service Catalog (Optional)

```bash
aws cloudformation deploy \
  --template-file cloudformation/service-catalog/portfolio.yaml \
  --stack-name s3-transfer-catalog \
  --parameter-overrides \
    TemplateBucket=my-deployment-bucket \
    PrincipalArn=arn:aws:iam::000000000000:role/TeamRole \
    LaunchRoleArn=arn:aws:iam::000000000000:role/SCLaunchRole \
  --capabilities CAPABILITY_NAMED_IAM
```

## Parameter Reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `SourceRoleArn` | Yes | Source account reader role ARN |
| `DestinationRoleArn` | Yes | Destination account writer role ARN |
| `ExternalId` | No | STS external ID for confused deputy protection |
| `SourceBucket` | Yes | Source S3 bucket name |
| `DestinationBucket` | Yes | Destination S3 bucket name |
| `SourcePrefix` | No | Source key prefix filter |
| `DestinationPrefix` | No | Destination key prefix |
| `SourceKmsKeyId` | Yes | Source KMS CMK ARN |
| `DestinationKmsKeyId` | Yes | Destination KMS CMK ARN |
| `LambdaCodeBucket` | Yes | S3 bucket for Lambda packages |
| `TemplateBucket` | Yes | S3 bucket for CF templates |
| `EnableSchedule` | No | Enable scheduled trigger (default: false) |
| `ScheduleExpression` | No | Cron/rate expression (default: rate(1 day)) |
| `EnableS3EventTrigger` | No | Enable S3 event trigger (default: false) |
| `TransferConcurrencyLimit` | No | Max concurrent transfers (default: 50) |
| `NotificationEmail` | No | Email for alarm notifications |
