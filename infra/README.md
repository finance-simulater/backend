# Infra

Terraform으로 AWS EC2, 보안그룹, Elastic IP를 생성한다.

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
