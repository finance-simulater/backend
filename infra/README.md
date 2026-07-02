# Infra

Terraform으로 AWS EC2, 보안그룹, Elastic IP, RDS MySQL, 프론트엔드 정적 배포용 S3 bucket, CloudFront를 생성한다.

## 사전 준비

1. AWS CLI 로그인 설정

```bash
aws configure
```

리전은 `ap-northeast-2`를 사용한다.

2. EC2 키페어 생성

AWS 콘솔에서 EC2 키페어를 만들고 `.pem` 파일을 안전하게 보관한다.
Terraform에는 키페어 이름만 입력한다.

3. 내 IP 확인

```bash
curl ifconfig.me
```

확인한 IP 뒤에 `/32`를 붙여 `ssh_allowed_cidr`에 입력한다.

## 실행

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars`를 실제 값으로 수정한다. 이 파일은 Git에 올리지 않는다.

```bash
terraform init
terraform plan
terraform apply
terraform output
```

EC2 접속:

```bash
ssh -i <your-key.pem> ubuntu@<ec2_public_ip>
```

## 주의

- `terraform.tfvars`, `terraform.tfstate`, `.pem` 파일은 Git에 올리지 않는다.
- SSH 22번 포트는 내 IP `/32`만 허용한다.
- FastAPI 8000 포트는 직접 열지 않는다. 운영에서는 Nginx가 80/443으로 프록시한다.
- 도메인 DNS A 레코드는 `terraform output ec2_public_ip` 값으로 연결한다.
- 학습 단계의 RDS는 로컬 접속 확인을 위해 public endpoint를 사용한다. 운영 전환 시 private RDS로 변경한다.

## 프론트엔드 S3 + CloudFront

Terraform apply 후 아래 output을 확인한다.

```bash
terraform output frontend_bucket_name
terraform output frontend_cloudfront_domain_name
terraform output frontend_url
```

프론트엔드 빌드 산출물은 S3 bucket에 업로드한다.

```bash
aws s3 sync ./dist s3://<frontend_bucket_name> --delete
```

CloudFront 캐시를 즉시 비우려면 distribution ID로 invalidation을 실행한다.

```bash
aws cloudfront create-invalidation \
  --distribution-id <frontend_cloudfront_distribution_id> \
  --paths "/*"
```

커스텀 프론트 도메인을 연결하려면 `terraform.tfvars`에 아래 값을 설정한다.

```hcl
frontend_domain_names        = ["fsimulation.store"]
frontend_acm_certificate_arn = "arn:aws:acm:us-east-1:..."
```

CloudFront용 ACM 인증서는 반드시 `us-east-1` 리전에 있어야 한다.

## 사용자 업로드 S3

회원가입, 프로필 이미지 같은 사용자 업로드 파일은 프론트 배포용 bucket과 분리된 private S3 bucket에 저장한다.

Terraform apply 후 bucket 이름을 확인한다.

```bash
terraform output upload_bucket_name
```

운영 서버의 `.env.prod`에는 아래 값을 추가한다.

```text
AWS_REGION=ap-northeast-2
UPLOAD_BUCKET_NAME=<upload_bucket_name>
```

업로드 흐름은 아래 구조를 사용한다.

```text
프론트 -> 백엔드에 업로드 URL 요청
백엔드 -> S3 presigned URL 발급
프론트 -> presigned URL로 S3에 직접 업로드
백엔드 DB -> S3 object key 저장
```

S3 bucket은 public access를 차단한다. EC2에는 IAM instance profile을 붙여 upload bucket에 필요한 최소 권한만 부여한다.

프론트 도메인이 정해지면 `terraform.tfvars`의 `upload_allowed_origins`에 해당 도메인을 추가해야 브라우저에서 presigned URL 업로드가 가능하다.

```hcl
upload_allowed_origins = [
  "http://localhost:3000",
  "http://localhost:5173",
  "https://fsimulation.store",
]
```
