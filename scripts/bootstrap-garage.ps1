#requires -Version 7
<#
.SYNOPSIS
    One-time Garage bootstrap for the WSS Map Processing Platform.

.DESCRIPTION
    The official Garage image is distroless (no shell), so the Garage CLI is
    invoked inside the running `garage` container via `docker compose exec`.
    This script:
      1. waits for Garage to be ready
      2. applies the single-node cluster layout (idempotent)
      3. creates the bucket and an S3 access key (idempotent)
      4. writes the credentials to infra/garage/credentials/ (mounted into the
         api/worker containers as /run/garage)
      5. brings up api, cv-worker, geo-worker and web

.EXAMPLE
    docker compose up -d --build postgres redis garage garage-cors
    pwsh scripts/bootstrap-garage.ps1
#>
$ErrorActionPreference = 'Stop'

Set-Location (Join-Path $PSScriptRoot '..')

$bucket = if ($env:S3_BUCKET) { $env:S3_BUCKET } else { 'wss' }
$keyName = 'wss-app'
$configPath = '/etc/garage.toml'

function Invoke-Garage {
    param([string[]]$GarageArgs)
    $output = docker compose exec -T garage /garage -c $configPath @GarageArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "garage $($GarageArgs -join ' ') failed:`n$output"
    }
    return ($output -join "\n")
}

Write-Host '[bootstrap] waiting for the garage container...'
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-Garage @('status') | Out-Null; $ready = $true; break }
    catch { Start-Sleep -Seconds 3 }
}
if (-not $ready) { throw '[bootstrap] garage did not become ready in time' }

$nodeId = (Invoke-Garage @('node', 'id') -split "\n")[0].Split('@')[0].Trim()
Write-Host "[bootstrap] node id: $nodeId"

$layout = Invoke-Garage @('layout', 'show')
if ($layout -notmatch [regex]::Escape($nodeId)) {
    Write-Host '[bootstrap] applying single-node cluster layout'
    Invoke-Garage @('layout', 'assign', '-z', 'dc1', '-c', '1G', $nodeId) | Out-Null
    Invoke-Garage @('layout', 'apply', '--version', '1') | Out-Null
}

$buckets = Invoke-Garage @('bucket', 'list')
if ($buckets -notmatch "\b$([regex]::Escape($bucket))\b") {
    Write-Host "[bootstrap] creating bucket '$bucket'"
    Invoke-Garage @('bucket', 'create', $bucket) | Out-Null
}

$keyExists = $true
try { Invoke-Garage @('key', 'info', $keyName) | Out-Null } catch { $keyExists = $false }
if (-not $keyExists) {
    Write-Host "[bootstrap] creating access key '$keyName'"
    Invoke-Garage @('key', 'create', $keyName) | Out-Null
}

Invoke-Garage @('bucket', 'allow', '--read', '--write', '--owner', $bucket, '--key', $keyName) | Out-Null

$info = Invoke-Garage @('key', 'info', '--show-secret', $keyName)
$access = ($info -split "\n" | Where-Object { $_ -match '^\s*Key ID' } | Select-Object -First 1).Split(':', 2)[1].Trim()
$secret = ($info -split "\n" | Where-Object { $_ -match '^\s*Secret key' } | Select-Object -First 1).Split(':', 2)[1].Trim()
if (-not $access -or -not $secret) { throw "[bootstrap] could not parse key credentials:`n$info" }

$credsDir = Join-Path $PWD 'infra/garage/credentials'
New-Item -ItemType Directory -Force -Path $credsDir | Out-Null
Set-Content -Path (Join-Path $credsDir 'access_key') -Value $access -NoNewline
Set-Content -Path (Join-Path $credsDir 'secret_key') -Value $secret -NoNewline
Write-Host '[bootstrap] wrote credentials to infra/garage/credentials/'

Write-Host '[bootstrap] starting application services...'
docker compose up -d api cv-worker geo-worker web

Write-Host ''
Write-Host '[bootstrap] done.'
Write-Host '  UI:  http://localhost:3000   (admin / admin123)'
Write-Host '  API: http://localhost:8000/docs'
