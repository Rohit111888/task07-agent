# Task 08 testing and QA review

## Review record

- Review type: implementation and test-design review
- Scope: FastAPI request logging, live Pytest suite, Postman collection, alarm safety
- Live-result review: complete this line with the POC/peer name and date after running the deployed tests

## Suggestions and implementations

| # | Review suggestion | Implementation |
|---|---|---|
| 1 | Prevent integration tests from waiting forever when the live model or network is unavailable. | Added configurable request timeouts and maximum-response-time assertions to Pytest and Postman. |
| 2 | Validate the response contract instead of checking only HTTP status codes. | Tests now verify required JSON fields, non-empty answers, validation details, and `X-Request-ID`. |
| 3 | Make production failures traceable across test output and CloudWatch. | Every response receives an `X-Request-ID`; the same value is included in the structured JSON log and query response. |
| 4 | Do not leave a publicly callable error endpoint enabled after the alarm demonstration. | `/test-error` is hidden from OpenAPI and controlled by `EnableTestErrorEndpoint`, whose default is `false`. |
| 5 | Avoid hardcoding the live endpoint in automation. | Pytest, Newman, PowerShell, and GitHub Actions accept a configurable base URL. |

## Live results sign-off

After deployment, paste the following results here:

- Pytest: `10 passed`
- Postman/Newman: `10 requests`, `0 failed assertions`
- Reviewer/POC:
- Review date:
- Any additional reviewer feedback and the commit that implements it:
