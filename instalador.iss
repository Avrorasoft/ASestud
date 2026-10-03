[Setup]
; Información de la aplicación
AppName=ASestud - Gestión Escolar
AppVersion=1.0
AppPublisher=Avrora Soft - Vibola LLC
AppPublisherURL=https://t.me/TuContacto
AppSupportURL=https://t.me/TuContacto
AppUpdatesURL=https://t.me/TuContacto

; Configuración de carpetas y salida
DefaultDirName={autopf}\Avrora Soft\ASestud
DefaultGroupName=Avrora Soft
OutputDir=D:\colegio_vaca_diez\Output
OutputBaseFilename=Instalar_ASestud_v1.0
Compression=lzma2/ultra
SolidCompression=yes
PrivilegesRequired=admin

; Icono del instalador
SetupIconFile=D:\colegio_vaca_diez\asestud_icon.ico

[Dirs]
; Otorga permisos de escritura a la carpeta para que la base de datos SQLite y subidas funcionen sin bloqueos
Name: "{app}"; Permissions: users-modify
Name: "{app}\static\uploads"; Permissions: users-modify

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copia todos los archivos compilados por PyInstaller e incluye el icono dentro de la instalación
Source: "D:\colegio_vaca_diez\dist\ASestud\*"; DestDir: "{app}"; Excludes: "licencia.key"; Flags: ignoreversion recursesubdirs createallsubdirs; Permissions: users-modify
Source: "D:\colegio_vaca_diez\asestud_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Accesos directos configurados con el WorkingDir y el IconFilename para mostrar el logotipo corporativo
Name: "{group}\ASestud"; Filename: "{app}\ASestud.exe"; WorkingDir: "{app}"; IconFilename: "{app}\asestud_icon.ico"
Name: "{group}\Desinstalar ASestud"; Filename: "{uninstallexe}"; WorkingDir: "{app}"
Name: "{autodesktop}\ASestud"; Filename: "{app}\ASestud.exe"; WorkingDir: "{app}"; IconFilename: "{app}\asestud_icon.ico"; Tasks: desktopicon

[Run]
; Ejecuta la aplicación al finalizar manteniendo el directorio de trabajo correcto
Filename: "{app}\ASestud.exe"; WorkingDir: "{app}"; Description: "Ejecutar ASestud ahora"; Flags: nowait postinstall skipifsilent

[Code]
var
  SerialPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  SerialPage := CreateInputQueryPage(wpSelectDir,
    'Activación del Sistema', 'Ingrese su licencia de Avrora Soft.',
    'Por favor, introduzca el número de serie proporcionado por Avrora Soft para activar ASestud.');
  SerialPage.Add('Número de Licencia:', False);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = SerialPage.ID then
  begin
    if Trim(SerialPage.Values[0]) = '' then
    begin
      MsgBox('Debe ingresar un número de licencia válido para continuar con la instalación.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SerialText: String;
  FileName: String;
begin
  if CurStep = ssPostInstall then
  begin
    SerialText := Trim(SerialPage.Values[0]);
    FileName := ExpandConstant('{app}\licencia.key');
    SaveStringToFile(FileName, SerialText, False);
  end;
end;