# 주식 모의투자 API 구현 문서

> 담당: 박수민 | 브랜치: `feat/11-stock-holdings-api`
> 스펙: `spec/feature/investment/README.md`, `spec/api/openapi.yaml` `investment` 태그

---

## 구현된 API

| 메서드 | 경로 | 설명 | 상태 |
|---|---|---|---|
| `GET` | `/api/v1/stocks` | 보유 주식 현황 + 투자 가능 현금 조회 | ✅ 완료 |
| `POST` | `/api/v1/stocks/buy` | 주식 매수 | ✅ 완료 |
| `POST` | `/api/v1/stocks/sell` | 주식 매도 (부분·전체) | ✅ 완료 |
| 내부 함수 | `StockService.apply_monthly_simulation()` | 턴 처리 시 몬테카를로 시가 갱신 | ⬜ 미구현 (턴 처리 파트 연동 시 추가) |

---

## 파일 구조

```
app/api/v1/stock/
├── __init__.py       빈 파일 (Python 패키지 선언)
├── model.py          SQLAlchemy 모델 (stock_holdings 테이블)
├── schema.py         Pydantic 입출력 스키마
├── repository.py     DB 쿼리 (StockHolding + SimulationState)
├── service.py        비즈니스 로직 (get_portfolio / buy / sell)
└── router.py         FastAPI 엔드포인트
```

---

## 관련 테이블

### `stock_holdings`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | BIGINT PK | |
| `user_id` | BIGINT FK | users.id |
| `stock_type` | ENUM | `high_vol` / `low_vol` / `index` |
| `principal` | INT | 투자 원금. 매수/매도 시만 변경 |
| `current_value` | INT | 현재 평가금액. 매턴 몬테카를로로 갱신 |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | ON UPDATE CURRENT_TIMESTAMP |

- UNIQUE KEY `(user_id, stock_type)` → 한 유저가 같은 전략을 중복 보유 불가. 추가 매수 시 기존 레코드를 업데이트.

### `simulation_state` (조회·갱신만)

- `cash_balance` : 매수 시 차감, 매도 시 증가.

---

## 주식 전략 3종

| `stock_type` | 이름 | 변동 범위 | 위험도 |
|---|---|---|---|
| `high_vol` | 고변동성 주식 | -30% ~ +30% | 고위험 |
| `low_vol` | 저변동성 주식 | -10% ~ +10% | 저위험 |
| `index` | 지수에 투자 | -5% ~ +5% | 중위험 |

---

## 코드 흐름

### GET /api/v1/stocks

```
router.get_portfolio(user_id)
  → service.get_portfolio(user_id)
      → repository.find_simulation_state(user_id)  # cash_balance 조회
      → repository.find_all_by_user(user_id)       # 보유 주식 전체 조회
      → _to_holding_dict() 로 각 holding 가공
          (profit_loss, profit_loss_rate 계산, STOCK_META로 한글명/위험도 매핑)
      → 합산값(total_principal, total_current_value, total_profit_loss) 계산
  ← StockPortfolioResponse 반환
```

### POST /api/v1/stocks/buy

```
router.buy_stock(user_id, StockBuyRequest)
  → service.buy(user_id, request)
      → repository.find_simulation_state(user_id)
      → 잔액 검증: request.amount > cash_balance → 400 INSUFFICIENT_BALANCE
      → repository.find_by_user_and_type(user_id, stock_type)
          존재하면: principal += amount, current_value += amount (추가 매수)
          없으면: 신규 레코드 생성 (principal = current_value = amount)
      → cash_balance -= amount
      → db.commit()
  ← StockActionResponse 반환
```

### POST /api/v1/stocks/sell

```
router.sell_stock(user_id, StockSellRequest)
  → service.sell(user_id, request)
      → repository.find_by_user_and_type(user_id, stock_type)
          없으면: 404 NOT_FOUND
      → 금액 검증: request.amount > current_value → 400 INSUFFICIENT_HOLDINGS
      → repository.find_simulation_state(user_id)
      → sell_ratio = amount / current_value
      → new_principal = round(principal × (1 - sell_ratio))
      → new_current = current_value - amount
          new_current == 0 (전체 매도): 레코드 삭제
          new_current > 0 (부분 매도): 레코드 업데이트
      → cash_balance += amount
      → db.commit()
  ← StockActionResponse 반환 (전체 매도 시 holding=null)
```

---

## 에러 응답

> 형식: `{"code": "...", "detail": "..."}` — `spec/api/domains/errors.md` 참고

| code | HTTP | 발생 상황 |
|---|---|---|
| `INSUFFICIENT_BALANCE` | 400 | 매수 금액 > 현금 잔액 |
| `INSUFFICIENT_HOLDINGS` | 400 | 매도 금액 > 보유 평가금액 |
| `NOT_FOUND` | 404 | 보유 주식 없음 (매도 시) / 시뮬레이션 상태 없음 |

---

## 타 파트 연동 포인트

### JWT 인증 (손기훈 파트 완성 후 교체)

현재 `user_id`를 쿼리 파라미터(`?user_id=1`)로 받음. JWT 완성 후:

```python
# router.py 각 엔드포인트에서
user_id: int  # 이 줄을 아래로 교체
user: User = Depends(get_current_user)  # JWT에서 user 추출
```

### 턴 처리 (김여진 파트 연동)

`POST /turns/process` 내부에서 아래 한 줄 추가:

```python
from app.api.v1.stock.service import StockService

stock_service = StockService(db)
stock_service.apply_monthly_simulation(user_id, turn_number)
```

`apply_monthly_simulation`은 현재 미구현. 턴 처리 파트와 협의 후 `service.py`에 추가 예정.

### 대시보드 (김여진 파트)

`GET /dashboard` 응답의 `보유 주식 평가액` 필드:

```python
from app.api.v1.stock.repository import StockRepository

repo = StockRepository(db)
holdings = repo.find_all_by_user(user_id)
total_stock_value = sum(h.current_value for h in holdings)
```

---

## 로컬 테스트 방법

```bash
# 1. Docker MySQL 실행
docker compose up -d mysql

# 2. 마이그레이션
uv run alembic upgrade head

# 3. 서버 실행
uv run uvicorn app.main:app --reload

# 4. Swagger UI
open http://localhost:8000/docs
```

### 테스트 시나리오

```bash
# 보유 현황 조회 (초기: 빈 배열)
curl "http://localhost:8000/api/v1/stocks?user_id=1"

# 고변동성 주식 30만원 매수
curl -X POST "http://localhost:8000/api/v1/stocks/buy?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{"stock_type": "high_vol", "amount": 300000}'

# 부분 매도 (10만원)
curl -X POST "http://localhost:8000/api/v1/stocks/sell?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{"stock_type": "high_vol", "amount": 100000}'

# 잔액 부족 에러 확인 (현금보다 많이 매수)
curl -X POST "http://localhost:8000/api/v1/stocks/buy?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{"stock_type": "index", "amount": 9999999}'
```
