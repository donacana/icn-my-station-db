# 백엔드 규칙

## 구조
- app/main.py     : FastAPI 앱 생성, CORS, 라우터 등록
- app/schemas.py  : 응답 모델. docs/api-contract.md와 1:1로 일치해야 한다.
- app/services/   : 데이터 조회·계산 로직. mock → DB 쿼리 교체는 이 안에서만 한다.
- app/routers/    : REST 엔드포인트. 로직 없이 services 호출만 한다.
- app/ws.py       : WebSocket /ws/live 실시간 푸시
- tests/          : pytest 테스트
- scripts/        : 보조 스크립트 (openapi.json 내보내기 등)

## 규칙
- 모든 응답 모델은 CamelModel(alias_generator=to_camel, populate_by_name=True)을 상속한다.
- datetime은 항상 timezone-aware(KST)로 만든다.
- 외부 공공 API를 호출하는 코드를 backend에 만들지 않는다. 데이터는 DB에서만 읽는다.
- DB가 준비되기 전에는 services에서 mock 데이터를 반환하되, 응답 모양은 계약과 완전히 같게 한다.
- 비밀값은 .env에서 환경변수로 읽는다 (pydantic-settings 사용).
- 운항 상태 매핑과 지연 기준(15분), 운항 여건 점수 공식, 혼잡 단계 기준값은 한 곳(app/core/rules.py)에 상수로 둔다.

## 엔드포인트 추가 순서
1. docs/api-contract.md에 필드가 정의되어 있는지 확인한다. 없으면 먼저 계약 문서에 추가 제안한다.
2. app/schemas.py에 응답 모델 작성
3. app/services/에 조회 함수 작성
4. app/routers/에 엔드포인트 추가 (response_model 지정)
5. tests/에 응답 키가 계약 문서와 일치하는지 확인하는 테스트 추가
6. uv run pytest 통과 확인
7. scripts/export_openapi.py로 docs/openapi.json 갱신

## 명령어 (backend 폴더에서 실행)
- 의존성 설치: uv sync
- 서버 실행: uv run uvicorn app.main:app --reload
- 테스트: uv run pytest
- 린트/포맷: uv run ruff format . && uv run ruff check --fix .
- openapi 내보내기: uv run python scripts/export_openapi.py