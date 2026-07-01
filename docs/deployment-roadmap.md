# Deployment Roadmap

이 문서는 `Downloads/진행순서모음` 이미지 내용을 기준으로 백엔드 배포 흐름을 정리한 작업 순서다.

## 현재 완료된 상태

- FastAPI 도메인 구조 정리: `app/api/v1/{auth,user,loan}`.
- 로컬 개발용 Docker Compose: MySQL + Redis.
- `.env.example` 제공, 실제 `.env`는 Git 제외.
- SQLAlchemy ORM 모델 작성.
- Alembic 마이그레이션 생성 및 로컬 MySQL 적용.

## 전체 방향

로컬에서는 Docker Compose로 MySQL과 Redis를 띄워 개발한다.
운영에서는 EC2에 FastAPI와 Nginx를 컨테이너로 올리고, DB는 RDS MySQL로 분리한다.
Redis는 초반에는 EC2/Docker Redis 또는 로컬 Redis로 검증하고, 운영 단계에서는 ElastiCache Redis로 분리한다.
AWS 리소스는 처음에는 콘솔로 흐름을 확인하고, 최종적으로 Terraform 코드로 재현 가능하게 관리한다.

## 진행 순서

1. 설정 관리 정리
   - `app/core/config.py`에서 `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `DEBUG`, CORS origin을 관리한다.
   - `app/database.py`, Alembic, Redis 클라이언트가 같은 설정 객체를 사용하게 맞춘다.

2. Redis와 인증 유틸 추가
   - Redis 클라이언트를 추가한다.
   - refresh token 저장/조회/삭제 함수를 만든다.
   - JWT 생성/검증, 비밀번호 해시 유틸을 `app/core/security.py`에 정리한다.

3. 공통 API 품질 정리
   - CORS 설정을 추가한다.
   - 공통 예외 클래스를 정리한다.
   - 필요하면 응답 포맷을 통일한다.

4. 운영 Docker 배포 파일 작성
   - `Dockerfile`을 추가한다.
   - `nginx/nginx.conf`를 추가한다.
   - `docker-compose.prod.yml`을 추가한다.
   - 운영에서는 FastAPI의 8000 포트를 직접 열지 않고 Nginx가 프록시한다.

5. AWS 콘솔로 Day5 흐름 확인
   - EC2 Ubuntu 인스턴스를 만든다.
   - 보안그룹은 SSH 22는 내 IP만, HTTP 80/HTTPS 443은 공개한다.
   - Docker, Git, Docker Compose를 설치한다.
   - Gabia 등에서 도메인을 구매하고 Cloudflare에 연결한다.
   - Cloudflare DNS에 `api` A 레코드를 EC2 퍼블릭 IP로 연결한다.

6. Terraform 인프라 코드 작성
   - `infra/main.tf`, `infra/variables.tf`, `infra/outputs.tf`, `infra/terraform.tfvars.example`을 작성한다.
   - EC2, 보안그룹, Elastic IP부터 코드화한다.
   - RDS와 Redis는 이후 단계에서 추가한다.
   - `terraform.tfvars`, `terraform.tfstate`, `.pem`은 절대 Git에 올리지 않는다.

7. RDS MySQL 연결
   - 학습 단계에서는 퍼블릭 RDS로 로컬 접속까지 확인할 수 있다.
   - 실제 운영 구조에서는 RDS를 private subnet에 두고 EC2 보안그룹에서만 3306을 허용한다.
   - `.env.prod`의 `DATABASE_URL`을 RDS 엔드포인트로 바꾼다.
   - Alembic으로 RDS에 마이그레이션을 적용한다.

8. Redis 운영 구성
   - 초반에는 Docker Redis로 검증한다.
   - 운영 전환 시 ElastiCache Redis를 Terraform으로 생성한다.
   - FastAPI의 `REDIS_URL`만 교체해서 코드 변경 없이 연결한다.

9. GitHub Actions 배포
   - push 시 테스트를 실행한다.
   - 테스트 성공 후 EC2에 SSH 접속한다.
   - `git pull`, Alembic 마이그레이션, `docker compose -f docker-compose.prod.yml up -d --build`를 실행한다.
   - GitHub Secrets에 `EC2_HOST`, `EC2_SSH_KEY`, `SECRET_KEY`, 테스트용 DB URL 등을 등록한다.

10. 도메인 최종 연결
    - Cloudflare DNS에서 `api.example.com`을 EC2 Elastic IP로 연결한다.
    - Nginx `server_name`을 실제 API 도메인으로 설정한다.
    - `https://api.example.com/docs` 접속을 확인한다.

## 사용자가 직접 해야 할 일

- AWS 계정 준비 및 과금 알림 설정.
- AWS IAM Access Key 발급 후 로컬에서 `aws configure`.
- EC2 키페어 생성 및 `.pem` 파일 안전하게 보관.
- 도메인 구매.
- Cloudflare에 도메인 추가 및 Gabia 네임서버 변경.
- Terraform 실행 전 `terraform.tfvars`에 실제 값 입력.
- GitHub Secrets에 운영 비밀값 등록.

## Codex가 작성할 코드

- 설정 관리 코드.
- Redis/JWT/보안 유틸 코드.
- Dockerfile, Nginx 설정, 운영 Compose 파일.
- Terraform 인프라 코드.
- GitHub Actions 배포 워크플로우.
- 필요한 README/운영 문서.
