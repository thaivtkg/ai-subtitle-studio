#define MyAppName "AI Subtitle Studio"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Nguyễn Minh Thái"
#define MyAppExeName "AI Subtitle Studio.exe"
#define OutputDir "..\release"

[Setup]
; AppId dùng để định danh ứng dụng cho việc Upgrade/Uninstall sau này
AppId={{9A2B4C6D-1234-5678-90AB-CDEF12345678}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=AISubtitleStudio_Setup_v{#MyAppVersion}
SetupIconFile=..\resources\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\AI Subtitle Studio\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\AI Subtitle Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent