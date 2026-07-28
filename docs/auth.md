# 인증 API

로컬 계정 인증은 이메일 인증, access token, refresh token을 함께 사용한다.

- access token: 응답 body로 전달하며 기본 유효기간은 15분이다.
- refresh token: JavaScript에서 읽을 수 없는 HttpOnly 쿠키로 전달한다.
- Redis에는 refresh token 원문 대신 SHA-256 해시와 사용자 ID를 저장한다.
- refresh 요청이 성공하면 기존 refresh token을 폐기하고 새 토큰으로 교체한다.
- 이메일 인증번호는 10분 동안 유효하며 Redis에는 HMAC 해시만 저장한다.
- 이메일 인증이 성공하면 회원가입에 한 번 사용하는 임시 인증 티켓을 발급한다.
- 임시 인증 티켓은 기본 30분 동안 Redis에만 저장된다.
- 최종 회원가입 전에는 `users` 테이블에 사용자 행을 생성하지 않는다.

## 환경변수

로컬 `.env`와 EC2 `.env.prod`에 다음 값을 설정한다.

```dotenv
SECRET_KEY=32바이트-이상의-충분히-긴-무작위-문자열
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=14
REFRESH_COOKIE_NAME=refresh_token
COOKIE_SECURE=false
EMAIL_PROVIDER=console
EMAIL_FROM_ADDRESS=no-reply@fsimulation.store
EMAIL_VERIFICATION_TTL_MINUTES=10
EMAIL_VERIFICATION_TICKET_TTL_MINUTES=30
EMAIL_RESEND_COOLDOWN_SECONDS=60
EMAIL_VERIFICATION_MAX_ATTEMPTS=5
```

운영 환경에서는 `COOKIE_SECURE=true`를 사용한다. `SECRET_KEY`는 Git에 올리거나
팀 채팅에 공유하지 않는다. 값이 없거나 32자보다 짧으면 애플리케이션이 시작되지
않는다. 운영 환경에서는 `EMAIL_PROVIDER=ses`를 사용한다.

무작위 secret은 다음 명령으로 생성할 수 있다.

```bash
openssl rand -hex 32
```

## 엔드포인트

### 인증번호 전송

```http
POST /api/v1/auth/email/send
Content-Type: application/json
```

```json
{
  "email": "user@example.com"
}
```

로컬에서 `EMAIL_PROVIDER=console`을 사용하면 인증번호는 FastAPI 로그에
출력된다. 기본적으로 같은 이메일에는 60초에 한 번만 전송할 수 있다. 가입 여부를
노출하지 않기 위해 이미 가입된 이메일도 동일한 `202 Accepted` 응답을 반환하지만,
인증번호는 발송하지 않는다.

### 이메일 인증

```http
POST /api/v1/auth/email/verify
Content-Type: application/json
```

```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

인증 성공 시 최종 회원가입에 사용할 임시 티켓을 반환한다. 이 단계에서는 사용자
DB 행과 로그인 토큰을 만들지 않는다. 존재하지 않는 인증 요청과 이미 가입된
이메일은 모두 `INVALID_VERIFICATION_CODE`로 응답해 가입 여부를 구분할 수 없게 한다.

```json
{
  "email_verification_token": "임시-인증-티켓",
  "expires_in": 1800
}
```

### 회원가입

```http
POST /api/v1/auth/signup
Content-Type: application/json
```

```json
{
  "email": "user@example.com",
  "email_verification_token": "이메일-인증-응답의-임시-티켓",
  "password": "password123",
  "nickname": "tester",
  "profile_image_seed": "tester",
  "job_type": "employee",
  "monthly_salary": 3000000
}
```

서버가 이메일과 임시 티켓의 조합을 먼저 확인한 뒤 중복 여부를 검사하고 인증 완료
상태의 사용자를 생성한다. 따라서 유효한 티켓 없이 회원가입 API로 이메일 가입
여부를 확인할 수 없다. 성공하면 access token을 응답하고 refresh token 쿠키를 설정하며,
사용한 임시 티켓은 삭제한다. 사용자가 이메일 인증 후 뒤로가더라도 회원가입을
제출하지 않았다면 DB에는 사용자 행이 남지 않고 임시 티켓만 만료된다.

### 로그인

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

### 내 정보

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

### 토큰 재발급

```http
POST /api/v1/auth/refresh
```

브라우저 요청에는 쿠키가 포함되어야 한다.

```javascript
fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
  method: "POST",
  credentials: "include",
});
```

### 로그아웃

```http
POST /api/v1/auth/logout
```

Redis의 refresh token을 삭제하고 브라우저 쿠키를 만료시킨다.

## AWS SES 설정

`infra/terraform.tfvars`에 다음 값을 추가한다.

```hcl
ses_domain_name  = "fsimulation.store"
ses_from_address = "no-reply@fsimulation.store"
```

`terraform apply` 후 `terraform output ses_dkim_records`에 나온 세 개의 CNAME을
Cloudflare DNS에 추가한다. DKIM CNAME은 프록시를 끈 DNS only로 설정한다.

SES 계정이 sandbox 상태라면 검증된 수신 주소에만 보낼 수 있다. 실제 회원 이메일로
보내려면 AWS SES의 Production access를 요청해야 한다.

- [AWS SES 도메인 Identity 설정](https://docs.aws.amazon.com/ses/latest/dg/creating-identities.html)
- [AWS SES sandbox 제한](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html)
