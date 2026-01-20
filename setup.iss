; Script for Inno Setup - LinkedIn Job Scraper Installer
#define MyAppName "LinkedIn Job Scraper"
#define MyAppVersion "1.0"
#define MyAppPublisher "Plugs"
#define MyAppExeName "LinkedInScraper.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-1234-56789ABCDEF0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=Output
OutputBaseFilename=JobScraperSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

; Disk spanning for large installers (browsers are bundled, making this large)
DiskSpanning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The main executable and all files in the dist folder (including bundled browsers)
Source: "dist\LinkedInScraper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Optionally launch the app after setup
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  MsgBox('This installer includes all required components.' + #13#10 + #13#10 +
         'The Chromium browser is bundled, so no additional downloads are needed.' + #13#10 + #13#10 +
         'Note: The installation size is approximately 500MB due to the bundled browser.', 
         mbInformation, MB_OK);
end;