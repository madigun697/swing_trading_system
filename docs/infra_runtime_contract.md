# Swing Trading System Infra Runtime Contract

작성일: 2026-05-10

## 1. 목적

Swing runtime이 Quant shared infra에 일관된 방식으로 연결되도록 env, port, compose 원칙을 정의한다.

## 2. 핵심 결정

### Canonical host contract
- 기본 host contract는 `INFRA_HOST` 하나로 통일한다.
- 기본값은 `localhost`다.
- 원격 infra 사용 시 `INFRA_HOST=<remote-host>`만 바꾸는 것을 기본 경로로 한다.

### Optional escape hatch
- 필요 시 `POSTGRES_HOST`, `MINIO_ENDPOINT`를 명시적으로 override할 수 있다.
- 단, 문서/예제/기본 운영 경로는 `INFRA_HOST`를 기준으로 한다.

## 3. 환경변수 계약

### 필수
- `INFRA_HOST`
- `POSTGRES_PORT`

### 기본 파생 규칙
- `POSTGRES_HOST = INFRA_HOST` (명시 override 없을 때)
- `MINIO_ENDPOINT = http://INFRA_HOST:9000` (명시 override 없을 때)

### 선택
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`
- `MINIO_REGION`
- `SWING_WEB_HOST`
- `SWING_WEB_PORT`
- `SWING_API_PORT`
- `SWING_METRICS_PORT`
- `ALPACA_*`
- notifier 관련 env

## 4. 포트 계약

### Shared Quant infra
| 서비스 | 포트 |
|---|---:|
| PostgreSQL | `55432` |
| MinIO API | `9000` |
| MinIO Console | `9001` |
| pgAdmin | `5050` |
| Airflow | `8080` |
| Quant web | `8000` |

### Swing reserved ports
| 서비스 | 포트 |
|---|---:|
| Swing web | `8401` |
| Swing API reserve | `8402` |
| Metrics/debug reserve | `8403` |

## 5. Compose 원칙

1. Swing compose는 `postgres`, `minio`를 새로 띄우지 않는다.
2. Swing compose는 shared Quant infra에 외부 연결만 수행한다.
3. Swing compose는 84xx 포트만 자체적으로 사용한다.
4. PostgreSQL/MinIO는 Quant runtime의 생명주기에 종속된다.

## 6. 실행 모드 계약

### Local development
```bash
INFRA_HOST=localhost
POSTGRES_PORT=55432
```

### Remote shared infra
```bash
INFRA_HOST=192.168.0.10
POSTGRES_PORT=55432
```

### Explicit override 예외
```bash
INFRA_HOST=192.168.0.10
POSTGRES_HOST=db.internal.example
MINIO_ENDPOINT=http://object.internal.example:9000
```

## 7. 서비스 주소 표기 규칙

- PostgreSQL: `${INFRA_HOST}:${POSTGRES_PORT}`
- MinIO API: `http://${INFRA_HOST}:9000`
- MinIO Console: `http://${INFRA_HOST}:9001`
- pgAdmin: `http://${INFRA_HOST}:5050`
- Airflow: `http://${INFRA_HOST}:8080`
- Quant web: `http://${INFRA_HOST}:8000`
- Swing web: `http://${INFRA_HOST}:8401`
- Swing API reserve: `http://${INFRA_HOST}:8402`
- Metrics/debug reserve: `http://${INFRA_HOST}:8403`

## 8. 운영 전제

- Quant infra가 먼저 올라와 있어야 한다.
- Swing DB user가 `swing_meta`, `swing_mart`, 필요 시 `swing_raw` 생성 권한을 가져야 한다.
- MinIO에 `swing-*` namespace를 생성할 수 있어야 한다.

## 9. 보안/안전 원칙

- 기본값은 paper trading / dry-run이다.
- notifier credentials와 broker credentials는 분리 관리한다.
- 운영 문서에는 localhost 예시와 remote host 예시를 함께 제공한다.

## 10. Sprint 1 진입 판정

Infra runtime contract 관점에서 Sprint 1은 **Ready**다.
외부 운영 전제는 다음 두 가지다.
1. Quant infra 접근 가능
2. DB/MinIO 권한 확보
