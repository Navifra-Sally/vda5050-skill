# vda5050 skill for Claude Code (한국어)

Claude Code에 정확하고 출처가 있는 VDA 5050 지식을 넣어주는 플러그인입니다. fleet control이나
AMR 연동을 개발·디버깅할 때 씁니다.

- 토픽 구조, 헤더, QoS/retain 규칙
- order 의미론: base/horizon, stitching, 수락 결정 트리, 거절 에러 타입, cancel
- state 의미론: 노드 통과, idle, 운영 모드, 에러 레벨, request/response
- 사전 정의 action, blockingType, action 상태 전이
- 2.1 ↔ 3.0 차이와 필드 이름 변경
- 스펙이 통합자에게 넘긴 결정 지점 15개와 선택지별 비용 (`references/open-points.md`)
- 공식 JSON 스키마(2.1.0, 3.0.0)와 스키마 + order 의미 검증 스크립트 `scripts/validate.py`

## 정말 도움이 되나: 간단 측정

VDA 5050 3.0.0 사실 질문 4개를 빈 디렉토리에서 Claude Code(Sonnet)에 1~3회 물었습니다. 플러그인 없이는
2.x 이름으로 답하거나 없는 값을 지어냅니다. 3.0이 2026년 3월 공개라 학습 데이터에 거의 없기 때문입니다.

| 질문 | 플러그인 없음 | 플러그인 있음 |
|---|---|---|
| `connectionState` 값 | 틀림 (2.x 목록, HIBERNATING 없음) | 맞음 |
| state 위치/배터리 필드명 | 틀림 (`agvPosition`, `batteryState`) | 맞음 (`mobileRobotPosition`, `powerSupply`) |
| `blockingType` 값 | 틀림 (SINGLE 없음) | 맞음 |
| 취소된 order에 update 시 errorType | 지어냄 (`orderUpdateError`) | 맞음 (ORDER_UPDATE_FOLLOWING_CANCEL) |

없음 0/4, 있음 4/4. 벤치마크가 아니라 스모크 테스트입니다. 사실 조회만 봤고 order 생성이나 어댑터
코드 품질은 재지 않았습니다.

## 설치

```
/plugin marketplace add Navifra-Sally/vda5050-skill
/plugin install vda5050@vda5050-skill
```

로컬에서 바로 써보기: `claude --plugin-dir ./vda5050-skill`

## 이런 식으로 씁니다

- "로봇이 g에 서 있고 base가 f d g야. b h를 release하고 i를 horizon으로 붙이는 order update JSON 만들어줘"
- "state에 OUTDATED_ORDER_UPDATE 떴는데 왜?"
- "엣지 중간에서 cancel했더니 다음 order가 START_NODE_OUT_OF_RANGE로 거절돼"
- "startCharging은 instant action이야 node action이야?"
- "3.0 state를 2.1 파서로 넣게 변환 함수 짜줘"
- "VDA5050 3.0 시뮬 로봇 파이썬으로 짜줘"

각 예시가 어떤 근거로 답하는지는 영문 README의 Example prompts 절을 보세요.

## 메시지 검증

```
python3 skills/vda5050/scripts/validate.py order  my_order.json
python3 skills/vda5050/scripts/validate.py state  my_state.json --spec 2.1.0
```

스키마 검증에 더해 스키마로 못 잡는 order 규칙(sequenceId 연속성, base가 앞부분인지, 엣지 release
조건, 첫 노드 release)을 검사합니다. `pip install jsonschema` 필요.

## 라이선스

스킬 본문과 스크립트는 MIT입니다. `skills/vda5050/references/schemas/` 의 JSON 스키마는 Verband der
Automobilindustrie 저작, MIT이며 https://github.com/VDA5050/VDA5050 에서 가져왔습니다. 3.0.0 태그의
스키마 3개가 JSON으로 파싱되지 않아(업스트림 이슈 #660) `main` 커밋 0b2ae43 것을 번들했습니다.
