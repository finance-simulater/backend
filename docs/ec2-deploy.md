# EC2 Deploy

EC2에서 Docker Compose로 FastAPI와 Nginx를 실행한다.

## 1. 저장소 받기

```bash
git clone https://github.com/finance-simulater/backend.git
cd backend
```

이미 받은 경우:

```bash
cd backend
git pull origin main
```

## 2. 운영 환경변수 작성

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

현재 RDS가 아직 없으면 운영 DB 연결은 나중에 한다. RDS 생성 전에는 컨테이너가 DB 연결을 요구하는 API에서 실패할 수 있다.

## 3. 실행

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

로그 확인:

```bash
docker compose -f docker-compose.prod.yml logs -f fastapi
docker compose -f docker-compose.prod.yml logs -f nginx
```

## 4. 접속 확인

```bash
curl http://localhost/docs
```

브라우저:

```text
http://<EC2_PUBLIC_IP>/docs
http://api.<your-domain>/docs
```

## 5. HTTPS 설정

도메인이 EC2 Elastic IP를 바라보고 있고, AWS 보안그룹에서 80/443이 열려 있어야 한다.

EC2의 `/home/ubuntu/backend/.env.prod`에 운영 도메인과 Let's Encrypt 알림 이메일을 추가한다.

```text
API_DOMAIN=api.<your-domain>
LETSENCRYPT_EMAIL=<your-email>
```

처음 한 번만 인증서를 발급한다.

```bash
cd /home/ubuntu/backend
chmod +x scripts/init-letsencrypt.sh scripts/renew-letsencrypt.sh
./scripts/init-letsencrypt.sh
docker compose -f docker-compose.prod.yml up -d
curl -I https://api.<your-domain>/docs
```

인증서 갱신은 필요할 때 아래 명령으로 실행한다.

```bash
cd /home/ubuntu/backend
./scripts/renew-letsencrypt.sh
```

## 6. 중지

```bash
docker compose -f docker-compose.prod.yml down
```

## 7. GitHub Actions 자동 배포

EC2를 GitHub Actions self-hosted runner로 등록한다.

GitHub 저장소의 `Settings -> Actions -> Runners -> New self-hosted runner`로 들어가서 Linux x64 명령을 EC2에서 실행한다.

EC2에서 runner 등록 후 실행:

```bash
cd ~/actions-runner
./run.sh
```

백그라운드 서비스로 등록하려면 GitHub가 안내하는 `svc.sh` 명령을 사용한다.

GitHub 저장소의 `Settings -> Secrets and variables -> Actions`에 아래 repository secret을 등록한다.

```text
EC2_APP_DIR=/home/ubuntu/backend
```

이후 `main` 브랜치에 push하면 GitHub Actions가 EC2 안에서 repository 파일을 동기화한 뒤 아래 작업을 자동으로 수행한다.

```bash
docker compose -f docker-compose.prod.yml up -d --build
curl -fsS http://localhost/docs
```

EC2의 `.env.prod`는 동기화 대상에서 제외되어 서버에 있는 운영 환경변수가 유지된다.
