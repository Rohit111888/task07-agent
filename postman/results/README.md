# Test run evidence

Run `scripts/run_task08_tests.ps1` after the Task 08 image and CloudFormation
changes are deployed. The script writes:

- `pytest-results.txt`
- `newman-results.json`

Commit those generated files with the final evidence after verifying that all
ten Pytest and all ten Postman requests pass.
