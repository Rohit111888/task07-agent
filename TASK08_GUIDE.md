# TASK 08 — Observability, Testing and QA

This project extends the Task 07 ECS deployment with structured JSON request
logging, three log-derived application metrics, an ECS CPU metric, a CloudWatch
dashboard, an error-rate alarm with SNS email, ten live Pytest tests, and the
same ten cases in Postman.

The alarm's error rate uses HTTP 5xx responses, which represent server/service
failures. Expected 4xx validation responses are still logged with error details
and `is_client_error=1`, but they do not page the operator.

## Implemented components

- `app/observability.py`: emits one compact JSON log per request.
- `app/main.py`: records query, latency, model, token usage, tool calls, status,
  errors, and request ID.
- `app/agent.py`: returns model/token/tool metadata without breaking the
  original `run_agent()` interface.
- `cloudformation/ecs-fargate.yml`: provisions metric filters, dashboard, SNS,
  alarm, and the temporary test-error flag.
- `tests/test_live_endpoint.py`: ten numbered tests against the HTTPS endpoint.
- `postman/Task08_Automotive_Agent.postman_collection.json`: matching ten cases.
- `.github/workflows/integration-tests.yml`: manually runs both suites and
  preserves the Newman result as a workflow artifact.

## 1. Build and deploy the new image

Commit and push the Task 08 changes to `main`. The existing deployment workflow
builds, smoke-tests, and pushes semantic-version and Git SHA tags to ECR. Record
the new ECR image URI shown by the workflow.

Update the existing stack from PowerShell. Reuse the real stack name,
certificate ARN, and new image tag:

```powershell
$STACK_NAME = "task07-agent-stack"
$IMAGE_URI = "654999855057.dkr.ecr.us-east-1.amazonaws.com/task07-agent:v1.0.REPLACE"
$CERTIFICATE_ARN = "arn:aws:acm:us-east-1:654999855057:certificate/REPLACE"
$ALARM_EMAIL = "your-email@example.com"

aws cloudformation deploy `
  --template-file cloudformation/ecs-fargate.yml `
  --stack-name $STACK_NAME `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides `
    ImageUri=$IMAGE_URI `
    CertificateArn=$CERTIFICATE_ARN `
    AlarmEmail=$ALARM_EMAIL `
    EnableTestErrorEndpoint=false `
  --region us-east-1 `
  --no-fail-on-empty-changeset
```

Open the SNS confirmation message sent to `$ALARM_EMAIL` and select **Confirm
subscription**. An unconfirmed subscription cannot receive alarm emails.

## 2. Generate traffic and inspect structured logs

Run both suites:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_task08_tests.ps1 `
  -BaseUrl "https://testagent.cciplatform-ai.com"
```

The script writes Pytest and Newman results under `postman/results/`.

In CloudWatch Logs Insights, select `/ecs/task07-agent` and run:

```text
fields @timestamp, request_id, path, query, latency_ms, model_used,
       token_count.total, tool_calls_made, status_code, error
| filter event = "agent_request"
| sort @timestamp desc
| limit 50
```

Capture a screenshot showing a successful `/query` event with the required
fields. Then open the `task08-agent-observability` dashboard and select a time
range containing the test run. Capture all four widgets in one screenshot.

## 3. Demonstrate the greater-than-5-percent alarm

Temporarily enable the controlled test endpoint:

```powershell
aws cloudformation deploy `
  --template-file cloudformation/ecs-fargate.yml `
  --stack-name $STACK_NAME `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides `
    ImageUri=$IMAGE_URI `
    CertificateArn=$CERTIFICATE_ARN `
    AlarmEmail=$ALARM_EMAIL `
    EnableTestErrorEndpoint=true `
  --region us-east-1 `
  --no-fail-on-empty-changeset
```

Wait until the ECS deployment is stable, then generate enough controlled 500
responses to exceed 5 percent of the current five-minute request volume:

```powershell
1..20 | ForEach-Object {
  try {
    Invoke-WebRequest `
      -Method Post `
      -Uri "https://testagent.cciplatform-ai.com/test-error"
  } catch {
    Write-Host "Expected forced HTTP 500"
  }
}
```

CloudWatch evaluates one five-minute period. Allow up to approximately ten
minutes for log metric delivery and alarm evaluation. Capture the alarm in
`ALARM` state and the SNS notification email.

Immediately redeploy with `EnableTestErrorEndpoint=false` after collecting the
evidence. Verify that `POST /test-error` then returns `404`.

## 4. Final review and submission

Ask the POC or a peer to review the Pytest and Postman results. Add their name,
date, and any additional feedback to `docs/task08_review.md`. The file already
records five implemented improvements from the initial QA review.

Final evidence is listed in `docs/evidence/README.md`. The minimum submission is:

- CloudWatch dashboard screenshot with four populated metrics
- Structured JSON log screenshot
- Alarm state and SNS email screenshots
- Pytest output showing all ten tests passing
- Exported Postman collection and run result showing all ten cases passing
- At least three documented review suggestions with implementations
