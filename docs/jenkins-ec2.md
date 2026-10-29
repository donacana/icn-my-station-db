# Jenkins용 EC2 준비

현재 서버 없음. 기존 RDS는 그대로 두고 Jenkins 전용 EC2를 새로 준비합니다. EC2, EBS, 공인 IPv4에는 요금이 발생할 수 있으므로 실행 전 AWS 콘솔의 비용 안내를 확인하세요. 이 문서나 저장소는 AWS 리소스를 자동 생성하지 않습니다.

## AWS 콘솔 선택값

EC2 → 인스턴스 → 인스턴스 시작에서 다음을 선택합니다.

| 항목 | 권장 시작값 |
|---|---|
| 리전 | 기존 RDS와 같은 리전 |
| 이름 | icn-jenkins |
| AMI | Canonical Ubuntu Server 24.04 LTS, 64-bit x86 |
| 인스턴스 유형 | t3.medium (2 vCPU, 4 GiB), 작은 팀 CI 시작용 |
| 키 페어 | 본인이 보관할 새 RSA .pem 키 또는 기존 키 |
| VPC | 가능하면 기존 RDS와 같은 VPC |
| 서브넷 | 인터넷 게이트웨이 경로가 있는 퍼블릭 서브넷 |
| 공인 IP 자동 할당 | 활성화 (이번 SSH 접속 방식 기준) |
| 보안 그룹 | 새 그룹 icn-jenkins-sg |
| 인바운드 | SSH TCP 22, 소스 My IP만 허용 |
| 스토리지 | 암호화된 gp3 30 GiB, 사용량에 따라 확장 |
| IAM 역할 | 현재 CI에는 AWS API 권한 불필요 |

Jenkins 권장은 소규모 팀 기준 RAM 4GB 이상입니다. 컨트롤러와 에이전트를 함께 사용하므로 빌드가 커지면 메모리를 늘리거나 에이전트를 분리합니다.

이 단계에서 8080, 50000, 5432 인바운드를 추가하지 않습니다. RDS 보안 그룹도 수정하지 않습니다. 아웃바운드는 GitHub, 컨테이너 레지스트리, Python 패키지 다운로드를 위한 DNS/HTTPS 등이 가능해야 합니다. 기존 VPC가 프라이빗 서브넷만 있다면 공인 IP만 켜도 연결되지 않으므로 네트워크 구성을 먼저 확인하세요.

## 접속

인스턴스가 Running이고 상태 검사를 통과한 후 공인 IPv4를 확인합니다. Windows PowerShell에서 실제 키 경로와 IP로 바꿔 실행합니다.

```powershell
ssh -i "C:\Users\KW\Downloads\icn-jenkins.pem" ubuntu@EC2_PUBLIC_IP
```

호스트 키 지문은 EC2에서 확인한 값과 비교합니다. .pem 파일 내용은 채팅이나 Git에 올리지 않습니다. 다음 작업을 맡길 때는 인스턴스 ID, 공인 IP, 키 파일의 로컬 경로만 전달합니다.

## Docker와 저장소 준비

새 Ubuntu 서버에서 [Docker 공식 Ubuntu 설치 안내](https://docs.docker.com/engine/install/ubuntu/#install-using-the-apt-repository)의 apt 저장소 설치 절차를 따릅니다. 설치 패키지는 docker-ce, docker-ce-cli, containerd.io, docker-buildx-plugin, docker-compose-plugin입니다.

```bash
sudo apt-get update
sudo apt-get install -y git
sudo docker version
sudo docker compose version
git clone --branch feature/jenkins-setup https://github.com/donacana/icn-my-station-db.git
cd icn-my-station-db
sudo docker compose -f infra/jenkins/compose.yaml up -d jenkins
```

위 clone은 PR 검토용 브랜치 기준입니다. PR 병합 후에는 main을 사용합니다.

본인 PC의 별도 PowerShell 창에서 터널을 엽니다.

```powershell
ssh -N -i "C:\Users\KW\Downloads\icn-jenkins.pem" -L 8080:127.0.0.1:8080 ubuntu@EC2_PUBLIC_IP
```

터널을 켜 둔 상태에서 http://localhost:8080 을 열고 [설치 및 Git 연결 안내](jenkins-setup.md)의 초기 관리자 설정, 에이전트 등록, Pipeline 작업 생성 순서로 진행합니다.

## 확인된 범위

Compose 구문 검증과 Windows Python 3.12 환경에서 uv 잠금 파일 설치를 확인했습니다. pytest는 테스트 0개로 exit 5를 반환했습니다. 설치 서버가 없고 로컬 Docker 엔진도 실행되지 않아 Linux 이미지 빌드, Jenkins 실행, Pipeline 실행은 아직 검증하지 못했습니다.

## 공식 자료

- https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html
- https://www.jenkins.io/doc/book/installing/linux/
- https://docs.docker.com/engine/install/ubuntu/
