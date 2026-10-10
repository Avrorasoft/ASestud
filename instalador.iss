[Setup]
AppId={{8B24A6D2-95E3-4E85-A672-005D7A942F1B}
AppName=ASestud
AppVersion=2.0.0
AppPublisher=Avrora Soft - Vibola LLC
DefaultDirName=C:\ASestud
DefaultGroupName=ASestud
DisableProgramGroupPage=yes
OutputDir=C:\ASestud\instalador_salida
OutputBaseFilename=ASestud_Actualizador_v2
SetupIconFile=C:\ASestud\asestud.ico
UninstallIconFile=C:\ASestud\asestud.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Binarios y recursos compilados por PyInstaller
Source: "C:\ASestud\dist\ASestud\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Icono para accesos directos
Source: "C:\ASestud\asestud.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ASestud"; Filename: "{app}\ASestud.exe"; IconFilename: "{app}\asestud.ico"
Name: "{autodesktop}\ASestud"; Filename: "{app}\ASestud.exe"; IconFilename: "{app}\asestud.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\ASestud.exe"; Description: "{cm:LaunchProgram,ASestud}"; Flags: nowait postinstall skipifsilent