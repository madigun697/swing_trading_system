전체적으로 이 전략은 “수익 극대화”보다 “국면 적응 + 리스크 관리” 철학이 명확해서, 스윙 트레이딩 시스템으로 매우 좋은 방향입니다.
특히 다음 3가지가 강점입니다.

* Regime 기반 전략 스위칭
* 전략 다변화(Pullback / Breakout / Momentum)
* 현금 비중 조절을 통한 Tail Risk 방어

다만 현재 설계 상태로는 목표인:

* CAGR 25%
* WIN rate 60%+
* MDD -10% 내외

를 동시에 달성하기에는 몇 가지 핵심 요소가 부족합니다.

아래 관점으로 평가드리겠습니다.

⸻

1. 전략 구조 자체는 “상위 10~20% 수준”

현재 구조는 사실상 다음 헤지펀드 스타일 접근과 유사합니다.

구성	유사 전략
Regime Switching	Bridgewater / AQR 계열
Momentum + Breakout	CANSLIM / Trend Following
Pullback	Mean Reversion Swing
Cash Overlay	Volatility Targeting

즉 방향성은 매우 좋습니다.

특히 스윙에서 중요한 건:

“언제 공격하고 언제 쉬는가”

인데 이 전략은 그 핵심을 잘 잡고 있습니다.

⸻

2. 가장 중요한 문제: “레짐 판단 지연”

현재 문서에서 가장 위험한 부분은:

“월말 평가”

입니다.

스윙 트레이딩에서 월말 기반 레짐 전환은 너무 느립니다.

2020 코로나
2022 금리쇼크
2024 AI correction 류의 장에서는:

* 5~10 거래일 안에
* -8~-15% 급락

이 발생합니다.

즉 월말 기준이면:

* MDD -10% 목표 달성이 거의 불가능합니다.

⸻

3. 추천: 레짐 판단 구조 수정 (핵심)

권장 구조

상위 레짐 (Weekly)

큰 방향 판단

하위 레짐 (Daily)

리스크 OFF 감지

즉:

레벨	역할
Weekly	Bull / Bear
Daily	Risk ON/OFF Trigger

⸻

4. 추천 레짐 시스템 (실전형)

현재 문서에 가장 필요한 부분입니다.

추천 조합

Core Trend Filter

* SPY > 200MA
* QQQ > 200MA
* Market Breadth > 50%

→ Bull

⸻

Risk Filter

* VIX > 25
* ATR Expansion
* QQQ < 20MA
* Distribution Day 증가

→ Risk OFF

⸻

Breadth Filter (매우 중요)

다음이 핵심입니다:

* S&P500 종목 중
* 50MA 위 비율

이게 40% 이하 내려가면:

강세장처럼 보여도 내부는 이미 약세입니다.

이걸 넣어야 MDD 방어가 됩니다.

⸻

5. 현재 레짐 분류 평가

현재 R1~R5 구조는 좋습니다.

다만 실제 운용에서는 아래처럼 단순화하는 게 성능이 좋습니다.

추천 구조	이유
Bull	공격
Neutral	제한적
Bear	현금화

너무 세분화하면:

* 오버피팅
* 전환 노이즈
* 실행 복잡성

이 증가합니다.

⸻

6. 목표 MDD -10% 달성 가능성

솔직히 말하면:

현재 구조만으로는 어려움

이유:

* Breakout 전략은 원래 MDD 큼
* Momentum도 급락장에 취약
* Pullback은 knife-catching 위험 존재

즉:

리스크 관리가 수익보다 더 중요

합니다.

⸻

7. MDD -10%를 위한 핵심 규칙 (필수)

(1) 레짐 OFF 시 강제 현금화

추천:

Regime	현금 비중
Strong Bull	0~10%
Volatile Bull	20~40%
Sideways	40~60%
Early Bear	80~100%
Deep Bear	90~100%

여기서 핵심:

“애매하면 쉬어라”

입니다.

⸻

(2) Portfolio Heat 제한

매우 중요합니다.

예:

* 총 손실 가능액 = 계좌의 5%

예시:

* 종목 5개
* 각 종목 손절 -1%

→ 전체 위험 = -5%

이 개념이 없으면 MDD 통제가 불가능합니다.

⸻

(3) 변동성 기반 포지션 사이징

ATR 기반 추천.

예:

Position Size =
(Account Risk)
/ (ATR x K)

이게 없으면:

* 변동성 큰 장에서
* 손실이 폭증합니다.

⸻

8. 전략별 평가

A. Breakout

장점

* CAGR 핵심 담당
* 큰 수익 창출

단점

* Win rate 낮음
* 횡보장 취약

추천

* R1 전용
* R2에서는 비중 축소

추천 비중:

Regime	Weight
R1	50~70%
R2	20~30%
R3 이하	OFF

⸻

B. Pullback

장점

* Win rate 높음
* 스윙 적합

단점

* 하락장에서 위험

추천

* 핵심 안정 전략으로 활용

추천 비중:

Regime	Weight
R1	20~30%
R2	50~70%
R3	70%
R4 이하	OFF

⸻

C. Quality Momentum

장점

* CAGR 향상
* 장기 추세 대응

단점

* 회전율 낮음
* 시장 붕괴 시 급락

추천

* 시장 Breadth 좋을 때만

⸻

9. 가장 중요한 개선점: “손절 체계”

문서에서:

“기존 방식대로 진행”

이라고 되어 있는데,

사실 전략 성패는 여기서 갈립니다.

⸻

10. 추천 손절 구조

초기 손절

* ATR 1.5~2 기반

or

* 최근 스윙로우 이탈

⸻

트레일링

추천:

* 10EMA
* 20EMA
* Chandelier Exit

⸻

시간 손절(Time Stop)

매우 중요.

예:

* 7~10일 동안
* 기대 방향 안 나오면 청산

이걸 넣으면:

* 자금 효율 상승
* MDD 감소
* CAGR 상승

효과 큽니다.

⸻

11. WIN RATE 60% 달성 가능성

현실적으로:

전략	일반 Win Rate
Breakout	35~50%
Momentum	40~55%
Pullback	55~70%

즉:

60% 이상을 원하면
Pullback 중심이어야 합니다.

하지만:

* CAGR은 낮아질 가능성 존재

따라서 최적 구조는:

전략	목적
Pullback	Win rate 확보
Breakout	CAGR 확보
Momentum	추세 수익 유지

입니다.

⸻

12. 추천 최종 구조 (실전형)

Bull Market

* Breakout 50%
* Momentum 30%
* Pullback 20%

⸻

Volatile Bull

* Pullback 60%
* Breakout 20%
* Momentum 20%

⸻

Sideways

* Pullback only
* 포지션 축소

⸻

Bear

* 현금화
* 단기채/MMF

⸻

13. 가장 추천하는 추가 요소

Volatility Targeting

이걸 넣으면 시스템 퀄리티가 급상승합니다.

예:

* VIX 상승 시
* 포지션 자동 축소

이건 실제 퀀트펀드 핵심 기술입니다.

⸻

14. 현실적인 기대 성과

구조를 잘 다듬으면:

지표	현실 가능 범위
CAGR	18~35%
MDD	-8~-15%
Win Rate	50~65%
Profit Factor	1.5~2.5

정도는 충분히 가능합니다.

특히:

“Bear Market 회피 능력”

이 좋아지면 장기 CAGR이 크게 향상됩니다.

⸻

최종 평가

강점

* 방향성 매우 우수
* Regime 기반 접근 적절
* 스윙 전략과 궁합 좋음
* MDD 관리 철학 존재

⸻

가장 위험한 부분

* 월말 레짐 전환
* 손절 규칙 구체성 부족
* 변동성 기반 포지션 사이징 부재
* Breadth/VIX 필터 없음

⸻

제가 추천하는 핵심 개선 우선순위

1순위

레짐 탐지 고도화

2순위

ATR 기반 리스크 사이징

3순위

Portfolio Heat 제한

4순위

VIX/Breadth 필터 추가

5순위

시간 손절(Time Stop)

⸻

이 전략은 잘 다듬으면:

“공격적이지만 생존 가능한”
상위권 스윙 시스템

으로 발전 가능성이 높습니다.