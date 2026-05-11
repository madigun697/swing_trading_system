# Sprint 2 QA Starting Points

작성일: 2026-05-11

## 목적

Sprint 1 review의 Sprint 2 권장 시작점 중 look-ahead 방지 테스트 기준을 Sprint 2 착수 전에 명문화한다.

## 필수 QA 기준

1. Screening input은 항상 `trade_date <= as_of_date`만 downstream으로 전달한다.
2. Screening input은 오름차순으로 정렬되어 feature/strategy 계산에 전달된다.
3. Feature 저장은 `swing_mart.swing_feature_store`에만 수행한다.
4. Screening run/signals 저장은 `swing_meta.screening_run`, `swing_meta.signal`에만 수행한다.
5. Quant shared relation은 `stg.*` read-only로만 사용한다.

## 추가된 Sprint 2 준비 테스트

- `tests/test_screening_input_loader.py`
  - future row filtering
  - ascending order enforcement
  - invalid lookback rejection
- `tests/test_screening_pipeline.py`
  - feature store 연결
  - screening run / signal 연결
  - run completion 연결
- `tests/test_swing_repository_contract.py`
  - Swing-owned schema write contract 확인

## Sprint 2 시작 가능 조건

- 위 테스트가 통과해야 screening/strategy 구현을 시작한다.
