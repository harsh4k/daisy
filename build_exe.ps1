param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (!$Python) {
        $localPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
        if (Test-Path -LiteralPath $localPython) { $Python = $localPython }
        else { $Python = (Get-Command python -ErrorAction Stop).Source }
    }
    $systemIcu = Join-Path $env:WINDIR 'System32\icuuc.dll'
    if (!(Test-Path -LiteralPath $systemIcu)) { throw 'Windows ICU library is missing.' }
    # Explicit ICU prevents unrelated tools on PATH supplying an incompatible DLL.
    $buildArgs = @('-m', 'PyInstaller', '--noconsole', '--onefile', '--noconfirm',
        '--name', 'Daisy', '--icon', 'assets/daisy.ico',
        '--version-file', 'assets/daisy.version', '--add-data', 'assets;assets',
        '--collect-all', 'winsdk', '--collect-all', 'qtawesome',
        '--hidden-import', 'winsdk.windows.ui.notifications.management',
        '--add-binary', "$systemIcu;.", 'main.py')
    & $Python @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Daisy build failed (exit $LASTEXITCODE)." }
    Write-Output 'Daisy built successfully: dist\Daisy.exe'
} finally { Pop-Location }
