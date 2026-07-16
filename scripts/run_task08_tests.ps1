param(
    [string]$BaseUrl = "https://testagent.cciplatform-ai.com"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

New-Item -ItemType Directory -Force -Path "postman/results" | Out-Null
$env:LIVE_BASE_URL = $BaseUrl.TrimEnd("/")

python -m pip install -r requirements-dev.txt
python -m pytest tests/test_live_endpoint.py -v --base-url $env:LIVE_BASE_URL |
    Tee-Object -FilePath "postman/results/pytest-results.txt"

npx --yes newman run "postman/Task08_Automotive_Agent.postman_collection.json" `
    -e "postman/Task08_Live.postman_environment.json" `
    --env-var "base_url=$env:LIVE_BASE_URL" `
    --reporters cli,json `
    --reporter-json-export "postman/results/newman-results.json"

Write-Host "Task 08 Pytest and Postman runs completed."
