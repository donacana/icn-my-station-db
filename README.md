# icn-my-station-db

인천공항 대시보드의 프론트엔드, 백엔드, 데이터 수집 및 데이터베이스 작업을 팀 단위로 관리하기 위한 저장소입니다.

## 폴더 구성

```text
icn-my-station-db/
├── frontend/     # 대시보드 화면과 사용자 인터페이스
├── backend/      # 서버 API와 업무 로직
├── collection/   # 데이터 수집과 전처리
├── database/     # ERD, SQL 스키마와 마이그레이션
├── README.md     # 프로젝트 소개와 협업 안내
├── main.py       # 기존 PyCharm 샘플 스크립트 (원본 보존)
└── .gitignore    # 비밀정보 및 로컬 생성 파일 제외 규칙
```

`database/schema.sql`은 신규 데이터베이스 생성용입니다. 이미 운영 중인 RDS에는 재실행하지 않습니다.

Jenkins 설치 구성은 `infra/jenkins/`, 파이프라인은 루트 `Jenkinsfile`에 있습니다. [Jenkins 설치 및 연결 안내](docs/jenkins-setup.md)에 따라 설정합니다. 현재 파이프라인은 CI 전용이며 RDS 변경과 애플리케이션 배포는 실행하지 않습니다.

## 내려받고 작업 시작하기

Git을 설치하고 GitHub 비공개 저장소 접근 권한을 받은 뒤 다음 명령을 실행합니다.

```bash
git clone https://github.com/donacana/icn-my-station-db.git
cd icn-my-station-db
git switch main
git pull --ff-only origin main
git switch -c feature/describe-your-change
```

현재는 실행 가능한 데이터베이스나 접속 설정이 없으므로 별도의 설치 또는 마이그레이션 명령은 없습니다. 데이터베이스 종류와 스키마가 정해지면 실행 방법을 추가합니다.

변경 사항을 검토하고 필요한 파일만 커밋한 뒤 작업 브랜치를 올려 Pull Request를 생성합니다.

```bash
git diff
git status --short
git add <검토한 파일 경로>
git diff --cached
git commit -m "docs: describe database changes"
git push -u origin feature/describe-your-change
```

## 비밀정보 관리

- 실제 접속 문자열, API 키, 비밀번호, 토큰, 인증서 개인키는 커밋하지 않습니다.
- 로컬 환경변수는 `.env` 또는 `.env.*` 파일에 보관합니다. 공유할 설정 설명에는 실제 값 대신 자리표시자를 사용합니다.
- SQL·ERD·문서에도 비밀번호, 운영 데이터 또는 개인정보를 넣지 않습니다.
- `.gitignore`는 파일 이름과 경로만 검사하므로 모든 비밀정보를 자동으로 탐지하지 않습니다. 커밋 전에 변경 내용을 직접 확인합니다.
- 이미 추적 중인 파일은 `.gitignore`만으로 제외되지 않습니다. 비밀정보가 커밋되었다면 해당 키를 폐기·재발급하고 팀과 기록 정리 방법을 협의합니다.
