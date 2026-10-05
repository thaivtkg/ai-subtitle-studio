[Setup]
AppId={{9A2B4C6D-1234-5678-90AB-CDEF12345678}
AppName=AI Subtitle Studio
AppVersion=1.0.0
AppPublisher=ThaiVTKG
DefaultDirName={autopf}\AI Subtitle Studio
DefaultGroupName=AI Subtitle Studio
UninstallDisplayIcon={app}\AI Subtitle Studio.exe
SetupIconFile=resources\app_icon.ico
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=AI_Subtitle_Studio_Setup_v1.0.0
InfoBeforeFile=RELEASE_NOTES.txt

[Files]
Source: "dist\AI Subtitle Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AI Subtitle Studio"; Filename: "{app}\AI Subtitle Studio.exe"
Name: "{autodesktop}\AI Subtitle Studio"; Filename: "{app}\AI Subtitle Studio.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\AI Subtitle Studio.exe"; Description: "{cm:LaunchProgram,AI Subtitle Studio}"; Flags: nowait postinstall skipifsilent
