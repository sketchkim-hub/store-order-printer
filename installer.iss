; Inno Setup 6 스크립트 - 한국어 설치 프로그램 만들기
; 1) build_exe.bat 실행 → dist\FestivalReceipt.exe 생성
; 2) Inno Setup 6 에서 이 파일 열기 → Build > Compile
; 결과: Output\FestivalReceipt-Setup.exe  (버전 지정: ISCC /DAppVersion=1.2.3 installer.iss)

#define AppName "매장용 주문 프린터"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
; 배포자 이름 (수정 가능)
#define AppPublisher "Jsquare"
#define AppExe "FestivalReceipt.exe"

[Setup]
; AppId: 이 프로그램 고유 ID. 앞으로 모든 버전에서 절대 바꾸지 마세요 (업데이트 설치 인식에 사용)
AppId={{CCD497A2-5038-4104-891A-3DFC5C8D83C8}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\FestivalReceipt
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=app.ico
OutputDir=Output
OutputBaseFilename=FestivalReceipt-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕 화면에 바로가기 만들기"; GroupDescription: "추가 작업:"

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "README_한국어.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion
Source: "docs\사용설명서.pdf"; DestDir: "{app}"; Flags: ignoreversion
Source: "docs\빠른시작.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\사용설명서"; Filename: "{app}\사용설명서.pdf"
Name: "{group}\{#AppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{#AppName} 실행"; Flags: nowait postinstall skipifsilent

; 판매 데이터(%APPDATA%\FestivalReceipt)는 제거해도 지우지 않습니다 (매출 기록 보호).
