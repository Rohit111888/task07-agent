# Task 09 — Demo Video Script

Maximum duration: 5 minutes

## Before Recording

Open the following before starting the recording:

1. Architecture diagram
2. VS Code with `cloudformation/task09-workflow.yml`
3. AWS S3 input bucket
4. AWS Step Functions state machine
5. Gmail success notification
6. Failure evidence screenshots
7. PowerShell terminal in the repository root

Close any files containing credentials or sensitive environment variables.

---

## 0:00–0:30 — Introduction

### Display

Show the Task 09 architecture diagram.

### Narration

> This is Task 09, an end-to-end event-driven automotive data-processing workflow. When a JSON or CSV file is uploaded to a specific Amazon S3 prefix, EventBridge automatically starts an AWS Step Functions state machine. The workflow invokes the existing automotive agent, stores its result in Amazon RDS PostgreSQL, and sends a notification through Amazon SNS. Failed agent calls are retried twice before being routed to an SQS dead-letter queue and generating a failure alert.

---

## 0:30–1:10 — CloudFormation and State Machine

### Display

Open:

```text
cloudformation/task09-workflow.yml
```

Briefly show the Step Functions definition and these states:

- Invoke Agent
- Store Result
- Notify
- Send To DLQ
- Failure Alert
- Workflow Failed

Also show the `Retry` and `Catch` sections under the Invoke Agent state.

### Narration

> The complete infrastructure and Amazon States Language definition are implemented in CloudFormation. The main states are Invoke Agent, Store Result, and Notify. The Invoke Agent state includes exponential-backoff retry handling with two retries. Its Catch configuration routes exhausted failures to the dead-letter queue and failure-alert states.

---

## 1:10–1:35 — Manual EventBridge Test

### Display

Run:

```powershell
aws events test-event-pattern `
    --event-pattern "file://task09/tests/deployed_event_pattern.json" `
    --event "file://task09/tests/test_event_pattern.json" `
    --region "us-east-1" `
    --no-cli-pager
```

### Expected Output

```json
{
    "Result": true
}
```

### Narration

> Before running the end-to-end workflow, I manually tested the EventBridge event pattern. The true result confirms that an S3 Object Created event for a JSON file under the incoming prefix matches the deployed rule.

---

## 1:35–2:10 — Upload Sample File

### Display

Briefly show:

```text
task09/sample-data/automotive_sample.json
```

Then upload it:

```powershell
$DemoKey = "incoming/automotive-demo-$((Get-Date).ToString('yyyyMMdd-HHmmss')).json"

aws s3 cp `
    ".\task09\sample-data\automotive_sample.json" `
    "s3://task09-automotive-input-654999855057-us-east-1/$DemoKey" `
    --region "us-east-1" `
    --no-progress
```

### Narration

> This sample contains automotive information for Ferrari, Tesla, and Porsche. I am uploading it to the monitored incoming prefix. I will not manually start Step Functions. The S3 event and EventBridge rule will start it automatically.

---

## 2:10–3:05 — Show Automatic Execution

### Display

Open or refresh the AWS Step Functions console:

```text
task09-automotive-workflow
```

Open the newest execution and show:

- Start time after the S3 upload
- Execution status
- Invoke Agent
- Store Result
- Notify
- Successful completion

### Narration

> EventBridge automatically created this execution after the S3 upload. The Invoke Agent state read the file and called the existing HTTPS automotive agent. The Store Result state persisted the response in RDS PostgreSQL, and the Notify state published the success notification. The workflow completed successfully without manual intervention.

---

## 3:05–3:40 — Show Result and RDS Confirmation

### Display

Show the execution output containing:

- `request_id`
- Agent status code `200`
- Agent answer
- `database_record`
- RDS record ID
- SNS notification result

If necessary, use the saved evidence:

```text
docs/task09/evidence/01-success-execution-output.png
```

### Narration

> The agent successfully analyzed the uploaded data and identified the Tesla Model S Plaid as the vehicle with the highest horsepower at 1,020 horsepower. The execution output also confirms that the result was stored in the workflow results table in RDS.

---

## 3:40–4:00 — Show Success Email

### Display

Show:

```text
docs/task09/evidence/02-success-sns-email.png
```

or open the received SNS email.

### Narration

> Amazon SNS delivered this success email. It contains the request ID, S3 source object, and RDS record ID.

---

## 4:00–4:35 — Show Failure Handling

### Display

Show:

```text
docs/task09/evidence/03-failure-retry-dlq-history.png
```

Point out:

- Three TaskFailed entries: initial attempt and two retries
- Send To DLQ
- Failure Alert

Then show:

```text
docs/task09/evidence/04-failure-sns-email.png
```

### Narration

> I also performed a controlled failure test. The execution history shows the initial failure followed by two retry attempts. After the retries were exhausted, Step Functions successfully sent the event to the SQS dead-letter queue and published a failure alert through SNS. This email confirms that the failure notification was delivered.

---

## 4:35–5:00 — Repository and Conclusion

### Display

Briefly show:

```text
cloudformation/task09-workflow.yml
task09/lambdas/
task09/sample-data/
task09/tests/
docs/task09/
```

### Narration

> The repository contains the CloudFormation and ASL definition, Lambda source code, sample automotive files, EventBridge test events, architecture diagram, documentation, and test evidence. This completes the fully automated Task 09 workflow, including success processing, RDS persistence, SNS notifications, retry handling, dead-letter queue routing, and failure alerting.