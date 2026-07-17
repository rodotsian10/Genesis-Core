# 제네시스 코어: 시스템 아키텍처 및 코어 엔진 설계

## 1. 개요
본 문서는 수백만 개의 개체(Entity)가 동시에 상호작용하는 "제네시스 코어" 시뮬레이션의 근간이 되는 코어 아키텍처를 설계합니다.

## 2. ECS (Entity-Component-System) 아키텍처
객체 지향(OOP) 대신 데이터 지향 설계인 ECS 패턴을 도입하여 캐시 적중률(Cache Hit Ratio)을 극대화하고 멀티스레드 병렬 처리를 가능하게 합니다.

### 2.1. Entity (엔티티)
모든 개체는 단순한 정수 ID(고유 식별자)입니다.
*   생물, 자원, 기후 현상, 심지어 '신(God)' 객체도 모두 하나의 Entity ID를 가집니다.

### 2.2. Component (컴포넌트)
로직이 없는 순수 데이터 구조체(Struct) 배열입니다.
*   `PositionComponent`: x, y, z 좌표
*   `HealthComponent`: 현재 체력, 최대 체력, 허기, 갈증
*   `DNAComponent`: 유전자 데이터 배열
*   `BrainComponent`: 신경망 가중치 및 노드 데이터
*   `FaithComponent`: 믿고 있는 신의 ID, 믿음의 강도

### 2.3. System (시스템)
특정 컴포넌트 조합을 가진 Entity들을 순회하며 로직을 처리합니다. 각 시스템은 독립적인 Worker Thread에서 병렬로 실행될 수 있습니다.
*   `MovementSystem`: Position과 Velocity 컴포넌트를 가진 모든 엔티티 업데이트.
*   `MetabolismSystem`: HealthComponent의 허기와 체력을 시간에 따라 갱신.
*   `NeuralNetworkSystem`: 시야(Vision) 입력을 받아 BrainComponent를 연산하여 다음 행동(Action) 도출.
*   `ReproductionSystem`: 교미 조건을 만족한 두 엔티티의 DNAComponent를 교차/돌연변이 연산하여 새 엔티티 생성.

## 3. 시뮬레이션 루프 (Simulation Loop)
시뮬레이션은 정해진 틱(Tick) 단위로 업데이트됩니다. 1 틱은 게임 내 최소 시간 단위입니다.

1.  **환경 업데이트 (Environment Tick):** 날씨, 온도, 태양광 계산.
2.  **감각 입력 처리 (Sensory Tick):** 각 생명체의 시야, 청각, 후각 거리 내의 데이터를 수집하여 뇌에 전달.
3.  **AI 연산 (Brain Tick):** 신경망을 거쳐 개체의 행동(이동, 섭취, 공격 등) 결정. (가장 무거운 연산이므로 GPU 가속 또는 잡 시스템 활용).
4.  **물리 및 행동 실행 (Action Tick):** 충돌 처리, 이동, 전투 결과 적용.
5.  **사망 및 탄생 처리 (Lifecycle Tick):** 체력이 0이 된 개체 삭제, 새로 태어난 개체 스폰.
6.  **역사 기록 (Logging Tick):** 의미 있는 임계치 돌파 시 로그 DB에 기록.

## 4. 백엔드 및 데이터베이스 설계
*   **시뮬레이터 코어:** C++ 또는 Rust 기반의 초고성능 엔진 (또는 Unity DOTS, Unreal Mass 활용).
*   **AI 트레이닝 백엔드:** Python (PyTorch) - 런타임 중 신경망 진화를 최적화하기 위해 비동기 통신으로 유전 알고리즘 세대 교체 연산.
*   **히스토리 DB:** MongoDB, InfluxDB - 방대한 타임라인 데이터 시계열 저장.
