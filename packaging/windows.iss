#ifndef AppVersion
  #error AppVersion required
#endif
[Setup]
AppId={{B0E00590-D3BF-42DD-AEC5-0CB4EF6C5A17}
AppName=Blurry
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Blurry
DefaultGroupName=Blurry
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir=..\build\desktop-packages
OutputBaseFilename=Blurry-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Blurry.exe
CloseApplications=yes
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
[Files]
Source: "..\build\desktop-dist\Blurry\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{group}\Blurry"; Filename: "{app}\Blurry.exe"
Name: "{group}\Uninstall Blurry"; Filename: "{uninstallexe}"
[Registry]
Root: HKCU; Subkey: "Software\chronocol.com\blurry"; Flags: uninsdeletekey
[Run]
Filename: "{app}\Blurry.exe"; Description: "Blurry"; Flags: nowait postinstall skipifsilent
