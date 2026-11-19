"""Exercise installer file behavior without changing Windows integration."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHELL = shutil.which('pwsh') or shutil.which('powershell')


@unittest.skipUnless(SHELL, 'PowerShell is required')
class InstallerTests(unittest.TestCase):
    def run_script(self, body):
        shortcut = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Daisy.lnk'
        shortcut_before = shortcut.read_bytes() if shortcut.exists() else None
        with tempfile.TemporaryDirectory(prefix='daisy-installer-test-') as folder:
            sandbox = Path(folder)
            package = sandbox / 'package'
            package.mkdir()
            for name in ('install.ps1', 'uninstall.ps1', 'LICENSE', 'NOTICE.md'):
                shutil.copyfile(ROOT / name, package / name)
            (package / 'Daisy.exe').write_bytes(b'test executable')
            script = sandbox / 'test.ps1'
            script.write_text(r'''
$ErrorActionPreference = 'Stop'
$sandbox = $PSScriptRoot
$package = Join-Path $sandbox 'package'
$target = Join-Path $sandbox 'custom-install'
$env:LOCALAPPDATA = Join-Path $sandbox 'localappdata'
class TestShortcut {
    [string]$TargetPath
    [string]$WorkingDirectory
    [string]$Description
    [void] Save() { [TestShell]::SavedTarget = $this.TargetPath }
}
class TestShell {
    static [string]$SavedTarget
    [TestShortcut] CreateShortcut([string]$path) {
        $link = [TestShortcut]::new()
        $link.TargetPath = [TestShell]::SavedTarget
        return $link
    }
}
function New-Object {
    [CmdletBinding(DefaultParameterSetName='Type')]
    param(
        [Parameter(ParameterSetName='Com', Mandatory)][string]$ComObject,
        [Parameter(ParameterSetName='Type', Position=0, Mandatory)][string]$TypeName,
        [Parameter(ParameterSetName='Type', Position=1)][object[]]$ArgumentList,
        [Parameter(ParameterSetName='Type')][hashtable]$Property
    )
    if ($ComObject -eq 'WScript.Shell') { return [TestShell]::new() }
    Microsoft.PowerShell.Utility\New-Object @PSBoundParameters
}
function Get-CimInstance { param($ClassName, $Filter) return @() }
function Get-ItemPropertyValue { param($Path, $Name, $ErrorAction) return $global:daisyTestRunEntry }
function Remove-ItemProperty { param($Path, $Name, $ErrorAction) $global:daisyTestStartupRemoved = $true }
function Remove-Item {
    [CmdletBinding()]
    param([string[]]$LiteralPath, [switch]$Force, [switch]$Recurse)
    foreach ($path in $LiteralPath) {
        if ($path -eq (Join-Path ([Environment]::GetFolderPath('Programs')) 'Daisy.lnk')) {
            $global:daisyTestShortcutRemoved = $true
            return
        }
        $absolute = [IO.Path]::GetFullPath($path)
        $allowed = $absolute.StartsWith($sandbox + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase) -or
            $absolute.StartsWith([IO.Path]::GetTempPath() + 'daisy-install-',
            [StringComparison]::OrdinalIgnoreCase)
        if (-not $allowed) { throw "Refusing removal outside test roots: $absolute" }
    }
    Microsoft.PowerShell.Management\Remove-Item @PSBoundParameters
}
''' + body, encoding='utf-8')
            environment = os.environ.copy()
            if Path(SHELL).name.lower() == 'powershell.exe':
                environment['PSModulePath'] = str(Path(environment['WINDIR']) /
                    'System32/WindowsPowerShell/v1.0/Modules')
            result = subprocess.run([SHELL, '-NoProfile', '-File', str(script)],
                                    capture_output=True, text=True, timeout=30,
                                    env=environment)
            shortcut_after = shortcut.read_bytes() if shortcut.exists() else None
            self.assertEqual(shortcut_after, shortcut_before, 'Real shortcut was changed')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_installed_uninstaller_defaults_to_its_custom_directory(self):
        self.run_script(r'''
& (Join-Path $package 'install.ps1') -InstallDir ($target + '\') -NoLaunch
& (Join-Path $target 'uninstall.ps1')
if (Test-Path -LiteralPath (Join-Path $target 'Daisy.exe')) {
    throw 'The uninstaller left the custom installation in place.'
}
if (-not (Test-Path -LiteralPath (Join-Path $target 'config.json'))) {
    throw 'Uninstall removed settings without -RemoveSettings.'
}
& (Join-Path $target 'uninstall.ps1') -RemoveSettings
if (Test-Path -LiteralPath $target) { throw 'Empty installation was not removed.' }
''')

    def test_remove_settings_keeps_unrelated_files(self):
        self.run_script(r'''
& (Join-Path $package 'install.ps1') -InstallDir $target -NoLaunch
$unrelated = Join-Path $target 'keep.txt'
Set-Content -LiteralPath $unrelated -Value 'not owned by Daisy'
& (Join-Path $target 'uninstall.ps1') -RemoveSettings
if (-not (Test-Path -LiteralPath $unrelated)) { throw 'Unrelated file was removed.' }
if (Test-Path -LiteralPath (Join-Path $target 'config.json')) { throw 'Settings remain.' }
''')

    def test_standalone_uninstaller_refuses_unowned_directory(self):
        self.run_script(r'''
$refused = $false
try { & (Join-Path $package 'uninstall.ps1') -RemoveSettings }
catch { $refused = $true }
if (-not $refused) { throw 'Standalone uninstaller accepted an unowned directory.' }
if (-not (Test-Path -LiteralPath (Join-Path $package 'Daisy.exe'))) {
    throw 'Standalone uninstaller changed its folder before refusing.'
}
''')

    def test_uninstall_keeps_another_installations_integrations(self):
        self.run_script(r'''
& (Join-Path $package 'install.ps1') -InstallDir $target -NoLaunch
[TestShell]::SavedTarget = 'X:\Other\Daisy.exe'
$global:daisyTestRunEntry = '"X:\Other\Daisy.exe"'
$global:daisyTestStartupRemoved = $false
$global:daisyTestShortcutRemoved = $false
& (Join-Path $target 'uninstall.ps1')
if ($global:daisyTestStartupRemoved -or $global:daisyTestShortcutRemoved) {
    throw 'Uninstall removed integration belonging to another installation.'
}
''')

    def test_download_installs_companions_from_verified_archive(self):
        self.run_script(r'''
$archive = Join-Path $sandbox 'release.zip'
Compress-Archive -Path (Join-Path $package '*') -DestinationPath $archive
$expectedNotice = Get-Content -LiteralPath (Join-Path $package 'NOTICE.md') -Raw
$global:daisyTestChecksum = '0' * 64
Remove-Item -LiteralPath (Join-Path $package 'Daisy.exe')
Set-Content -LiteralPath (Join-Path $package 'NOTICE.md') -Value 'wrong source notices'
function Invoke-RestMethod {
    param($Uri, $Headers)
    if ($Uri -eq 'https://fixture/checksum') {
        return $global:daisyTestChecksum
    }
    $global:daisyTestReleaseRequest = $Uri
    return @{ tag_name = 'fixture'; assets = @(
        @{name='Daisy-win-x64.zip'; browser_download_url='https://fixture/archive'; size=1},
        @{name='Daisy-win-x64.zip.sha256'; browser_download_url='https://fixture/checksum'}) }
}
function Invoke-WebRequest {
    param($Uri, $OutFile, $Headers)
    Copy-Item -LiteralPath $archive -Destination $OutFile
}
New-Item -ItemType Directory -Path $target | Out-Null
Set-Content -LiteralPath (Join-Path $target 'Daisy.exe') -Value 'old installed executable'
$rejected = $false
try { & (Join-Path $package 'install.ps1') -InstallDir $target -NoLaunch }
catch { $rejected = $true }
if (-not $rejected) { throw 'A checksum mismatch was accepted.' }
if ((Get-Content -LiteralPath (Join-Path $target 'Daisy.exe')).Trim() -ne 'old installed executable') {
    throw 'Failed checksum changed the existing installation.'
}
if ($global:daisyTestReleaseRequest -ne 'https://api.github.com/repos/harsh4k/daisy/releases/latest') {
    throw 'Default installation did not request the latest release.'
}
$global:daisyTestChecksum = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
& (Join-Path $package 'install.ps1') -Version 'fixture' -InstallDir $target -NoLaunch
if ($global:daisyTestReleaseRequest -ne 'https://api.github.com/repos/harsh4k/daisy/releases/tags/fixture') {
    throw 'Explicit version did not request that release.'
}
if ((Get-Content -LiteralPath (Join-Path $target 'NOTICE.md') -Raw) -ne $expectedNotice) {
    throw 'Installer used companions from outside the verified release archive.'
}
& (Join-Path $target 'uninstall.ps1') -RemoveSettings
''')

    def test_install_preserves_notices_and_update_keeps_settings(self):
        self.run_script(r'''
& (Join-Path $package 'install.ps1') -InstallDir $target -NoLaunch
$settings = Join-Path $target 'config.json'
$customSettings = '{"start_with_windows":false,"test_setting":"keep me"}'
Set-Content -LiteralPath $settings -Value $customSettings -NoNewline
& (Join-Path $package 'install.ps1') -InstallDir $target -NoLaunch
if ((Get-Content -LiteralPath $settings -Raw) -ne $customSettings) {
    throw 'Update changed existing settings.'
}
if (-not (Test-Path -LiteralPath (Join-Path $target 'Daisy.previous.exe'))) {
    throw 'Update did not retain a rollback executable.'
}
if (-not (Test-Path -LiteralPath (Join-Path $target 'NOTICE.md'))) {
    throw 'Install dropped the bundled third-party notices.'
}
''')


if __name__ == '__main__':
    unittest.main()
