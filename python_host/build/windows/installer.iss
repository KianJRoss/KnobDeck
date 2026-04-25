; Inno Setup installer script for KnobDeck
#define AppName "KnobDeck"
#define AppVersion "0.2.0"
#define AppPublisher "KnobDeck Contributors"
#define AppExeName "KnobDeck.exe"

[Setup]
AppId={{A0E0A2B4-5D65-4C3F-A6E9-1E8C3A7C4B99}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=KnobDeck-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\..\dist\KnobDeck\assets\knobdeck.ico
UninstallDisplayIcon={app}\assets\knobdeck.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\..\dist\KnobDeck\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
