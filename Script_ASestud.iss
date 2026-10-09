[Setup]
; Información General del Sistema
AppName=ASestud
AppVersion=1.0
AppPublisher=Avrora Soft - Vibola LLC
DefaultDirName={autopf}\ASestud
DefaultGroupName=ASestud
OutputDir=Output
OutputBaseFilename=Instalar_ASestud
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

; =========================================================
; ACTIVACIÓN DE PÁGINA DE NÚMERO DE SERIE
; =========================================================
UserInfoPage=yes

; =========================================================
; ÍCONO DEL INSTALADOR Y DESINSTALADOR
; =========================================================
SetupIconFile=asestud.ico
UninstallDisplayIcon={app}\ASestud.exe

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Iconos adicionales:"

[Files]
; Copia todo el contenido de la carpeta compilada
Source: "dist\ASestud\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\ASestud\ngrok.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\ASestud\cloudflared.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "asestud.ico"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\instance"; Permissions: everyone-full
Name: "{app}\static\uploads"; Permissions: everyone-full
Name: "{app}\static\boletines"; Permissions: everyone-full

[Icons]
Name: "{group}\ASestud"; Filename: "{app}\ASestud.exe"; IconFilename: "{app}\asestud.ico"
Name: "{group}\Desinstalar ASestud"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ASestud"; Filename: "{app}\ASestud.exe"; IconFilename: "{app}\asestud.ico"; Tasks: desktopicon

[Run]
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall add rule name=""ASestud_Port5000"" dir=in action=allow protocol=TCP localport=5000"; Flags: runhidden
Filename: "{app}\ASestud.exe"; Description: "Ejecutar ASestud ahora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall delete rule name=""ASestud_Port5000"""; Flags: runhidden

[Code]
// =========================================================
// VALIDACIÓN ESTRUCTURAL DEL KEYGEN DE AVRORA SOFT
// =========================================================
function CheckSerial(Serial: String): Boolean;
var
  Prefix: String;
  TieneTiempo: Boolean;
begin
  Result := False;
  
  // 1. Identificador obligatorio de ASestud
  Prefix := Copy(Serial, 1, 9);
  if Prefix <> 'AVRO-EST-' then Exit;

  // 2. Nivel de edición (PRO o BSC)
  if (Pos('-PRO-', Serial) = 0) and (Pos('-BSC-', Serial) = 0) then Exit;

  // 3. Validar variables de tiempo (Meses, Años o Indefinida)
  TieneTiempo := False;
  if Pos('-2M-', Serial) > 0 then TieneTiempo := True;
  if Pos('-4M-', Serial) > 0 then TieneTiempo := True;
  if Pos('-6M-', Serial) > 0 then TieneTiempo := True;
  if Pos('-1A-', Serial) > 0 then TieneTiempo := True;
  if Pos('-2A-', Serial) > 0 then TieneTiempo := True;
  if Pos('-3A-', Serial) > 0 then TieneTiempo := True;
  if Pos('-4A-', Serial) > 0 then TieneTiempo := True;
  if Pos('-INF-', Serial) > 0 then TieneTiempo := True;
  
  if not TieneTiempo then Exit;

  // 4. Indicador de límite de PCs
  if Pos('PC-', Serial) = 0 then Exit;

  // 5. Longitud mínima de seguridad para el Hash final (mínimo 28 caracteres)
  if Length(Serial) < 28 then Exit;

  // Si cumple con toda la estructura, se habilita la instalación
  Result := True;
end;