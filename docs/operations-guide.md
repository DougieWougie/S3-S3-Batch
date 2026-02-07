# Operations Guide

## Triggering Transfers

### Scheduled (EventBridge)

When `EnableSchedule` is set to `true`, transfers run automatically on the configured schedule. Modify the schedule:

```bash
aws events put-rule \
  --name "s3-transfer-hub-ScheduledTransfer" \
  --schedule-expression "cron(0 2 * * ? *)"
```

### S3 Event (EventBridge)

When `EnableS3EventTrigger` is set to `true`, transfers trigger on new objects in the source bucket. Requires S3 EventBridge notifications enabled:

```bash
aws s3api put-bucket-notification-configuration \
  --bucket my-source-bucket \
  --notification-configuration '{"EventBridgeConfiguration": {}}'
```

### API Gateway

Trigger a transfer via the REST API (requires AWS SigV4 authentication):

```bash
aws apigateway test-invoke-method \
  --rest-api-id <api-id> \
  --resource-id <resource-id> \
  --http-method POST \
  --body '{"source_prefix": "data/batch-001/"}'
```

Or using `curl` with SigV4:

```bash
curl -X POST \
  --aws-sigv4 "aws:amz:us-east-1:execute-api" \
  --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
  -H "x-amz-security-token: $AWS_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_prefix": "data/"}' \
  https://<api-id>.execute-api.us-east-1.amazonaws.com/v1/transfer
```

### Manual (AWS CLI)

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:000000000000:stateMachine:s3-transfer-hub-TransferWorkflow \
  --input '{"source_prefix": "data/"}'
```

## Monitoring

### CloudWatch Dashboard

Access the dashboard at:
```
https://<region>.console.aws.amazon.com/cloudwatch/home?region=<region>#dashboards:name=s3-transfer-hub-Dashboard
```

The dashboard shows:
- Step Functions execution counts (started/succeeded/failed/timed out)
- Execution duration (average and max)
- Lambda invocations per function
- Lambda errors and throttles
- Lambda duration (average and p99)

### Alarms

| Alarm | Trigger | Action |
|-------|---------|--------|
| SFN-Failed | Any execution failure | SNS notification |
| SFN-TimedOut | Any execution timeout | SNS notification |
| TransferLambda-Errors | >10 errors in 5 min | SNS notification |
| TransferLambda-Throttles | >5 throttles in 5 min | SNS notification |

### Structured Logs

All Lambda functions emit structured JSON to CloudWatch Logs:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "logger": "transfer_object.handler",
  "message": "TransferObject complete",
  "function_name": "s3-transfer-hub-TransferObject",
  "request_id": "abc-123",
  "source_key": "data/file.txt",
  "dest_key": "transferred/file.txt",
  "size": 1048576
}
```

Query logs with CloudWatch Insights:

```
# Failed transfers
fields @timestamp, @message
| filter level = "ERROR"
| sort @timestamp desc

# Transfer duration by object
fields @timestamp, source_key, size
| filter message = "TransferObject complete"
| stats avg(size) as avg_size, count() as total
```

### Execution Reports

Reports are stored in the manifest bucket under `reports/<execution-id>/report.json`:

```json
{
  "execution_id": "abc-123",
  "status": "PASSED",
  "total_objects": 1500,
  "total_size_bytes": 5368709120,
  "validation": {
    "total_expected": 1500,
    "total_found": 1500,
    "samples_checked": 10,
    "samples_passed": 10
  }
}
```

## Troubleshooting

### Access Denied Errors

**Symptom**: `AccessDeniedError` in Lambda logs.

**Check**:
1. IAM role trust policies allow the Lambda execution role
2. External ID matches across all configurations
3. KMS key policies grant the appropriate roles
4. S3 bucket policies grant cross-account access

```bash
# Test role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::111111111111:role/SourceReaderRole \
  --role-session-name test \
  --external-id your-external-id
```

### Throttling / SlowDown

**Symptom**: `RetryableError` with `SlowDown` error code.

**Fix**:
- Reduce `TransferConcurrencyLimit` parameter
- Reduce `MaxConcurrency` in the Distributed Map (requires ASL edit)
- Enable S3 request metrics to identify prefix hotspots

### Large Object Failures

**Symptom**: Timeout on TransferObject Lambda.

**Check**:
- Objects >5GB use multipart copy automatically
- Lambda timeout is 900s (15 min maximum)
- For very large objects, multipart copy with 100MB parts may still time out

### Validation Failures

**Symptom**: `ValidationError` with count or size mismatch.

**Check**:
- Review the manifest at `s3://<manifest-bucket>/manifests/<exec-id>/manifest.json`
- Compare with actual destination objects
- Check for partial failures in the Distributed Map execution history
- S3 eventual consistency can cause temporary count mismatches

### Step Functions Execution History

```bash
# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn <arn> \
  --status-filter FAILED \
  --max-results 10

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn <execution-arn>

# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn> \
  --reverse-order
```
