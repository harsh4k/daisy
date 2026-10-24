<#
.SYNOPSIS
  Installs Daisy for the current user. No admin rights needed.

.EXAMPLE
  irm https://raw.githubusercontent.com/harsh4k/daisy/main/install.ps1 | iex

.EXAMPLE
  .\install.ps1 -Startup          # also start Daisy with Windows
  .\install.ps1 -Version v1.0.0   # a specific release

Downloads Daisy.exe from the GitHub release, checks its SHA-256, installs it to
%LOCALAPPDATA%\Programs\Daisy, adds a Start Menu shortcut and starts it.
Running it again updates Daisy and keeps your settings (config.json).
#>
[CmdletBinding()]
param(
    [string]$Version = 'latest',
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Daisy'),
    [switch]$Startup,
    [switch]$NoLaunch
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$repo = 'harsh4k/daisy'

if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'Daisy needs 64-bit Windows 10 or 11.'
}
if ([Environment]::OSVersion.Version.Build -lt 17763) {
    throw 'Daisy needs Windows 10 version 1809 or newer.'
}

function Get-Sha256([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }

# 1. Find Daisy.exe: next to this script (an extracted release zip), else download it.
$here = if ($PSScriptRoot) { $PSScriptRoot } else { $null }
$work = Join-Path ([IO.Path]::GetTempPath()) ('daisy-install-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
try {
    if ($here -and (Test-Path -LiteralPath (Join-Path $here 'Daisy.exe'))) {
        $source = Join-Path $here 'Daisy.exe'
        Write-Host 'Using the Daisy.exe next to this script.'
    } else {
        $api = if ($Version -eq 'latest') { "https://api.github.com/repos/$repo/releases/latest" }
               else { "https://api.github.com/repos/$repo/releases/tags/$Version" }
        Write-Host "Finding Daisy ($Version)..."
        $release = Invoke-RestMethod -Uri $api -Headers @{ 'User-Agent' = 'daisy-installer' }
        $zip = $release.assets | Where-Object { $_.name -eq 'Daisy-win-x64.zip' } | Select-Object -First 1
        $sum = $release.assets | Where-Object { $_.name -eq 'Daisy-win-x64.zip.sha256' } | Select-Object -First 1
        if (-not $zip -or -not $sum) { throw "Release $($release.tag_name) has no Daisy-win-x64.zip with a checksum." }
        $zipPath = Join-Path $work $zip.name
        Write-Host "Downloading $($release.tag_name) ($([math]::Round($zip.size / 1MB)) MB)..."
        Invoke-WebRequest -Uri $zip.browser_download_url -OutFile $zipPath -Headers @{ 'User-Agent' = 'daisy-installer' }
        $expected = ((Invoke-RestMethod -Uri $sum.browser_download_url -Headers @{ 'User-Agent' = 'daisy-installer' }) -split '\s+')[0].ToLowerInvariant()
        if ((Get-Sha256 $zipPath) -ne $expected) { throw 'Checksum mismatch: the download is damaged or was changed. Nothing was installed.' }
        Expand-Archive -LiteralPath $zipPath -DestinationPath $work -Force
        $source = Join-Path $work 'Daisy.exe'
        if (-not (Test-Path -LiteralPath $source)) { throw 'The release zip has no Daisy.exe.' }
    }

    # 2. Stop a running copy so the file can be replaced.
    $target = Join-Path $InstallDir 'Daisy.exe'
    $running = @(Get-CimInstance Win32_Process -Filter "Name='Daisy.exe'" | Where-Object { $_.ExecutablePath -eq $target })
    foreach ($p in $running) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($running.Count) { Start-Sleep -Seconds 2 }

    # 3. Install, keeping the previous version for one-step rollback.
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    if (Test-Path -LiteralPath $target) {
        Copy-Item -LiteralPath $target -Destination (Join-Path $InstallDir 'Daisy.previous.exe') -Force
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
    if ((Get-Sha256 $source) -ne (Get-Sha256 $target)) { throw 'The installed file does not match the download.' }
    foreach ($extra in 'uninstall.ps1', 'LICENSE') {
        if ($here -and (Test-Path -LiteralPath (Join-Path $here $extra))) { Copy-Item (Join-Path $here $extra) $InstallDir -Force }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $InstallDir 'uninstall.ps1'))) {
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/$repo/main/uninstall.ps1" -OutFile (Join-Path $InstallDir 'uninstall.ps1') -ErrorAction SilentlyContinue
    }

    # 4. First install only: start with settings that do not touch Windows startup.
    $config = Join-Path $InstallDir 'config.json'
    if (-not (Test-Path -LiteralPath $config)) {
        $first = @{ start_with_windows = [bool]$Startup }
        $first | ConvertTo-Json | Set-Content -LiteralPath $config -Encoding UTF8
    } elseif ($Startup) {
        Write-Host 'Your settings already exist; turn on "Start with Windows" in Daisy (right-click the island).'
    }

    # 5. Start Menu shortcut.
    $menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Daisy.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($menu)
    $link.TargetPath = $target
    $link.WorkingDirectory = $InstallDir
    $link.Description = 'Daisy: a Dynamic Island for Windows'
    $link.Save()

    Write-Host ''
    Write-Host "Daisy is installed in $InstallDir" -ForegroundColor Green
    Write-Host 'Hover the pill at the top of your screen. Right-click it for settings.'
    Write-Host "Update later by running this again. Remove it with: & '$InstallDir\uninstall.ps1'"
    if (-not $NoLaunch) { Start-Process -FilePath $target -WorkingDirectory $InstallDir }
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
