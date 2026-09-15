#define AppVersion "0.1.1"
[Setup]
AppId={{C6CBEF96-D7B1-4E70-8493-F192E22D9308}
AppName=VidVeya
AppVersion={#AppVersion}
AppPublisher=VidVeya
AppPublisherURL=https://github.com/turtoncarllyle/vidveya
AppSupportURL=https://github.com/turtoncarllyle/vidveya/issues
DefaultDirName={localappdata}\Programs\VidVeya
DefaultGroupName=VidVeya
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\VidVeya.exe
OutputDir=..\release
OutputBaseFilename=VidVeya-{#AppVersion}-win-x64-setup
SetupIconFile=..\assets\vidveya.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\VidVeya\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VidVeya"; Filename: "{app}\VidVeya.exe"
Name: "{autodesktop}\VidVeya"; Filename: "{app}\VidVeya.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VidVeya.exe"; Description: "{cm:LaunchProgram,VidVeya}"; Flags: nowait postinstall skipifsilent
