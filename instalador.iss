; Script de Instalación para Inno Setup
; Proyecto: ASestud - Sistema de Gestión Escolar
; Empresa: Avrora Soft - Vibola LLC

#define MyAppName "ASestud"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Avrora Soft - Vibola LLC"
#define MyAppExeName "ASestud.exe"
#define MyIconName "asestud.ico"

[Setup]
AppId={{E6B9D0A1-4F27-4E28-8C39-B61D1A9F4E5A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=C:\ASestud_App
DisableDirPage=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=C:\ASestud\Output
OutputBaseFilename=Instalador_ASestud
SetupIconFile=C:\ASestud\{#MyIconName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Archivos generados por PyInstaller en dist\ASestud
Source: "C:\ASestud\dist\ASestud\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Copiar el icono directamente al directorio de instalación
Source: "C:\ASestud\{#MyIconName}"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Estructura persistente para base de datos y uploads
Name: "C:\ASestud\uploads"; Permissions: users-full
Name: "C:\ASestud\uploads\boletines"; Permissions: users-full
Name: "C:\ASestud\uploads\chat"; Permissions: users-full

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyIconName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyIconName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent