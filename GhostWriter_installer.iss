; Установщик Windows (Inno Setup) для каталога PyInstaller onedir: dist\GhostWriter\
;
; White-label: имя в мастере установки и путь в Program Files должны совпадать с
; config/config.json (поле app_name). Имя EXE и имя каталога dist — с GhostWriter.spec
; (секции EXE и COLLECT, поле name). При смене бренда правьте #define ниже и при необходимости пути Source.

#define MyAppName "Ghost Writer"
#define MyAppExeName "GhostWriter.exe"
#define MyAppVersion "1.0"
#define MyAppPublisher "Ghost Writer"

[Setup]
; Уникальный AppId (фигурные скобки удвоены — синтаксис Inno). При форке продукта смените GUID.
AppId={{F8E2B4A1-0C3D-4E5F-9A8B-2D1C0E7F6A5B}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=GhostWriter_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
; Иконка мастера (если файла нет — закомментируйте строку)
SetupIconFile=assets\icons\app_icon.ico

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\GhostWriter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
