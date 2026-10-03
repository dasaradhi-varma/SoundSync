$ws = New-Object -ComObject WScript.Shell
$desk = [Environment]::GetFolderPath('Desktop')
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Create shortcut on Desktop
$lnkPath = Join-Path $desk "SoundSync Multi-Out.lnk"
$shortcut = $ws.CreateShortcut($lnkPath)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"" + (Join-Path $scriptDir "launch_app.vbs") + "`""
$shortcut.WorkingDirectory = $scriptDir
$iconPath = Join-Path $scriptDir "app_icon.ico"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Description = "SoundSync Multi-Out - Multi-Device Audio Hub"
$shortcut.Save()

Write-Host "[OK] Desktop Shortcut created at: $lnkPath"
