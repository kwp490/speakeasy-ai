; ─────────────────────────────────────────────────────────────────────────────
; dictat0r.AI v3 Inno Setup Installer Script — CPU-Only Variant
;
; Produces a single dictator-AI-CPU-Setup-0.3.1.exe that handles:
;   - File extraction (from PyInstaller dist/dictator-cpu/ output)
;   - HuggingFace token prompt + Cohere Transcribe model download
;   - Desktop + Start Menu shortcuts
;   - Data migration from previous installs
;   - Windows Defender exclusions
;   - Silent / unattended mode
;
; This is the CPU-only variant: no CUDA libraries, no GPU detection,
; smaller installer size. Transcription runs on CPU (slower but works
; on any system without a dedicated NVIDIA GPU).
;
; Build:
;   pyinstaller dictator-cpu.spec
;   iscc installer\dictator-cpu-setup.iss
;
; Requires Inno Setup 6.x — https://jrsoftware.org/isdl.php
; ─────────────────────────────────────────────────────────────────────────────

#define MyAppName "dictat0r.AI"
#define MyAppVersion "0.3.1"
#define MyAppPublisher "kwp490"
#define MyAppURL "https://github.com/kwp490/dictat0rAI-v3"
#define MyAppExeName "dictator.exe"

[Setup]
; Same AppId as GPU variant — installing one replaces the other
AppId={{A1B2C3D4-5E6F-7A8B-9C0D-E1F2A3B4C5D6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} (CPU)
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\dictat0r.AI
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=Output
OutputBaseFilename=dictator-AI-CPU-Setup-{#MyAppVersion}
#ifdef FastCompress
Compression=lzma2/fast
SolidCompression=no
#else
Compression=lzma2/ultra64
SolidCompression=yes
#endif
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
MinVersion=10.0
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\dictator-cpu\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "cohere-model-setup.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\models";  Permissions: users-modify
Name: "{app}\config";  Permissions: users-modify
Name: "{app}\logs";    Permissions: users-modify
Name: "{app}\temp";    Permissions: users-modify

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; Comment: "dictat0r.AI — Voice to Text (CPU)"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; Comment: "dictat0r.AI — Voice to Text (CPU)"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Add-MpPreference -ExclusionPath '{app}' -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionProcess '{app}\{#MyAppExeName}' -ErrorAction SilentlyContinue"""; \
    Flags: runhidden waituntilterminated; StatusMsg: "Configuring Windows Defender exclusions..."

Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\temp"
Type: filesandordirs; Name: "{app}\config"

[UninstallRun]
Filename: "powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Remove-MpPreference -ExclusionPath '{app}' -ErrorAction SilentlyContinue; Remove-MpPreference -ExclusionProcess '{app}\{#MyAppExeName}' -ErrorAction SilentlyContinue"""; \
    Flags: runhidden waituntilterminated; RunOnceId: "DefenderExclusions"

[Code]
var
  TokenPage: TWizardPage;
  TokenEdit: TNewEdit;
  DownloadPage: TOutputProgressWizardPage;
  SummaryPage: TWizardPage;
  SummaryMemo: TNewMemo;
  HFToken: String;
  CleanInstall: Boolean;
  ModelExists: Boolean;

{ Called before file extraction.  Detects an existing install and cleans
  config/logs/temp so upgrades always start with fresh settings.
  Silent mode: auto-clean.  Interactive mode: prompt Clean vs Repair.
  Models are always preserved. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  AppDir, ConfigDir, LogsDir, TempDir: String;
  DoClean: Boolean;
begin
  Result := '';
  CleanInstall := False;
  AppDir   := ExpandConstant('{app}');
  ConfigDir := AppDir + '\config';
  LogsDir   := AppDir + '\logs';
  TempDir   := AppDir + '\temp';

  { Only act if there is an existing install with a config directory }
  if not DirExists(ConfigDir) then
    Exit;

  if WizardSilent then
    DoClean := True
  else
    DoClean := (MsgBox('An existing dictat0r.AI installation was detected.' + #13#10 + #13#10 +
                        'Clean Install — remove old settings, logs and temp files (recommended).' + #13#10 +
                        'Repair — keep existing settings and overwrite application files only.' + #13#10 + #13#10 +
                        'Perform a Clean Install?',
                        mbConfirmation, MB_YESNO) = IDYES);

  if DoClean then
  begin
    CleanInstall := True;
    DelTree(ConfigDir, True, True, True);
    DelTree(LogsDir,  True, True, True);
    DelTree(TempDir,  True, True, True);
  end;
end;

procedure CreateTokenPage;
var
  Lbl: TNewStaticText;
  TopPos: Integer;
begin
  TokenPage := CreateCustomPage(wpSelectDir,
    'HuggingFace Authentication',
    'A HuggingFace account and access token are required to download the Cohere Transcribe model.');

  TopPos := 0;

  Lbl := TNewStaticText.Create(TokenPage);
  Lbl.Parent := TokenPage.Surface;
  Lbl.Left := 0;  Lbl.Top := TopPos;
  Lbl.Width := TokenPage.SurfaceWidth;
  Lbl.Caption := 'CPU-Only Build';
  Lbl.Font.Style := [fsBold];  Lbl.Font.Size := 9;
  TopPos := TopPos + ScaleY(18);

  Lbl := TNewStaticText.Create(TokenPage);
  Lbl.Parent := TokenPage.Surface;
  Lbl.Left := ScaleX(8);  Lbl.Top := TopPos;
  Lbl.Width := TokenPage.SurfaceWidth - ScaleX(8);
  Lbl.AutoSize := False;  Lbl.WordWrap := True;  Lbl.Height := ScaleY(36);
  Lbl.Caption := 'This is the CPU-only version. Transcription runs without a GPU.' + #13#10 +
                 'It works on any system but will be slower than the GPU version.';
  Lbl.Font.Color := $808080;
  TopPos := TopPos + ScaleY(40);

  Lbl := TNewStaticText.Create(TokenPage);
  Lbl.Parent := TokenPage.Surface;
  Lbl.Left := 0;  Lbl.Top := TopPos;
  Lbl.Width := TokenPage.SurfaceWidth;
  Lbl.Caption := 'HuggingFace Access Token';
  Lbl.Font.Style := [fsBold];  Lbl.Font.Size := 9;
  TopPos := TopPos + ScaleY(22);

  Lbl := TNewStaticText.Create(TokenPage);
  Lbl.Parent := TokenPage.Surface;
  Lbl.Left := ScaleX(8);  Lbl.Top := TopPos;
  Lbl.Width := TokenPage.SurfaceWidth - ScaleX(8);
  Lbl.AutoSize := False;  Lbl.WordWrap := True;  Lbl.Height := ScaleY(56);
  Lbl.Caption := 'To download the model you need a free HuggingFace account:' + #13#10 +
                 '  1. Sign up at https://huggingface.co/join' + #13#10 +
                 '  2. Accept the license at https://huggingface.co/CohereLabs/cohere-transcribe-03-2026' + #13#10 +
                 '  3. Create a Read token at https://huggingface.co/settings/tokens';
  Lbl.Font.Color := $808080;
  TopPos := TopPos + ScaleY(60);

  Lbl := TNewStaticText.Create(TokenPage);
  Lbl.Parent := TokenPage.Surface;
  Lbl.Left := ScaleX(8);  Lbl.Top := TopPos;
  Lbl.Width := TokenPage.SurfaceWidth - ScaleX(8);
  Lbl.Caption := 'Paste your HuggingFace token below (starts with hf_):';
  TopPos := TopPos + ScaleY(18);

  TokenEdit := TNewEdit.Create(TokenPage);
  TokenEdit.Parent := TokenPage.Surface;
  TokenEdit.Left := ScaleX(8);  TokenEdit.Top := TopPos;
  TokenEdit.Width := TokenPage.SurfaceWidth - ScaleX(16);
  TokenEdit.PasswordChar := '*';
  TokenEdit.Text := '';
  TopPos := TopPos + ScaleY(28);

  Lbl := TNewStaticText.Create(TokenPage);
  Lbl.Parent := TokenPage.Surface;
  Lbl.Left := ScaleX(8);  Lbl.Top := TopPos;
  Lbl.Width := TokenPage.SurfaceWidth - ScaleX(8);
  Lbl.AutoSize := False;  Lbl.WordWrap := True;  Lbl.Height := ScaleY(28);
  Lbl.Caption := 'Your token is used only during setup to download the model. It is not stored.';
  Lbl.Font.Color := $808080;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  Info: String;
begin
  HFToken := Trim(TokenEdit.Text);
  Info := '';
  Info := Info + 'Application:' + NewLine;
  Info := Info + Space + 'dictat0r.AI {#MyAppVersion} (CPU) — Native Windows Voice-to-Text' + NewLine + NewLine;
  if MemoDirInfo <> '' then
    Info := Info + MemoDirInfo + NewLine + NewLine;
  Info := Info + 'Speech engine:' + NewLine;
  Info := Info + Space + 'Cohere Transcribe 03-2026  (CPU mode, 14 languages)' + NewLine + NewLine;
  Info := Info + 'The installer will:' + NewLine;
  Info := Info + Space + '1. Extract dictat0r.AI application files' + NewLine;
  Info := Info + Space + '2. Download Cohere Transcribe model from HuggingFace' + NewLine;
  Info := Info + Space + '3. Create desktop and Start Menu shortcuts' + NewLine;
  Info := Info + Space + '4. Configure Windows Defender exclusions' + NewLine + NewLine;
  Info := Info + 'Mode: CPU-only (no GPU required)' + NewLine;
  Result := Info;
end;

procedure DirectoryCopy(SourceDir, DestDir: String);
var
  FindRec: TFindRec;
  SourcePath, DestPath: String;
begin
  if not ForceDirectories(DestDir) then Exit;
  if FindFirst(SourceDir + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name = '.') or (FindRec.Name = '..') then Continue;
        SourcePath := SourceDir + '\' + FindRec.Name;
        DestPath := DestDir + '\' + FindRec.Name;
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          DirectoryCopy(SourcePath, DestPath)
        else
          CopyFile(SourcePath, DestPath, False);
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure MigrateOldData;
var
  OldSettings, NewSettings, OldModelsDir, NewEngineDir: String;
  FindRec: TFindRec;
  OldLogDir, OldLog, NewLog: String;
  LogFiles: array[0..2] of String;
  I: Integer;
begin
  OldSettings := ExpandConstant('{userappdata}\dictat0r.AI\settings.json');
  NewSettings := ExpandConstant('{app}\config\settings.json');
  if FileExists(OldSettings) and (not FileExists(NewSettings)) then
    CopyFile(OldSettings, NewSettings, False);
  OldModelsDir := ExpandConstant('{localappdata}\dictat0r.AI\models');
  if DirExists(OldModelsDir) then
    if FindFirst(OldModelsDir + '\*', FindRec) then
    begin
      try
        repeat
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
            begin
              NewEngineDir := ExpandConstant('{app}\models\') + FindRec.Name;
              if not DirExists(NewEngineDir) then
                DirectoryCopy(OldModelsDir + '\' + FindRec.Name, NewEngineDir);
            end;
        until not FindNext(FindRec);
      finally
        FindClose(FindRec);
      end;
    end;
  OldLogDir := ExpandConstant('{userappdata}\dictat0r.AI');
  LogFiles[0] := 'dictator.log';
  LogFiles[1] := 'dictator.log.1';
  LogFiles[2] := 'dictator.log.2';
  for I := 0 to 2 do
  begin
    OldLog := OldLogDir + '\' + LogFiles[I];
    NewLog := ExpandConstant('{app}\logs\') + LogFiles[I];
    if FileExists(OldLog) and (not FileExists(NewLog)) then
      CopyFile(OldLog, NewLog, False);
  end;
end;

procedure WriteDefaultSettings;
var
  SettingsFile, Json: String;
begin
  SettingsFile := ExpandConstant('{app}\config\settings.json');
  if not FileExists(SettingsFile) then
  begin
    Json := '{' + #13#10 + '  "engine": "cohere",' + #13#10 + '  "device": "cpu"' + #13#10 + '}';
    SaveStringToFile(SettingsFile, Json, False);
  end;
end;

procedure ConfigureDefenderExclusions;
var
  AppDir, ExeFullPath, PsCmd: String;
  ResultCode: Integer;
begin
  AppDir := ExpandConstant('{app}');
  ExeFullPath := AppDir + '\{#MyAppExeName}';
  PsCmd := 'Add-MpPreference -ExclusionPath ''' + AppDir + ''' -ErrorAction SilentlyContinue; ' +
           'Add-MpPreference -ExclusionProcess ''' + ExeFullPath + ''' -ErrorAction SilentlyContinue';
  Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -Command "' + PsCmd + '"',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure DownloadModel;
var
  ExePath, ModelsDir, TokenArg: String;
  ResultCode: Integer;
begin
  ExePath := ExpandConstant('{app}\{#MyAppExeName}');
  ModelsDir := ExpandConstant('{app}\models');
  DownloadPage := CreateOutputProgressPage('Downloading Model',
    'Downloading the Cohere Transcribe model. This may take several minutes.');
  DownloadPage.Show;
  DownloadPage.SetText('Downloading Cohere Transcribe (CohereLabs/cohere-transcribe-03-2026)...',
    'Source: huggingface.co/CohereLabs/cohere-transcribe-03-2026');
  DownloadPage.SetProgress(0, 1);
  { download_model exit codes: 0 = success, 1 = failure, 2 = auth required }
  TokenArg := '';
  if HFToken <> '' then
    TokenArg := ' --token "' + HFToken + '"';
  try
    Exec(ExePath, 'download-model --target-dir "' + ModelsDir + '"' + TokenArg,
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    if ResultCode = 2 then
      MsgBox('Authentication failed. Make sure you have:' + #13#10 + #13#10 +
             '  1. Accepted the model license on HuggingFace' + #13#10 +
             '  2. Provided a valid access token' + #13#10 + #13#10 +
             'You can retry later by running cohere-model-setup.ps1.',
             mbError, MB_OK)
    else if ResultCode <> 0 then
      MsgBox('Model download failed (exit code ' + IntToStr(ResultCode) + ').' + #13#10 + #13#10 +
             'You can download it later using cohere-model-setup.ps1' + #13#10 +
             'or the model will be downloaded on first launch.',
             mbError, MB_OK);
  except
    MsgBox('Could not start model download.' + #13#10 +
           'You can download the model later using cohere-model-setup.ps1.',
           mbError, MB_OK);
  end;
  DownloadPage.SetProgress(1, 1);
  DownloadPage.Hide;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Summary, InstDir, ModelsDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    if not CleanInstall then
      MigrateOldData;
    WriteDefaultSettings;
    ConfigureDefenderExclusions;
    if not ModelExists then
      DownloadModel;
    InstDir := ExpandConstant('{app}');
    ModelsDir := InstDir + '\models';
    Summary := 'dictat0r.AI {#MyAppVersion} (CPU) installed successfully.' + #13#10 + #13#10;
    Summary := Summary + 'INSTALL LOCATION' + #13#10;
    Summary := Summary + '  ' + InstDir + #13#10 + #13#10;
    Summary := Summary + 'MODEL STATUS' + #13#10;
    if DirExists(ModelsDir + '\cohere') then
      Summary := Summary + '  [OK] Cohere Transcribe — ready' + #13#10
    else
      Summary := Summary + '  [!!] Cohere Transcribe — download failed (run cohere-model-setup.ps1)' + #13#10;
    Summary := Summary + #13#10;
    Summary := Summary + 'VARIANT' + #13#10;
    Summary := Summary + '  CPU-only (no GPU required)' + #13#10 + #13#10;
    Summary := Summary + 'SHORTCUTS' + #13#10;
    Summary := Summary + '  Desktop shortcut created' + #13#10;
    Summary := Summary + '  Start Menu group created' + #13#10 + #13#10;
    Summary := Summary + 'DEFAULT HOTKEYS' + #13#10;
    Summary := Summary + '  Ctrl+Alt+P   Start recording' + #13#10;
    Summary := Summary + '  Ctrl+Alt+L   Stop recording & transcribe' + #13#10;
    Summary := Summary + '  Ctrl+Alt+Q   Quit application' + #13#10;
    SummaryMemo.Text := Summary;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if (PageID = TokenPage.ID) and ModelExists then
    Result := True;
end;

procedure InitializeWizard;
begin
  ModelExists := False;

  CreateTokenPage;
  SummaryPage := CreateCustomPage(wpInfoAfter,
    'Installation Summary', 'Review what was installed and configured.');
  SummaryMemo := TNewMemo.Create(SummaryPage);
  SummaryMemo.Parent := SummaryPage.Surface;
  SummaryMemo.Left := 0;  SummaryMemo.Top := 0;
  SummaryMemo.Width := SummaryPage.SurfaceWidth;
  SummaryMemo.Height := SummaryPage.SurfaceHeight;
  SummaryMemo.ScrollBars := ssVertical;
  SummaryMemo.ReadOnly := True;
  SummaryMemo.Font.Name := 'Consolas';
  SummaryMemo.Font.Size := 9;
  SummaryMemo.Text := 'Installing...';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  CohereDir: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    CohereDir := ExpandConstant('{app}\models\cohere');
    ModelExists := DirExists(CohereDir) and FileExists(CohereDir + '\config.json');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir, ModelsDir, CohereDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    AppDir := ExpandConstant('{app}');
    ModelsDir := AppDir + '\models';
    CohereDir := ModelsDir + '\cohere';
    if DirExists(CohereDir) then
      if not UninstallSilent then
        if MsgBox('Delete the Cohere Transcribe model (~5 GB)?' + #13#10 + #13#10 +
                   'Click Yes to remove, or No to keep for reinstall.',
                   mbConfirmation, MB_YESNO) = IDYES then
          DelTree(CohereDir, True, True, True);
    if DirExists(ModelsDir) then RemoveDir(ModelsDir);
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    AppDir := ExpandConstant('{app}');
    if DirExists(AppDir) then RemoveDir(AppDir);
  end;
end;
