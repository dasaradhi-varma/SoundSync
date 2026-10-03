$ws = New-Object -ComObject WScript.Shell
$desk = [Environment]::GetFolderPath('Desktop')
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Split-Path -Parent $scriptDir

# Create shortcut on Desktop
$lnkPath = Join-Path $desk "SoundSync Multi-Out.lnk"
$shortcut = $ws.CreateShortcut($lnkPath)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"" + (Join-Path $projectRoot "launch_app.vbs") + "`""
$shortcut.WorkingDirectory = $projectRoot
$iconPath = Join-Path $projectRoot "app_icon.ico"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Description = "SoundSync Multi-Out - Multi-Device Audio Hub"
$shortcut.Save()

Write-Host "[OK] Desktop Shortcut created at: $lnkPath"
