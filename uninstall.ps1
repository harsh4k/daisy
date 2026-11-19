<#
.SYNOPSIS
  Removes Daisy: the program, the Start Menu shortcut and the Windows startup entry.
  Your settings (config.json) are kept unless you pass -RemoveSettings.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = $PSScriptRoot,
    [switch]$RemoveSettings
)
$ErrorActionPreference = 'Stop'

$InstallDir = (Get-Item -LiteralPath $InstallDir).FullName
if ($InstallDir -eq [IO.Path]::GetPathRoot($InstallDir) -or
    (Test-Path -LiteralPath (Join-Path $InstallDir 'main.py'))) {
    throw 'Run the uninstaller inside the Daisy installation, not a drive root or source checkout.'
}
$InstallDir = $InstallDir.TrimEnd([char[]]'\/')
$marker = Join-Path $InstallDir '.daisy-install.json'
if (-not (Test-Path -LiteralPath $marker)) {
    throw 'No Daisy installation record was found. Update Daisy before using this uninstaller.'
}
$record = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
if ($record.kind -ne 'Daisy' -or $record.directory -ne $InstallDir -or
    ((Get-Item -LiteralPath $InstallDir).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'The Daisy installation record does not match this directory.'
}

$target = Join-Path $InstallDir 'Daisy.exe'
$running = @(Get-CimInstance Win32_Process -Filter "Name='Daisy.exe'" | Where-Object { $_.ExecutablePath -eq $target })
foreach ($p in $running) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
if ($running.Count) { Start-Sleep -Seconds 2 }

$runPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$command = Get-ItemPropertyValue -Path $runPath -Name 'Daisy' -ErrorAction SilentlyContinue
if ($command -eq $target -or $command -eq ('"' + $target + '"')) {
    foreach ($path in $runPath, 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run') {
        Remove-ItemProperty -Path $path -Name 'Daisy' -ErrorAction SilentlyContinue
    }
}
$shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'Daisy.lnk'
if (Test-Path -LiteralPath $shortcut) {
    $shell = New-Object -ComObject WScript.Shell
    if ($shell.CreateShortcut($shortcut).TargetPath -eq $target) {
        Remove-Item -LiteralPath $shortcut -Force -ErrorAction SilentlyContinue
    }
}

foreach ($name in 'Daisy.exe', 'Daisy.previous.exe', 'LICENSE', 'NOTICE.md') {
    Remove-Item -LiteralPath (Join-Path $InstallDir $name) -Force -ErrorAction SilentlyContinue
}
if ($RemoveSettings) {
    foreach ($name in 'config.json', 'mode_state.json', '.daisy-install.json', 'uninstall.ps1') {
        Remove-Item -LiteralPath (Join-Path $InstallDir $name) -Force -ErrorAction SilentlyContinue
    }
    if (-not (Get-ChildItem -LiteralPath $InstallDir -Force | Select-Object -First 1)) {
        Remove-Item -LiteralPath $InstallDir -Force
    }
    Write-Host 'Daisy and its settings were removed. Any unrelated files were kept.' -ForegroundColor Green
} else {
    Write-Host "Daisy was removed. Your settings are kept in $InstallDir\config.json." -ForegroundColor Green
    Write-Host 'Delete that folder, or run again with -RemoveSettings, to remove them too.'
}
