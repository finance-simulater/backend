# 트러블슈팅 기록

문제를 해결할 때마다 **증상 → 원인 → 해결 → 교훈**을 여기에 남긴다. 같은 문제를 두 번 겪지 않고, 새 팀원이 맥락을 빠르게 잡기 위함.

> 새 항목은 **맨 위에** 추가한다(최신순). 아래 템플릿을 복사해서 채운다.

```markdown
## [YYYY-MM-DD] 제목 (#이슈번호)

**증상**: 무엇이 어떻게 잘못 보였나
**원인**: 근본 원인
**해결**: 어떻게 고쳤나 (코드/명령 포함)
**교훈**: 다음에 어떻게 예방/대응할까
**관련**: 파일·PR·커밋
```

---

## [2026-08-01] 매수/매도 동시 요청 시 잔액 음수·초과 매도 (#11)

**증상**
동일 유저가 더블클릭·재시도로 매수/매도 요청을 거의 동시에 보내면 `cash_balance`가 음수가 되거나 보유량을 초과해 매도되는 상황이 이론적으로 가능.

**원인**
`buy()`/`sell()`가 "조회 → 검증 → 갱신"을 잠금 없이 처리. 두 요청이 모두 갱신 전의 잔액을 읽고 검증을 통과한 뒤 각자 커밋(read-check-write race).

**해결**
- repository 조회 메서드에 `for_update` 옵션 추가 → `with_for_update()` (`SELECT ... FOR UPDATE`)로 행을 트랜잭션 종료까지 잠금.
- `buy()`/`sell()`에서 `SimulationState`·`StockHolding`을 `for_update=True`로 조회.
- **락 순서를 `SimulationState → StockHolding`으로 통일**해 데드락 방지(원래 `sell`은 holding을 먼저 조회 → state 먼저 조회로 변경).

```python
# repository.py
def find_simulation_state(self, user_id, for_update=False):
    query = self.db.query(SimulationState).filter(SimulationState.user_id == user_id)
    if for_update:
        query = query.with_for_update()
    return query.first()
```

**교훈**
- "조회 → 검증 → 갱신"이 한 요청 안에서 이뤄지는 곳은 항상 동시성 의심. 잔액·재고처럼 공유 자원을 갱신하면 행 잠금(FOR UPDATE) 또는 원자적 UPDATE로 직렬화한다.
- 여러 행을 잠글 땐 **모든 경로에서 잠금 순서를 동일하게** 유지해야 데드락이 안 난다.
- (선택) DB에 `CHECK(cash_balance >= 0)` 제약을 두면 앱 버그가 있어도 최후 방어선이 된다 — 마이그레이션 + `erd.md` 갱신 필요.

**관련**: `app/api/v1/stock/repository.py`, `app/api/v1/stock/service.py`

---

## [2026-08-01] 부분 매도 반복 시 원금 반올림 오차 누적 (#11)

**증상**
부분 매도를 여러 번 하면 남은 `principal`에 `round()` 오차가 조금씩 쌓임.

**원인**
`new_principal = round(principal * (1 - sell_ratio))` — **남는 비율**을 곱해 매번 반올림하므로 오차가 남은 원금에 축적됨.

**해결**
"파는 원금"을 계산해 원금에서 정수로 차감:
```python
sold_principal = round(holding.principal * sell_ratio)
new_principal  = holding.principal - sold_principal
```
원래 원금(정수)에서 정수를 빼므로 "원금 − 판 것들의 합"이 항상 정확히 일치.

**교훈**
비율로 잔량을 재계산하기보다 **변화량(delta)을 계산해 원값에서 가감**하면 반올림 누적이 없다.

**관련**: `app/api/v1/stock/service.py` `sell()`

---

## [2026-08-01] DB 없이 API 엔드포인트 테스트하기 (#11)

**증상**
stock API를 유닛 테스트하고 싶은데, 실제 MySQL에 붙이면 CI에서 느리고 데이터 세팅이 번거로움.

**해결**
repository를 in-memory `FakeStockRepository`로 대체하고 FastAPI `dependency_overrides`로 주입. 라우터·서비스 로직은 그대로 타면서 DB만 가짜로 교체.
```python
def make_client(repo):
    service = StockService(db=MagicMock(), repository=repo)
    app.dependency_overrides[get_stock_service] = lambda: service
    return TestClient(app)
```
- Fake는 실제 repo 메서드 시그니처(`for_update` 인자 포함)를 동일하게 구현해야 서비스가 정상 동작.
- `dependency_overrides`는 테스트 후 `pop`으로 정리(fixture `autouse`로 자동화).

**교훈**
4계층 구조(repository 분리) 덕분에 DB를 손쉽게 목킹할 수 있다. 새 도메인도 같은 패턴으로 테스트 작성.

**관련**: `tests/test_stock.py`, 기존 참고: `tests/test_error_responses.py`

---

## [2026-07-28] 로컬 실행 시 RDS로 붙어 연결 타임아웃 (#11)

**증상**
`uvicorn`/`alembic` 실행 시 `Can't connect to MySQL server on '...rds.amazonaws.com' (timed out)`.

**원인**
`.env`의 `DATABASE_URL`이 팀 공유 RDS를 가리킴. 로컬에서 RDS 보안그룹 접근이 막혀 타임아웃. `.env`는 git 미추적(`.gitignore`)이라 각자 로컬 값이며, git 작업으로 바뀌지 않는다(되돌린 건 수동 편집).

**해결**
로컬 개발은 Docker MySQL을 사용하도록 `.env` 변경(RDS 값은 주석으로 보존):
```
DATABASE_URL=mysql+pymysql://ssu_finance_user:ssu_password12@localhost:3306/ssu_finance
# DATABASE_URL=mysql+pymysql://finance_admin:...@...rds.amazonaws.com:3306/finance
```
```bash
docker compose up -d          # MySQL + Redis
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

**교훈**
- `.env`는 개인 로컬 파일 — git이 절대 안 건드린다. 값이 "되돌아간다"면 수동 편집을 의심.
- 로컬은 Docker MySQL, RDS는 필요 시 주석 전환. `.env.example` 템플릿은 커밋해 공유.

**관련**: `backend/.env`, `docker-compose.yml`
