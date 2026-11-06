# RFID · Vision Pick-and-Place

Python 3.11 이상. 기본 실행은 **시뮬레이션**이며 실제 로봇 드라이버는 포함하지 않습니다.

## 실행

```powershell
python -m pip install -r requirements.txt
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --workers 1
```

다른 터미널에서:

```powershell
python orchestrator.py --quantity 3
python -m unittest -v
```

시뮬레이션은 1번 태그의 빼빼로를 지정 수량만큼 피킹하며 큐를 소진한 뒤 홈으로 복귀합니다. API 최초 시작 시 `rfid.db`에 제공된 5종 데이터를 등록합니다. 기존 행은 덮어쓰지 않습니다. `RFID_DB` 환경 변수로 DB 경로를 변경할 수 있습니다.

## API

로컬 Swagger: http://127.0.0.1:8000/docs

| 경로 | 용도 |
|---|---|
| GET `/api/v1/tags/{uid}` | 제품 상세; 콜론 유무 허용, 4/7바이트 검증 |
| POST `/api/v1/scan-event` | `uid`, `quantity`(기본 1), `event_id`(선택)로 작업 생성 |
| GET `/api/v1/current-task` | FIFO 선두 작업과 YOLO 클래스/목적지; 비어 있으면 `task: null` |
| PATCH `/api/v1/tasks/{task_id}` | `completed`, `status`, 선택 `error` 보고 |
| WS `/ws` | 연결 시 snapshot, 이후 scan/task_progress 실시간 이벤트 |

같은 `event_id`와 같은 내용의 재전송은 기존 작업을 반환합니다. 동일 태그의 활성 작업이 있거나 같은 이벤트 ID에 다른 내용을 보내면 409입니다. 미등록 태그는 404, UID 형식 오류는 422입니다. UID는 대문자 연속 HEX로 저장하므로 선행 0을 보존합니다. 기본 키 인덱스 조회이며 SQLite B-tree의 복잡도는 O(log N)입니다.

WebSocket은 실시간 알림이며 영구 이벤트 로그가 아닙니다. 느린 클라이언트는 오래된 알림이 생략될 수 있으므로 REST로 현재 상태를 조회합니다. 인메모리 방송이므로 서버는 **단일 worker**, 로봇 컨트롤러는 **단일 인스턴스**로 운영합니다. 인증이 없는 로컬 개발 API이므로 외부 공개 전 인증과 접근 제어가 필요합니다.

## 실제 로봇 및 비전 연결

`Orchestrator(api, robot, scanner, vision)`에 현장 어댑터를 전달합니다.

- `robot.pre_scan()`: 정의된 리딩 포즈까지 이동 완료 대기.
- `robot.approach(pose)`, `grip()`, `retract()`: 접근 경로 실행, 파지 센서 확인, 안전 리프트.
- `robot.place(box_id)`: 보정된 목적지 접근, 적치, 릴리스 확인 및 퇴피 완료 대기.
- `robot.home()`, `stop()`: 안전 홈 및 즉시 정지 요청. 각 메서드는 실패 시 예외를 발생시켜야 합니다.
- `wait_trigger()`: 작업자/진입 센서 신호를 기다리는 블로킹 콜백.

오류 시 ERROR 및 정지를 요청하고 작업을 DEFECTIVE로 기록합니다. 오류 상황에서는 자동 홈 이동을 하지 않습니다. 중단된 PICKING 작업은 실제 적치 수량을 확인한 뒤 운영자가 정리해야 하며 자동 재개하지 않습니다. 실제 적치와 DB 기록은 원자적일 수 없으므로 통신/전원 장애 후 현물 대조가 필요합니다.

`YoloVision(weights, frame_provider, depth_provider, calibration)`는 학습된 YOLOv8 모델의 클래스 이름과 ID가 모두 일치하는 최고 신뢰도 후보를 선택합니다. 매 피킹마다 새 프레임을 추론합니다. 기본 사전학습 모델에는 이 프로젝트의 커스텀 5개 라벨이 없으므로 전용 학습 가중치가 필요합니다. bbox 중심은 기하학적 후보이며 물체별 파지 가능성은 현장에서 검증해야 합니다.

`Calibration(K, T_base_camera, workspace_min, workspace_max, rpy)`는 고정 상단 카메라 기준입니다. 깊이는 카메라 optical Z의 **미터**, 로봇 위치도 **미터**, RPY는 **라디안**입니다. 입력 프레임은 K에 맞게 왜곡 보정되어야 합니다. RGB-D 깊이는 RGB와 정렬된 유효 깊이를 전달합니다. RGB 단독 사용 시 측정된 작업 평면과 광선 교차를 별도로 구현해 optical Z를 제공해야 하며 임의 상수를 실기에 사용하지 않습니다. 카메라가 로봇에 부착되면 현재 TCP 변환까지 합성해야 합니다.

관절 제한, 충돌 검사, 안전 접근 높이, 속도 제한, 그리퍼 센서, E-stop/안전 PLC는 실제 로봇 어댑터와 장비에서 구현/검증해야 합니다. Python 상태 머신은 인증된 안전 제어기가 아닙니다.

## 데이터 모델과 범위

요청한 제품 테이블과 별도의 `tasks` 수량/이벤트/진행 테이블을 사용합니다. UID 재기록 가능 태그는 인증 수단이 아니며 현장 UID 중복을 관리해야 합니다. SKU UNIQUE는 요청 스키마를 따르므로 한 SKU에 여러 물리 태그를 등록하려면 제품과 태그 테이블 분리가 필요합니다. 소비기한은 제공된 메타데이터로 저장하며 자동 출고 차단 정책은 적용하지 않습니다. 현재 구현은 SQLite입니다.

## 저장된 제품 정보 조회

DB Browser for SQLite에서 `rfid.db`의 `product_tag_mappings`를 수정한 뒤 적용과 변경사항 저장하기를 눌러 저장합니다. `database.py`의 SEEDS는 새 DB의 초기값이므로 기존 DB를 덮어쓰지 않습니다. UID를 읽은 후 `GET /api/v1/tags/{uid}`로 현재 저장값을 조회합니다. 이 조회는 작업을 생성하지 않습니다. `--read-only`는 UID만 출력하며 기본 스캔 명령은 작업을 생성하므로 활성 작업이 있으면 409를 반환합니다.
