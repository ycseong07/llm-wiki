# Register `tailscale serve` so the local FastAPI is reachable over the tailnet via HTTPS.
# Run once on Windows (PowerShell as Admin). Survives reboots because of --bg.
#
# Verify on Mac:  curl https://<windows-host>.<tailnet>.ts.net/v1/health
# Reset later:    tailscale serve reset

$ErrorActionPreference = "Stop"

Write-Output "Current tailscale serve state:"
tailscale serve status

Write-Output ""
Write-Output "Registering 127.0.0.1:8000 -> tailnet HTTPS (port 443)..."
tailscale serve --bg --https=443 http://127.0.0.1:8000

Write-Output ""
Write-Output "New state:"
tailscale serve status
