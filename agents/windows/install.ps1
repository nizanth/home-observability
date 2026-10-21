# Install the OTel collector agent as a Windows service.
# Run from an elevated PowerShell:  .\install.ps1 -Gateway <central-host>:4317
param([Parameter(Mandatory = $true)][string]$Gateway)
$ErrorActionPreference = 'Stop'

$Version = '0.116.0'
$Dir     = 'C:\otelcol'
$Svc     = 'otelcol-contrib'
$Url     = "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v$Version/otelcol-contrib_${Version}_windows_amd64.tar.gz"

New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$Tar = Join-Path $env:TEMP 'otelcol.tar.gz'
Invoke-WebRequest -Uri $Url -OutFile $Tar
tar -xzf $Tar -C $Dir otelcol-contrib.exe
Copy-Item (Join-Path $PSScriptRoot 'agent.yaml') "$Dir\config.yaml" -Force

if (Get-Service $Svc -ErrorAction SilentlyContinue) {
    Stop-Service $Svc -Force
    sc.exe delete $Svc | Out-Null
    Start-Sleep -Seconds 2
}
# The collector binary speaks the Windows service protocol natively.
New-Service -Name $Svc -DisplayName 'OpenTelemetry Collector (home)' `
    -BinaryPathName "`"$Dir\otelcol-contrib.exe`" --config `"$Dir\config.yaml`"" `
    -StartupType Automatic | Out-Null

# Service-scoped environment for ${env:GATEWAY_ENDPOINT} in agent.yaml
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\$Svc" `
    -Name Environment -Type MultiString -Value @("GATEWAY_ENDPOINT=$Gateway")

Start-Service $Svc
Get-Service $Svc
Write-Host "Agent running -> $Gateway. Uninstall: Stop-Service $Svc; sc.exe delete $Svc; Remove-Item -Recurse $Dir"
