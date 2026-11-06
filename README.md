<p align="center">
  <img src="https://raw.githubusercontent.com/vision-picking-robot/.github/main/profile/assets/banner.svg" alt="Vision Picking Robot" width="100%" />
</p>

**RFID Pick-and-Place**

RFID 태그 UID로 제품과 목적지 상자를 조회하고, 비전 검출과 로봇팔 피킹 작업으로 연결하는 프로젝트입니다.

**구성**

| 모듈 | 역할 |
|---|---|
| `rfid_scanner.py` | 태그 식별값 수집 |
| `database.py` | SQLite 제품 매핑 및 작업 큐 |
| `api_server.py` | 제품 조회 REST API와 WebSocket 알림 |
| `vision.py` | YOLO 클래스 매칭과 카메라 좌표 변환 |
| `orchestrator.py` | 피킹 상태 머신 및 동작 시뮬레이션 |

**시작하기**

코드는 [`robot_rfid/`](robot_rfid/)에 있습니다. VS Code에서 이 폴더를 열고 Python 환경을 준비하세요.

```powershell
cd robot_rfid
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-hardware.txt
```

태그 UID 읽기:

```powershell
.\.venv\Scripts\python.exe rfid_scanner.py --read-only --timeout 60
```

API 서버 실행:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --workers 1
```

**[상세 설치·실행 안내](robot_rfid/README.md)** · **[소스 코드](robot_rfid/)** · **[이슈](https://github.com/vision-picking-robot/rfid-pick-and-place/issues)**

**확인된 범위**

태그 식별값을 통한 제품 정보 조회를 확인했습니다. 실제 로봇 드라이버, 학습 가중치와 현장 캘리브레이션은 별도 연결이 필요합니다.

가상환경 및 실행 DB는 저장소에 포함하지 않습니다.
