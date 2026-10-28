# Jenkins 설치 및 GitHub 연결

## 현재 범위

RDS PostgreSQL은 기존 환경을 유지합니다. 이 구성은 GitHub checkout, 잠금 파일 기준 의존성 설치, pytest 실행만 수행합니다. 현재 backend에는 앱과 테스트가 없어 테스트 단계가 UNSTABLE로 끝나는 것이 예상 결과입니다. 성공한 테스트나 배포로 간주하지 않습니다.

`database/schema.sql`은 신규 DB 전용이므로 기존 RDS에 실행하지 않습니다. DB 비밀번호와 운영 API 키를 이 CI 작업에 등록하지 마세요. TESTING 환경변수만으로 DB 접속이 차단되지는 않습니다. 팀원이 테스트를 추가할 때 DB 의존성과 앱 시작 시 연결을 실제로 격리해야 합니다.

## 1. 설치 환경

서버가 아직 없으면 [EC2 준비 안내](jenkins-ec2.md)부터 진행합니다.

Docker Engine + Compose v2가 설치된 Linux 서버 또는 Linux containers 모드의 Docker Desktop이 필요합니다. RDS에는 Jenkins를 설치할 수 없습니다. 원격 설치 서버와 SSH 접속 정보는 아직 미정입니다. 새 EC2 인스턴스나 AWS 리소스를 자동 생성하는 설정은 없습니다.

저장소 루트에서 실행합니다.

Linux 서버에서 Docker 그룹을 설정하지 않았다면 아래 docker 명령 앞에 `sudo`를 붙입니다.

```bash
docker compose -f infra/jenkins/compose.yaml up -d jenkins
```

로컬 PC에서는 http://localhost:8080 으로 접속합니다. 원격 서버에서는 본인 PC에서 SSH 터널을 연 뒤 같은 주소로 접속합니다. 아래 값은 실제 SSH 사용자와 서버 주소로 바꿉니다.

```bash
ssh -L 8080:127.0.0.1:8080 USER@SERVER
```

초기 관리자 암호는 본인 터미널에서 확인하고 설치 화면에 직접 입력합니다. 이 출력은 채팅이나 Git에 올리지 않습니다.

```bash
docker compose -f infra/jenkins/compose.yaml exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

추천 플러그인을 설치하고 관리자 계정을 생성합니다. Pipeline, Git, JUnit, Timestamper 플러그인이 필요합니다. 컨트롤러 및 에이전트 이미지는 설치 시점의 태그를 사용하므로 운영 도입 때 검증한 digest로 고정하고 업데이트를 관리하세요.

## 2. 빌드 에이전트 등록

Manage Jenkins → Nodes에서 Built-In Node의 executors를 0으로 설정합니다.

New Node → 이름 `icn-ci` → Permanent Agent를 생성합니다.

- executors: 1
- Remote root directory: `/home/jenkins/agent`
- Labels: `icn-ci`
- Usage: Only build jobs with label expressions matching this node
- Launch method: Launch agent by connecting it to the controller
- WebSocket 사용

저장 후 에이전트 연결 안내의 secret 값을 로컬 `infra/jenkins/.env`에 아래 형식으로 저장합니다. 실제 토큰은 Git에 커밋하지 않습니다. 이 파일은 이미 .gitignore에서 제외됩니다.

```text
JENKINS_AGENT_TOKEN=<Jenkins 화면에서 확인한 에이전트 연결 토큰>
```

```bash
docker compose -f infra/jenkins/compose.yaml --profile agent up -d --build
```

Nodes 화면에서 icn-ci가 online인지 확인합니다. 빌드는 별도 에이전트에서 실행하며 Docker 소켓이나 Jenkins 홈 디렉터리를 공유하지 않습니다. 이 에이전트에는 RDS 접속 정보를 주입하지 않습니다.

## 3. GitHub Pipeline 작업

New Item → `icn-dashboard-ci` → Pipeline:

| 설정 | 값 |
|---|---|
| Definition | Pipeline script from SCM |
| SCM | Git |
| Repository URL | https://github.com/donacana/icn-my-station-db.git |
| Credentials | 공개 저장소 읽기는 비워 둠 |
| Branch Specifier | */main |
| Script Path | Jenkinsfile |

Jenkinsfile이 main에 병합되기 전 시험할 때만 Branch Specifier를 `*/feature/jenkins-setup`으로 지정합니다. Save → Build Now를 실행합니다. 첫 실행 후 Jenkinsfile의 5분 주기 Poll SCM 설정이 적용되어 변경된 커밋이 있을 때 빌드합니다. 현재 구성은 외부에서 8080 포트에 접근할 필요가 없습니다.

실제 테스트가 추가되면 테스트 통과 시 SUCCESS, 실패 시 FAILURE입니다. 테스트가 0개이면 UNSTABLE이며 자동 배포는 없습니다. pytest XML 결과는 Jenkins에 수집하고 작업 디렉터리는 실행 후 정리합니다.

## 4. 나중에 추가할 배포

앱 실행 코드, 빌드 명령, 배포 서버, RDS 엔진 버전 및 현재 적용된 스키마를 확인한 뒤 별도 배포 작업을 추가합니다. CI 작업과 배포 권한을 분리하고, 신뢰된 main 변경만 배포하도록 구성합니다.

기존 RDS의 스키마와 초기 SQL을 대조해 기준 버전을 확정해야 합니다. 이후 버전·체크섬 이력, 동시 실행 잠금, 가능한 범위의 트랜잭션, 백업 및 실패 복구 절차를 갖춘 증분 마이그레이션을 적용합니다. 파일명 기록만으로 데이터 보존이 보장되지는 않습니다.

즉시 Push 감지가 필요하면 HTTPS Jenkins 주소와 Webhook 검증을 준비한 후 GitHub Webhook을 연결합니다. 현재는 Poll SCM을 사용하므로 Webhook 미등록이 오류가 아닙니다.

## 운영 주의

- 중지: `docker compose -f infra/jenkins/compose.yaml --profile agent stop`
- Jenkins 설정은 jenkins_home 볼륨에 보존됩니다. `down -v`는 사용하지 않습니다.
- Jenkins 관리자 계정, 에이전트 토큰, RDS 비밀번호는 서로 다른 용도입니다.
- 공개 저장소의 임의 PR에 운영 배포 권한을 부여하지 않습니다.

## 공식 문서

- https://www.jenkins.io/doc/book/installing/docker/
- https://www.jenkins.io/doc/book/pipeline/getting-started/
- https://www.jenkins.io/doc/book/security/controller-isolation/
