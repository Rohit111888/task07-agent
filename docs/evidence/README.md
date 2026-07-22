# Task 08 Evidence

This folder contains the final evidence for the Task 08 observability,
testing, and quality-assurance implementation.

## Evidence files

1. `01-structured-json-log.png`
   - Shows a structured CloudWatch log for a `/query` request.
   - Includes the request ID, query, latency, model, token counts,
     tool calls, HTTP status, and error field.

2. `02-cloudwatch-dashboard-four-metrics.png`
   - Shows the `task08-agent-observability` dashboard.
   - Includes Request Count, Average Request Latency, Error Rate,
     and ECS CPU Utilization.

3. `03-sns-subscription-confirmed.png`
   - Shows the confirmed email subscription to the
     `task08-agent-alerts` SNS topic.

4. `04-alarm-in-alarm-state.png`
   - Shows the `task08-agent-error-rate-high` CloudWatch alarm
     in the `ALARM` state.

5. `05-sns-alarm-email.png`
   - Shows the SNS email generated when the CloudWatch alarm
     entered the `ALARM` state.

6. `06-pytest-10-passed.png`
   - Shows all 10 live Pytest integration tests passing.

7. `07-postman-newman-results.png`
   - Shows 10 Newman requests, 40 assertions, and zero failures.

## Review evidence

The implementation review, improvement suggestions, completed changes,
and final verification results are documented in:

`../task08_review.md`

## Safety verification

After the alarm demonstration:

- `EnableTestErrorEndpoint` was restored to `false`.
- `POST /test-error` was verified to return HTTP 404.
- The production HTTPS endpoint remained healthy.
