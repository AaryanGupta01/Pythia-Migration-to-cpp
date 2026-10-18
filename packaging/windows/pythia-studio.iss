; PYTHIA Studio installer (Inno Setup 6). Built by packaging/windows/build.py, which passes:
;   /DStageDir=<staged app folder>  /DOutDir=<output folder>  /DAppVersion=1.1.0  /DIconFile=<pythia.ico>  /DLicenseFile=<LICENSE>
; Per-user install (no administrator rights), everything the app needs is inside: Python, the C++ compiler, the UI.

#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
#define AppName "PYTHIA Studio"
#define AppExe "PYTHIA Studio.exe"

[Setup]
AppId={{6C8E4D52-3B1F-4F7A-9E2D-7A1F0C5B9D31}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=PYTHIA team (VIT)
AppComments=Find the slow parts of a Python program, compile them to C++ and prove they behave the same.
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#OutDir}
OutputBaseFilename=PYTHIA-Studio-Setup-{#AppVersion}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile={#LicenseFile}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "PYTHIA Studio"
Name: "{autoprograms}\{#AppName} (command line)"; Filename: "{cmd}"; Parameters: "/k ""cd /d ""%USERPROFILE%"" && set PATH={app};%PATH% && echo PYTHIA command line: pythia prog.py --run    pythia-studio --doctor"""; WorkingDir: "{%USERPROFILE}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
