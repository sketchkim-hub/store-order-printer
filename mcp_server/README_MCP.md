# 매장용 주문 프린터 – 읽기 전용 MCP 서버

AI 비서(Claude Desktop, Cursor 등)가 영수증 프로그램의 **매출과 메뉴를 조회만** 할 수 있게 해 주는 작은 서버입니다.
영수증 프로그램 자체는 전혀 바뀌지 않습니다.

| 도구 | 설명 |
|---|---|
| `get_today_sales` | 오늘 매출: 총액, 주문(영수증) 수, 판매 수량, 품목별 수량·금액 |
| `get_item_sales(start_date, end_date)` | 기간(YYYY-MM-DD, 양 끝 포함, 최대 366일) 품목별 수량·금액 + 일별 총액 |
| `get_menu` | 메뉴: 번호(단축키), 품목, 가격 |

- 여러 품목 주문과 예전(1품목) 판매 기록을 모두 집계합니다. CSV 가 없으면 판매 저널로 대신 읽습니다.
- **읽기 전용**: 인쇄, 메뉴 수정, 파일 쓰기 기능이 없습니다. `queue`, `counter.json` 은 열지도 않습니다.

## 1. 설치 (Windows)

1. Python 3.10 이상 설치 (python.org, "Add python.exe to PATH" 체크).
2. 소스 폴더(`store-order-printer`)를 내려받아 원하는 위치에 둡니다. 예: `C:\store-order-printer`
3. 명령 프롬프트에서:
   ```
   cd C:\store-order-printer\mcp_server
   py -m pip install -r requirements.txt
   ```
4. 확인 (선택): `py tests\test_reader.py` → `READER TESTS OK`, `py tests\test_e2e.py` → `E2E TESTS OK`

> `mcp_server` 폴더는 반드시 소스 폴더 안에 두세요 (상위 폴더의 `storage.py` 를 같이 사용합니다).

## 2. 데이터 폴더

기본: `%APPDATA%\FestivalReceipt` (설치형 프로그램의 데이터 폴더).
**포터블**로 쓰거나 다른 위치라면 환경변수 `FESTIVAL_RECEIPT_DATA_DIR` 에 그 폴더를 지정하세요
(예: `D:\FestivalReceipt\data`). 앱의 `FESTIVAL_RECEIPT_DATA` 도 인식합니다.

## 3. Claude Desktop 설정

파일: `%APPDATA%\Claude\claude_desktop_config.json` (Claude Desktop → 설정 → 개발자 → 구성 편집)

py 런처 사용:
```json
{
  "mcpServers": {
    "store-order-printer": {
      "command": "py",
      "args": ["C:\\store-order-printer\\mcp_server\\server.py"]
    }
  }
}
```

python 경로 직접 지정 + 포터블 데이터 폴더:
```json
{
  "mcpServers": {
    "store-order-printer": {
      "command": "C:\\Users\\사용자\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
      "args": ["C:\\store-order-printer\\mcp_server\\server.py"],
      "env": { "FESTIVAL_RECEIPT_DATA_DIR": "D:\\FestivalReceipt\\data" }
    }
  }
}
```
저장 후 Claude Desktop 을 완전히 종료(트레이 아이콘 → 종료)했다가 다시 실행하세요.
python 경로는 명령 프롬프트에서 `where python` 또는 `py -c "import sys; print(sys.executable)"` 로 확인합니다.

## 4. Cursor 설정

프로젝트의 `.cursor/mcp.json` (모든 프로젝트에 쓰려면 `%USERPROFILE%\.cursor\mcp.json`):
```json
{
  "mcpServers": {
    "store-order-printer": {
      "command": "py",
      "args": ["C:\\store-order-printer\\mcp_server\\server.py"],
      "env": { "FESTIVAL_RECEIPT_DATA_DIR": "C:\\Users\\사용자\\AppData\\Roaming\\FestivalReceipt" }
    }
  }
}
```
Cursor 설정 → MCP 에서 `store-order-printer` 가 초록색(연결됨)인지 확인하세요.

## 5. 이렇게 물어보세요

- "오늘 매출 얼마야?"
- "오늘 제일 많이 팔린 메뉴 3개 알려줘"
- "이번 주(10월 7일~13일) 품목별 판매량 보여줘"
- "10월 매출을 날짜별로 정리해줘"
- "어묵은 이번 달에 몇 개 팔렸어?"
- "지금 메뉴판 가격 알려줘"

## 6. 보안 안내

- **로컬 전용**: stdio 방식이라 이 컴퓨터의 AI 앱만 실행합니다. 네트워크 포트를 열지 않습니다.
- **읽기 전용**: 판매 기록·메뉴·설정을 바꾸거나 인쇄할 수 없습니다. 데이터 폴더의 파일은 읽기 모드로만 엽니다.
- **AI 회사로 전송**: AI 에게 매출을 물으면 조회 결과(품목, 수량, 금액, 날짜)가 그 AI 서비스(예: Anthropic, Cursor 가
  사용하는 모델 제공사)로 전송됩니다. 민감하다고 생각되면 연결하지 마세요. 판매 데이터에는 고객 개인정보가 없습니다.
- PIN(admin.json), Firebase 비밀번호 등은 읽지 않습니다.

## 7. 파일

| 파일 | 설명 |
|---|---|
| `server.py` | MCP 서버 (FastMCP, stdio) |
| `sales_reader.py` | 데이터 폴더 찾기·판매/메뉴 읽기·집계 (읽기 전용) |
| `requirements.txt` | `mcp>=1.2,<2` |
| `tests/sampledata.py` | 테스트용 임시 데이터 생성 |
| `tests/test_reader.py` | 집계·날짜 검증·읽기 전용 확인 |
| `tests/test_e2e.py` | 실제 서버를 stdio 로 띄워 MCP 클라이언트로 도구 호출 |
