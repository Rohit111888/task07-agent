# TASK 08 — Observability, Testing and QA

This project extends the Task 07 AWS ECS Fargate deployment with structured
JSON request logging, CloudWatch application metrics, a four-widget monitoring
dashboard, an error-rate alarm with SNS email notifications, ten live Pytest
integration tests, and the same ten test cases in Postman/Newman.

The alarm monitors HTTP 5xx responses, which represent server or service
failures. Expected HTTP 4xx validation responses are still recorded with error
details and `is_client_error=1`, but they do not trigger the operational alarm.

## Project details

- AWS region: `us-east-1`
- CloudFormation stack: `task07-agent-stack`
- Live HTTPS endpoint: `https://testagent.cciplatform-ai.com`
- CloudWatch log group: `/ecs/task07-agent`
- CloudWatch dashboard: `task08-agent-observability`
- SNS topic: `task08-agent-alerts`
- CloudWatch alarm: `task08-agent-error-rate-high`
- ECR image used during verification:
  `654999855057.dkr.ecr.us-east-1.amazonaws.com/task07-agent:v1.0.8`

## Implemented components

- `app/observability.py`
  - Produces one compact structured JSON log for every HTTP request.

- `app/main.py`
  - Assigns an `X-Request-ID`.
  - Records the request path, method, query, latency, model, token usage,
    tool calls, HTTP status, and error information.
  - Provides the controlled `/test-error` endpoint used for alarm testing.

- `app/agent.py`
  - Returns the generated answer together with model, token, and tool-call
    metadata.
  - Preserves compatibility with the original `run_agent()` interface.

- `cloudformation/ecs-fargate.yml`
  - Provisions CloudWatch metric filters.
  - Creates the CloudWatch dashboard.
  - Creates the SNS topic and email subscription.
  - Creates the server error-rate alarm.
  - Controls the `/test-error` endpoint through
    `EnableTestErrorEndpoint`.

- `tests/test_live_endpoint.py`
  - Contains ten numbered live integration tests against the HTTPS endpoint.

- `postman/Task08_Automotive_Agent.postman_collection.json`
  - Contains the same ten test cases with forty total assertions.

- `.github/workflows/integration-tests.yml`
  - Runs the integration suites through GitHub Actions.
  - Preserves the Newman JSON result as a workflow artifact.

- `scripts/run_task08_tests.ps1`
  - Runs the Pytest and Newman suites against a configurable base URL.

## 1. Run the live test suites

Run both suites from the project root:

```powershell
powershell -ExecutionPolicy Bypass `
  -File ".\scripts\run_task08_tests.ps1" `
  -BaseUrl "https://testagent.cciplatform-ai.com"
```

The generated results are saved under:

```text
postman/results/pytest-results.txt
postman/results/newman-results.json
```

Verified results:

```text
Pytest: 10 passed
Newman requests: 10 executed, 0 failed
Newman assertions: 40 executed, 0 failed
```

The ten tested cases are:

1. Health endpoint
2. Root endpoint
3. Ferrari happy path
4. Graph-ranked automotive query
5. Electric-vehicle edge case
6. No-matching-brand edge case
7. Empty question
8. Whitespace-only question
9. Very long question
10. Malformed JSON

The tests validate response status, response time, request IDs, response
schemas, validation details, non-empty answers, and expected domain behavior.

## 2. Inspect structured JSON logs

In CloudWatch Logs Insights, select the following log group:

```text
/ecs/task07-agent
```

Run this query:

```text
fields @timestamp, request_id, path, query, latency_ms, model_used,
       token_count.total, tool_calls_made, status_code, error
| filter event = "agent_request"
| sort @timestamp desc
| limit 50
```

Each structured request log includes:

- Timestamp
- Request ID
- HTTP path and method
- Submitted query
- Request latency
- Model used
- Input, output, and total token counts
- Tool calls
- HTTP status
- Success, client-error, and server-error classification
- Error description

A successful `/query` log was verified in CloudWatch and saved as evidence.

## 3. Verify the CloudWatch dashboard

Open the following dashboard:

```text
task08-agent-observability
```

The dashboard contains four populated widgets:

1. Request Count
2. Average Request Latency
3. Error Rate
4. ECS CPU Utilization

The Error Rate metric is based on HTTP 5xx server responses. Expected HTTP 4xx
validation responses are logged but do not count as server failures.

## 4. SNS subscription and alarm configuration

The CloudFormation template provisions the SNS topic:

```text
task08-agent-alerts
```

The email subscription was confirmed successfully. A full subscription ARN was
returned, confirming that the subscription was no longer in the
`PendingConfirmation` state.

The CloudWatch alarm is:

```text
task08-agent-error-rate-high
```

The alarm transitions to `ALARM` when the HTTP 5xx error rate exceeds the
configured 5 percent threshold.

## 5. Controlled alarm demonstration

The `/test-error` endpoint is controlled by the CloudFormation parameter:

```text
EnableTestErrorEndpoint
```

Its normal and default value is:

```text
false
```

For the alarm demonstration, the parameter was temporarily changed to `true`.

Controlled HTTP 500 responses were then generated with:

```powershell
1..10 | ForEach-Object {
    $status = curl.exe -s -o NUL -w "%{http_code}" `
      -X POST "https://testagent.cciplatform-ai.com/test-error"

    Write-Host "Request $_ -> HTTP $status"
    Start-Sleep -Seconds 1
}
```

The generated failures increased the measured error rate to approximately
26.19 percent, which exceeded the 5 percent threshold.

The following results were verified:

- The alarm transitioned to `ALARM`.
- The alarm reason showed that the threshold had been crossed.
- The SNS alarm email was received successfully.
- The alarm later returned to `OK`.

Immediately after collecting the evidence:

- `EnableTestErrorEndpoint` was restored to `false`.
- The CloudFormation stack returned to `UPDATE_COMPLETE`.
- `POST /test-error` was verified to return HTTP 404.
- The normal production endpoint remained healthy.

## 6. Quality-assurance improvements

The implementation review documented five improvements:

1. Prevent integration tests from waiting indefinitely.
   - Added configurable request timeouts and maximum-response-time assertions.

2. Validate response contracts instead of checking only HTTP status codes.
   - Added checks for required JSON fields, validation details, request IDs,
     non-empty answers, and expected domain behavior.

3. Make production failures traceable.
   - The same `X-Request-ID` is returned to the client and written to the
     structured CloudWatch log.

4. Prevent the controlled error endpoint from remaining publicly available.
   - `/test-error` is hidden from OpenAPI and controlled by
     `EnableTestErrorEndpoint`, whose default value is `false`.

5. Avoid hardcoding the deployed endpoint.
   - Pytest, Newman, PowerShell, and GitHub Actions accept a configurable
     base URL.

The complete review record is stored in:

```text
docs/task08_review.md
```

## 7. Evidence

The final Task 08 evidence is stored under:

```text
docs/evidence/
```

Evidence files:

1. `01-structured-json-log.png`
   - Structured CloudWatch `/query` log containing the required request fields.

2. `02-cloudwatch-dashboard-four-metrics.png`
   - CloudWatch dashboard showing all four populated widgets.

3. `03-sns-subscription-confirmed.png`
   - Confirmed SNS email subscription.

4. `04-alarm-in-alarm-state.png`
   - CloudWatch alarm in the `ALARM` state.

5. `05-sns-alarm-email.png`
   - SNS notification email generated by the alarm.

6. `06-pytest-10-passed.png`
   - Pytest output showing all ten tests passed.

7. `07-postman-newman-results.png`
   - Newman output showing ten requests, forty assertions, and zero failures.

Additional machine-readable evidence:

```text
postman/results/newman-results.json
postman/results/pytest-results.txt
```

The evidence index is available at:

```text
docs/evidence/README.md
```

## 8. Final verification summary

| Verification item | Result |
|---|---|
| Live HTTPS endpoint | Passed |
| Structured JSON logging | Verified |
| Request Count metric | Verified |
| Average Request Latency metric | Verified |
| Error Rate metric | Verified |
| ECS CPU Utilization metric | Verified |
| Four-widget CloudWatch dashboard | Verified |
| SNS email subscription | Confirmed |
| CloudWatch error-rate alarm | Entered `ALARM` successfully |
| SNS alarm notification | Received |
| Pytest suite | `10 passed` |
| Newman suite | `10 requests`, `40 assertions`, `0 failures` |
| `EnableTestErrorEndpoint` restored to `false` | Verified |
| `/test-error` after disabling | HTTP 404 |
| Python docstring audit | Passed |
| Git branch | Synchronized with `origin/main` |

## 9. Final submission contents

The final submission should include:

- Application source code
- CloudFormation infrastructure template
- Docker configuration
- GitHub Actions workflows
- Pytest integration tests
- Postman collection and environment
- Newman and Pytest result files
- Task 08 guide
- Task 08 review document
- Organized evidence screenshots
- Requirements files
- Safe `.env.example` placeholders

The final submission should not include:

```text
.git/
.pytest_cache/
__pycache__/
*.pyc
.env
TASK_7.pdf
queries/
```

The PowerShell test runner should remain in the official project because it is
part of the Task 08 testing workflow. When Gmail blocks the ZIP because it
contains a `.ps1` file, the official ZIP should be shared through Google Drive
instead of removing the script.