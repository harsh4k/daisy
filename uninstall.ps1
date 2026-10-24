<#
.SYNOPSIS
  Removes Daisy: the program, the Start Menu shortcut and the Windows startup entry.
  Your settings (config.json) are kept unless you pass -RemoveSettings.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Daisy'),
    [switch]$RemoveSettings
)
$ErrorActionPreference = 'Stop'

$target = Join-Path $InstallDir 'Daisy.exe'
$running = @(Get-CimInstance Win32_Process -Filter "Name='Daisy.exe'" | Where-Object { $_.ExecutablePath -eq $target })
foreach ($p in $running) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
if ($running.Count) { Start-Sleep -Seconds 2 }

# Windows startup entry (and the approval Windows keeps for it).
foreach ($path in 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
                  'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run') {
    Remove-ItemProperty -Path $path -Name 'Daisy' -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath('Programs')) 'Daisy.lnk') -Force -ErrorAction SilentlyContinue

foreach ($name in 'Daisy.exe', 'Daisy.previous.exe', 'LICENSE') {
    Remove-Item -LiteralPath (Join-Path $InstallDir $name) -Force -ErrorAction SilentlyContinue
}
if ($RemoveSettings) {
    Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host 'Daisy and its settings were removed.' -ForegroundColor Green
} else {
    Write-Host "Daisy was removed. Your settings are kept in $InstallDir\config.json." -ForegroundColor Green
    Write-Host 'Delete that folder, or run again with -RemoveSettings, to remove them too.'
}
