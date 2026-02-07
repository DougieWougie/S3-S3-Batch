# Architecture

## System Overview

The S3-to-S3 Cross-Account Batch Transfer uses a three-account model with a centralized hub account orchestrating transfers between source and destination accounts.

### Architecture Diagram

```mermaid
graph TB
    subgraph Hub["Hub Account"]
        EB[EventBridge Rules]
        API[API Gateway<br/>AWS_IAM Auth]
        SFN[Step Functions<br/>State Machine]
        L1[ListObjects<br/>Lambda]
        L2[TransferObject<br/>Lambda x N]
        L3[ValidateTransfer<br/>Lambda]
        L4[GenerateReport<br/>Lambda]
        MB[Manifest Bucket<br/>Encrypted S3]
        CW[CloudWatch<br/>Dashboard + Alarms]
        SNS[SNS Topic]
    end

    subgraph Source["Source Account"]
        SB[Source S3 Bucket]
        SK[Source KMS CMK]
        SR[Source Reader Role]
    end

    subgraph Dest["Destination Account"]
        DB[Destination S3 Bucket]
        DK[Dest KMS CMK]
        DR[Dest Writer Role]
    end

    EB --> SFN
    API --> SFN
    SFN --> L1
    SFN --> L2
    SFN --> L3
    SFN --> L4

    L1 -.->|assume role| SR
    SR --> SB
    SR --> SK

    L2 -.->|assume role| DR
    DR -->|server-side copy| DB
    DR -.->|read via bucket policy| SB
    DR --> DK
    DR --> SK

    L1 --> MB
    L3 --> MB
    L4 --> MB
    L4 --> SNS

    SFN --> CW
```

### Workflow Sequence

```mermaid
sequenceDiagram
    participant Trigger as Trigger (Schedule/S3/API)
    participant SFN as Step Functions
    participant L1 as ListObjects
    participant S3M as Manifest Bucket
    participant DMap as Distributed Map
    participant L2 as TransferObject
    participant L3 as ValidateTransfer
    participant L4 as GenerateReport
    participant SNS as SNS

    Trigger->>SFN: Start execution
    SFN->>L1: Invoke (source_prefix)
    L1->>L1: Assume source role
    L1->>L1: Paginated S3 listing
    L1->>S3M: Write manifest.json
    L1-->>SFN: {manifest_key, count}

    SFN->>DMap: Read manifest from S3
    loop For each object (parallel)
        DMap->>L2: Invoke (Key, Size)
        L2->>L2: Assume dest role
        alt Size < 5GB
            L2->>L2: copy_object (server-side)
        else Size >= 5GB
            L2->>L2: multipart_copy (server-side)
        end
        L2-->>DMap: {status: SUCCESS}
    end

    SFN->>L3: Invoke (manifest_key)
    L3->>L3: Count destination objects
    L3->>L3: Sample ContentLength checks
    L3-->>SFN: {status: PASSED/FAILED}

    SFN->>L4: Invoke (validation result)
    L4->>S3M: Write report.json
    L4->>SNS: Publish notification
    L4-->>SFN: {report_key}
```

## Security Model

### IAM Trust Relationships

```mermaid
graph LR
    subgraph Hub
        LR[Lambda Exec Role]
    end

    subgraph Source
        SR[Source Reader Role]
    end

    subgraph Destination
        DR[Dest Writer Role]
    end

    LR -->|sts:AssumeRole<br/>+ ExternalId| SR
    LR -->|sts:AssumeRole<br/>+ ExternalId| DR
    DR -.->|bucket policy grant| Source
```

### Defense in Depth

| Layer | Control |
|-------|---------|
| **IAM Roles** | Lambda exec role can ONLY assume specific cross-account roles (by ARN). No wildcards. |
| **External ID** | Optional STS external ID prevents confused deputy attacks |
| **KMS** | Both buckets use CMKs. Key policies grant only specific roles, only specific actions |
| **Bucket Policies** | Source bucket grants read to dest role only. Deny insecure transport. |
| **API Gateway** | AWS_IAM (SigV4) auth only - no API keys, no open endpoints |
| **Manifest Bucket** | Encrypted, versioned, lifecycle-managed, public access blocked |
| **Lambda** | ReservedConcurrentExecutions caps blast radius. X-Ray tracing enabled |
| **Step Functions** | CloudWatch logging at ALL level with execution data |

### Copy Mechanism

No data flows through Lambda. The `TransferObject` Lambda assumes the **destination account role** which has:
- Write on destination bucket (native to the account)
- Read on source bucket (via bucket policy grant)
- KMS Encrypt on destination CMK
- KMS Decrypt on source CMK (via key policy grant)

The actual data transfer is a server-side copy within AWS infrastructure.

## Scalability

- **Distributed Map** processes objects in parallel (configurable `MaxConcurrency`, default 40)
- **Multipart copy** for objects >= 5GB with 100MB parts
- **ReservedConcurrentExecutions** on TransferObject Lambda prevents account-level throttling
- **Manifest stored in S3** (not passed inline) supports millions of objects
- Step Functions can handle up to 10M items per Distributed Map execution

## Retry Strategy

| Error Type | Lambda Retries | SFN Retries | Total Max |
|------------|---------------|-------------|-----------|
| S3 Throttling (SlowDown) | 5 (1-60s jitter) | 8 (5s base, 2.5x backoff) | 13 |
| Lambda Service Error | 0 | 3 (2s base, 2x backoff) | 3 |
| Access Denied | 0 | 0 | 0 (NonRetryableError) |

All retries use `JitterStrategy: FULL` to prevent thundering herd.
