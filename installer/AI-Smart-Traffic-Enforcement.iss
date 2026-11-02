#define AppName "AI Smart Traffic Enforcement System"
#define AppVersion "1.0.0"
#define AppPublisher "Kranthi Kumar Yarlagadda"
#define AppExeName "main.py"

[Setup]
AppId={{8C67DA8E-7F18-4D5E-8A3D-7B0D6C21A501}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\AI Smart Traffic Enforcement System
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=AI-Smart-Traffic-Enforcement-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
UninstallDisplayIcon={app}\models\haarcascades\haarcascade_frontalface_default.xml
DisableProgramGroupPage=yes
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\package-source\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Start Traffic Enforcement (USB Camera)"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\start-camera.ps1"""; WorkingDir: "{app}"
Name: "{group}\Install Python Dependencies"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\install-dependencies.ps1"""; WorkingDir: "{app}"
Name: "{group}\Project Documentation"; Filename: "{app}\README.md"
Name: "{autodesktop}\AI Smart Traffic Enforcement"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\start-camera.ps1"""; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\install-dependencies.ps1"""; Description: "Install Python packages now (recommended; requires internet)"; Flags: postinstall skipifsilent shellexec

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
