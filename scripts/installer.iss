; LBS Firmware Studio 安装程序脚本（Inno Setup 6）
; 用法: tools\innosetup\ISCC.exe scripts\installer.iss
; 产物: dist\LBS-Firmware-Studio-v0.1.0-setup.exe
;
; 设计要点：per-user 安装（默认 {localappdata}）——应用运行时需写 products.yaml
; 与 products/<产品>/write/（保存脚本/固件目录），Program Files 会因写权限失败。

#define MyAppName "LBS Firmware Studio"
#define MyAppVersion "0.1.0"
#define MyAppExeName "LBS-Firmware-Studio.exe"

[Setup]
AppId={{A4E2445F-AE06-4627-A249-DC56643687B5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=LBS
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={localappdata}\LBS-Firmware-Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=LBS-Firmware-Studio-v{#MyAppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "..\dist\LBS-Firmware-Studio\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
