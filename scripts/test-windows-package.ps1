$ErrorActionPreference = 'Stop'
$package = (Get-ChildItem build/desktop-packages/*-setup.exe).FullName
$app = Join-Path $env:TEMP ('Blurry-package-' + [guid]::NewGuid())
$prefs = 'HKCU:\Software\chronocol.com\blurry'
$env:QT_QPA_PLATFORM = 'offscreen'
function Install-Blurry {
    $p = Start-Process -FilePath $package -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$app`"") -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Installer failed: $($p.ExitCode)" }
}
function Remove-Blurry {
    $p = Start-Process -FilePath "$app/unins000.exe" -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Uninstaller failed: $($p.ExitCode)" }
    if (Test-Path $prefs) { throw 'Preferences survived uninstall' }
    if (Test-Path "$app/Blurry.exe") { throw 'Application survived uninstall' }
}
function Smoke-Blurry {
    $fixture = (Resolve-Path tests/fixtures/public/dental_squadron.jpg).Path
    $p = Start-Process -FilePath "$app/Blurry.exe" -ArgumentList @('__smoke-test', "`"$fixture`"") -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "GUI smoke failed: $($p.ExitCode)" }
}
if (Test-Path $prefs) { throw 'Runner preference store must start empty' }
Install-Blurry
try {
    $version = & "$app/blurry-engine.exe" --version
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^blurry ') { throw 'Frozen CLI version failed' }
    $output = Join-Path $env:TEMP ('Blurry-output-' + [guid]::NewGuid())
    New-Item -ItemType Directory $output | Out-Null
    try {
        $fixture = (Resolve-Path tests/fixtures/public/dental_squadron.jpg).Path
        $report = (& "$app/blurry-engine.exe" --json --strict -o $output $fixture) | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0 -or $report.status -ne 'ok') { throw 'Frozen CLI report failed' }
        if (-not (Test-Path (Join-Path $output $report.output))) { throw 'Frozen CLI output missing' }
    } finally { Remove-Item -Recurse -Force $output }
    Smoke-Blurry
    New-Item -Path $prefs -Force | Out-Null
    New-ItemProperty -Path $prefs -Name onboarded -Value 'true' -PropertyType String -Force | Out-Null
    Install-Blurry
    if ((Get-ItemProperty $prefs).onboarded -ne 'true') { throw 'Upgrade cleared onboarding' }
    Remove-Blurry
    Install-Blurry
    Smoke-Blurry
    Remove-Blurry
} finally {
    if (Test-Path "$app/unins000.exe") { Remove-Blurry }
}
