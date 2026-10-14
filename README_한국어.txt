매장용 주문 프린터 (FestivalReceipt) - README
=====================================================
노트북 + 영수증 프린터(예: 신화포스 SLK-TS100) / 라벨 프린터로 축제·매장 판매 영수증을 출력합니다.
설정 파일을 직접 고칠 필요 없이 모두 화면에서 설정합니다.
그림이 있는 사장님용 설명서: docs\사용설명서.pdf (또는 .docx), 요약: docs\빠른시작.txt

■ 1. 설치 (사장님용)
1) 프린터 드라이버 설치 (영수증 프린터: 제조사 홈페이지 또는 CD) → USB 연결.
   ※ 라벨 프린터도 드라이버를 설치하세요.
2) FestivalReceipt_Setup_x.x.x.exe 실행 → 다음 → 설치. 바탕 화면에 "매장용 주문 프린터" 아이콘이 생깁니다.
   (설치 없이 쓰려면 FestivalReceipt.exe 를 USB 등에 두고, 같은 폴더에 'data' 폴더를 만들면 포터블 모드)
3) 처음 실행하면 "처음 설정" 마법사가 나옵니다:
   ① 가게 이름 → ② 프린터 선택 후 [테스트 인쇄] → ③ 관리자 PIN(숫자 4자리) 두 번 → ④ 예시 메뉴/빈 메뉴 선택.

■ 2. 판매
- 메뉴 버튼(또는 숫자키 1~9, 0=10번, F1~F12, Shift+F1/F2)을 누르면 오른쪽 "주문 내역"에 담김. 다시 누르면 +1.
- 줄 선택 후 + / - 키(또는 ＋/－ 버튼)로 수량, Delete(또는 [줄 삭제])로 삭제.
- Enter 또는 [결제 / 인쇄] → 미리보기 → Enter(인쇄) / Esc(취소, 기록 안 됨).
- Esc/Backspace 또는 [전체 취소] → 확인 후 주문 비우기.
- 위쪽 "출력 프린터" 체크로 이번에 출력할 프린터 선택 (둘 다 체크 = 둘 다 출력).
- [오늘 매출 출력]: 품목별 수량/금액 합계. [테스트 인쇄]: 프린터 확인.
- 인쇄 실패 시 원인(프린터 이름, 오프라인, 용지 등)을 알림창으로 표시. 한 대라도 출력되면 판매 기록.

■ 3. 메뉴 관리 (오른쪽 위, PIN 필요)
- 목록 선택 → 품목/가격 수정 → [수정 적용]. [추가]를 누르면 "새 메뉴" 줄이 생기고 바로 선택됩니다.
- [삭제], [▲ 위로]/[▼ 아래로]로 순서(=단축키 번호) 변경.
- 반드시 초록색 [저장 (적용)]을 눌러야 판매 화면에 반영됩니다. 저장하지 않은 변경이 있으면 창 제목에
  "● 저장 안 된 변경 있음" 이 표시되고, [닫기]/X 를 누르면 "저장할까요?" (예/아니오/취소) 를 묻습니다.
- 가격은 0보다 큰 숫자, 이름은 비울 수 없음. 저장 시 이전 메뉴는 menu.csv.bak_날짜시각 으로 보관.
- 지난 판매 기록은 메뉴를 바꿔도 그대로 남습니다.

■ 4. 설정 (오른쪽 위 [설정], PIN 필요)
- 가게 정보: 가게/행사 이름, 매대 이름, 영수증 하단 문구, 기기 ID(노트북 여러 대일 때 구분), 미리보기 켜기/끄기,
  백업 폴더([찾아보기…]로 USB 등 선택).
- 프린터: [＋ 프린터 추가] → 목록에서 Windows 에 설치된 프린터 선택 →
    방식: 영수증 프린터(ESC/POS) = SLK-TS100 등 감열 영수증 프린터
          일반/라벨 프린터(Windows 드라이버) = 라벨 프린터, 일반 프린터 등 모든 프린터
    레이아웃: 영수증 전체 / 라벨(크게 요약)
    용지 폭: 80mm(42칸), 58mm(32칸), 79mm 롤(연속 감열지, 길이 자동), 자동(드라이버 용지 크기)
    각 줄의 [테스트 인쇄]로 바로 확인. "사용" 체크 = 시작 시 출력 대상.
- 온라인 동기화(선택): 아래 7번 참고. 꺼두면 인터넷 없이 모든 기능 동작.
- [저장]을 누르면 즉시 적용 (재시작 불필요).

■ 5. 라벨 프린터 팁
- 프린터 이름이 목록에 없으면: Windows 설정 > 블루투스 및 장치 > 프린터 및 스캐너 에서 드라이버 설치 확인.
- 라벨 크기: 프린터 및 스캐너 > 해당 프린터 > 인쇄 기본 설정 > 용지(Stock)에서 실제 라벨 크기(예: 50x30mm)와
  간격(Gap) 또는 연속용지(Continuous) 선택. 프로그램은 용지 크기에 맞춰 글자 크기를 자동 조절합니다.
- 79mm 연속 롤지: 용지 폭을 "79mm 롤"로. 드라이버가 사용자 지정 크기를 무시하면 드라이버에서
  79 x 200mm 같은 사용자 용지를 만들어 선택하세요.

■ 6. 데이터 위치 / 백업
- 모든 데이터: %APPDATA%\FestivalReceipt  (탐색기 주소창에 그대로 입력)
  (포터블 모드: exe 옆 data 폴더)
  config.json(설정), menu.csv(메뉴), admin.json(PIN 해시), counter.json(영수증 번호),
  sales\날짜.csv (엑셀로 열림), sales\journal_날짜.jsonl, backup\, queue\(온라인 전송 대기), preview\
- 판매마다 즉시 디스크에 기록(정전 대비) + 백업 폴더에 한 번 더 기록. 영수증 번호는 매일 0001부터.
- 프로그램을 제거해도 판매 데이터는 지워지지 않습니다.
- 예전 버전(프로그램 폴더에 config.json 이 있던 버전)에서 업데이트하면 첫 실행 때 설정·메뉴·PIN·판매기록을
  새 데이터 폴더로 자동 복사합니다 (원본은 그대로).
- PIN 을 잊었을 때: 프로그램 종료 → %APPDATA%\FestivalReceipt\admin.json 삭제 → 다시 실행하여
  [메뉴 관리] 또는 [설정]을 열면 새 PIN 설정.

■ 7. Firebase 실시간 전송 (선택)
1. https://console.firebase.google.com → 프로젝트 추가.
2. Authentication > 로그인 방법 > "이메일/비밀번호" 사용 설정.
3. Authentication > 사용자 > 사용자 추가 (영수증 전용 이메일/강한 비밀번호) → "사용자 UID" 복사.
4. Firestore Database > 데이터베이스 만들기 (asia-northeast3 서울, 프로덕션 모드).
5. firestore.rules 의 REPLACE_WITH_UID 를 UID 로 바꿔 Firestore > 규칙 에 붙여넣고 [게시].
6. 프로젝트 설정 > 일반 > 웹 앱 추가 → apiKey, projectId 확인.
7. 프로그램 [설정] > 온라인 동기화 → 사용 체크, API 키, 프로젝트 ID, 이메일, 비밀번호 입력 → 저장.
   비밀번호는 Windows 자격 증명 관리자에 저장됩니다(불가능하면 데이터 폴더의 firebase_config.json).
- 하단 상태: "✔ 동기화 완료" / "전송 대기 N건" / "✖ 오프라인 - 대기 N건". 인터넷이 끊겨도 자동 재전송, 중복 없음.
- 관리자(서비스 계정) 키는 사용하지 않습니다. 노트북에 두지 마세요.
- 문서 형식: sales/{날짜-번호-기기ID} = {items:[{key,name,price,qty,amount}], total, date, time, receipt_no, device_id, uid}

=====================================================
■ 8. 판매자/개발자용: exe 와 설치 프로그램 만들기
준비: Windows 10/11, Python 3.11 이상 (python.org, "Add Python to PATH" 체크).
1) 소스 폴더에서 setup.bat 실행 (pywin32, keyring 설치).
2) (선택) run_tests.bat → ALL TESTS PASSED 확인. run.bat 으로 소스 그대로 실행 가능
   (run_debug.bat = 오류를 콘솔에 표시).
3) 아이콘: app.ico 를 원하는 아이콘으로 교체 (파일명 동일, 256x256 포함 권장).
4) build_exe.bat 실행 → dist\FestivalReceipt.exe (단일 파일, Python 없는 PC 에서도 실행).
5) 설치 프로그램: Inno Setup 6 설치 (https://jrsoftware.org/isinfo.php) → installer.iss 열기 →
   맨 위 AppName/AppVersion/AppPublisher 수정, [Setup] 의 AppId 를 Tools > Generate GUID 로 새로 만든 값으로
   한 번 교체(이후 버전에서는 유지) → Build > Compile → Output\FestivalReceipt_Setup_버전.exe
   (한국어 설치 화면, 바탕 화면/시작 메뉴 바로가기, 제거 프로그램 포함)
6) 배포 전 확인: 깨끗한 PC 에서 설치 → 처음 설정 마법사 → 테스트 인쇄 → 판매 → 매출 출력.
- 백신이 PyInstaller exe 를 오진하는 경우가 있습니다. 코드 서명 인증서로 서명하면 줄어듭니다
  (signtool sign /a /fd sha256 /tr http://timestamp.digicert.com /td sha256 dist\FestivalReceipt.exe).
- 소스 구성: receipt.py(메인), settings_ui.py(설정/마법사), appconfig.py(설정·경로), printers.py(프린터),
  firebase_sync.py(동기화), storage.py(안전 저장), menu.sample.csv(예시 메뉴), tests\(테스트)
- 개발 중 다른 데이터 폴더를 쓰려면 환경변수 FESTIVAL_RECEIPT_DATA 지정.

■ 9. GitHub 에 올리기
- .gitignore 가 판매 데이터, 설정, PIN, Firebase 설정/비밀번호, 빌드 결과를 제외합니다.
- git add 전 git status 로 firebase_config.json, config.json, admin.json, sales 등이 없는지 확인. 저장소는 Private 권장.

■ 10. GitHub 자동 빌드 / 배포
- .github/workflows/build.yml: push 할 때마다 Windows 에서 테스트 → exe → 설치 프로그램 → 포터블 zip 을 만들어
  Actions 탭의 Artifacts 로 올립니다.
- 배포: git tag v1.0.0 && git push origin v1.0.0 → Releases 에 FestivalReceipt-Setup.exe 와
  FestivalReceipt-Portable.zip 이 자동 게시됩니다 (버전 = 태그).
- installer.iss 의 AppId 는 절대 바꾸지 마세요 (업데이트 설치 인식용). 배포자 이름은 AppPublisher 에서 수정.
- 설명서 PDF 다시 만들기: docs\manual.html 수정 → 크롬에서 열어 인쇄 → PDF 로 저장 (A4, 머리글/바닥글 끔).
