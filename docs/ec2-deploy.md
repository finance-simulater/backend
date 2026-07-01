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
