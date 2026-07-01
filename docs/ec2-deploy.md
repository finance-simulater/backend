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

## 5. 중지

```bash
docker compose -f docker-compose.prod.yml down
```

## 6. GitHub Actions 자동 배포

GitHub 저장소의 `Settings -> Secrets and variables -> Actions`에 아래 repository secrets를 등록한다.

```text
EC2_HOST=EC2 Elastic IP 또는 api 도메인
EC2_USERNAME=ubuntu
EC2_SSH_KEY=.pem 파일 내용 전체
EC2_APP_DIR=/home/ubuntu/backend
```

`EC2_SSH_KEY`는 파일 경로가 아니라 private key 파일의 내용이다.

Mac에서 복사할 때:

```bash
cat ~/.ssh/study-ec2.pem
```

출력되는 아래 전체 내용을 GitHub secret 값으로 넣는다.

```text
-----BEGIN ... PRIVATE KEY-----
...
-----END ... PRIVATE KEY-----
```

이후 `main` 브랜치에 push하면 GitHub Actions가 repository 파일을 EC2로 업로드한 뒤 아래 작업을 자동으로 수행한다.

```bash
docker compose -f docker-compose.prod.yml up -d --build
curl -fsS http://localhost/docs
```

EC2의 `.env.prod`는 업로드 대상에서 제외되어 서버에 있는 운영 환경변수가 유지된다.
