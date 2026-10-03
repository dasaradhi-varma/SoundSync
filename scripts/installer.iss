; SoundSync Multi-Out - Inno Setup Installer Script
; Created by Dasaradhi Varma

[Setup]
AppId={{8B1A2C3D-4E5F-6A7B-8C9D-0E1F2A3B4C5D}
AppName=SoundSync Multi-Out
AppVersion=1.0.0
AppPublisher=Dasaradhi Varma
AppPublisherURL=https://github.com/dasaradhivarma/sound
DefaultDirName={autopf}\SoundSync Multi-Out
DisableDirPage=no
DefaultGroupName=SoundSync Multi-Out
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=SoundSync_Setup_Inno
SetupIconFile=..\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Messages]
SelectDirDesc=Where should SoundSync Multi-Out be installed?%nCreated by Dasaradhi Varma
SelectDirLabel3=Setup will install SoundSync Multi-Out into the following folder.%n[Created by Dasaradhi Varma]

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\SoundSync.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\SoundSync Multi-Out"; Filename: "{app}\SoundSync.exe"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\SoundSync Multi-Out"; Filename: "{app}\SoundSync.exe"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\SoundSync.exe"; Description: "{cm:LaunchProgram,SoundSync Multi-Out}"; Flags: nowait postinstall skipifsilent
