# S3-to-S3 Cross-Account Batch Transfer

AWS Service Catalog product for automated batch S3-to-S3 file transfers across AWS accounts with customer-managed KMS CMK encryption.

## Features

- **Cross-account transfers** using IAM role assumption (no data through Lambda)
- **KMS CMK encryption** on both source and destination buckets
- **Step Functions orchestration** with Distributed Map for parallel processing
- **Three trigger types**: scheduled (EventBridge), S3 event, REST API (IAM auth)
- **Validation**: count verification + random sample integrity checks
- **Monitoring**: CloudWatch dashboard, alarms, structured JSON logging
- **Retry strategy**: exponential backoff with jitter at Lambda and Step Functions levels
- **Service Catalog**: self-service provisioning with launch constraints

## Architecture

```
Hub Account                 Source Account         Destination Account
+------------------+       +---------------+      +------------------+
| Step Functions   |       | S3 Bucket     |      | S3 Bucket        |
|   Distributed Map|       |   + KMS CMK   |      |   + KMS CMK      |
|                  |       | Reader Role   |      | Writer Role      |
| Lambda x4        |------>|   (list)      |      |   (copy+write)   |
|   ListObjects    |       +---------------+      +------------------+
|   TransferObject |              |                       ^
|   ValidateXfer   |              +----- server-side -----+
|   GenerateReport |                    copy_object
|                  |
| EventBridge      |
| API Gateway      |
| CloudWatch       |
+------------------+
```

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.

## Quick Start

### Prerequisites

- AWS CLI configured with credentials for hub, source, and destination accounts
- Python 3.12+
- S3 buckets with KMS CMK encryption in source and destination accounts

### Deployment Order

1. **Source account**: Cross-account access stack
2. **Destination account**: Cross-account access stack
3. **Hub account**: Main nested stack (or via Service Catalog)

See [docs/deployment-guide.md](docs/deployment-guide.md) for complete instructions.

## Development

```bash
# Install test dependencies
pip install pytest moto boto3

# Run unit tests
pytest tests/unit/ -v

# Validate CloudFormation templates
./scripts/validate-templates.sh
```

## Documentation

- [Architecture](docs/architecture.md) - system overview, security model, scalability
- [Deployment Guide](docs/deployment-guide.md) - prerequisites, deployment order, parameters
- [Operations Guide](docs/operations-guide.md) - triggering, monitoring, troubleshooting
