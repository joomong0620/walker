# 🚶 길벗이

AI와 센서 데이터를 기반으로
고령자의 **보행 중 위험 상황을 실시간으로 감지**하고 보호자가 대응하는 웹·앱 기반 플래폼

----

## 🧩 Project Overview

길벗이는
고령자 및 거동이 불편한 사용자를 위한
**AI + IoT + 서버 기반 실시간 안전 보행 지원 시스템**입니다.

단순 객체 인식이 아니라,
AI 추론 결과와 센서 데이터를 종합해
위험도를 계산하고 즉시 대응하는 구조 설계에 초점을 맞췄습니다.


## 🕰️ 개발 기간
* 24.09.02일 ~ 25.02.24일(6개월)


## 🧠 Problem Definition

기존 보행 보조 기기의 한계:
- 단순 보행 보조 기능 중심
- 위험 감지 후 수동 대응
- AI 모델 결과를 그대로 출력하는 구조
- 데이터 누적 및 분석 시스템 부재

👉 우리는 질문했습니다:

“AI가 장애물을 인식했다면,
그 다음은 누가 판단하고 어떻게 대응할 것인가?”

길벗이는 AI 결과를 서비스 구조 안에서 재해석하고,
실시간 위험도 계산과 경고 시스템으로 연결하는 것을 목표로 설계되었습니다.



### 👩‍💻 멤버구성

| 이름      | 담당 기능                                                     |
| ------- | --------------------------------------------------------- |
| 김주연     | 팀장, 데이터베이스 설계 및 구축, FastAPI 서버 개발 및 배포, AI 위험도 계산 로직 설계   |
| 팀원A     | 보행기 하드웨어 구성 및 회로 설계, 센서 데이터 처리 및 연동 구현, 하드웨어 기반 경고 시스템 구현 |
| 팀원B     | 장애물 인식 AI 모델 제작, 차선·횡단보도·포트홀 인식 모델 개발                     |
| 팀원C     | 모바일 애플리케이션 디자인 및 제작, 서버 및 하드웨어 연동                         |
| 팀원D     | 웹 대시보드 화면 구성 및 제작, 음성 알림 경고 시스템 구현                        |


### ⚙️개발 환경
- **Language**: Python 3.12  
- **Backend Framework**: FastAPI  
- **AI / Computer Vision**: YOLOv8, OpenCV  
- **Database**: PostgreSQL    
- **Server / Infra**: Railway, Docker, Uvicorn     



## 👩‍💻 My Role (김주연 | Team Lead, Backend)

### 🔹 총괄 역할
- 팀장
- 백엔드 아키텍처 설계
- 데이터베이스 설계 및 구축
- API 서버 구현 및 배포
- AI 위험 계산 로직 설계

### 🛠 Architecture & Backend Design
#### 1️⃣ 데이터베이스 설계 (PostgreSQL) - [상세 보기 - WIKI 이동](https://github.com/joomong0620/walker/wiki/%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C(DB-%EA%B5%AC%EC%B6%95))
- 설계 목표
- AI 추론 결과 + 센서 데이터 통합 저장
- 사용자별 활동 데이터 분석 가능 구조
- 심박, 가속도, 자이로센서 IoT 통신


> 구현 내용
- 사용자 / 활동 기록 / 위험 로그 / 센서 데이터 테이블 분리 설계
- BASE_RISK_TABLE 설계
- 인덱싱 적용으로 조회 성능 개선
- 데이터 정규화 구조 설계

👉 단순 저장이 아니라
“이후 분석과 리포트 생성을 고려한 구조 설계”

#### 2️⃣ API 서버 구축 (FastAPI)  - [상세 보기 - WIKI 이동](https://github.com/joomong0620/walker/wiki/%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C(API-%EA%B5%AC%EC%B6%95))
- 활동 시간 조회
- 심박수 및 센서 데이터 수집
- 실시간 위험 감지 API
- 평균 데이터 기반 리포트 생성 API
- RESTful 구조 설계
- Uvicorn 기반 비동기 처리 구조 적용

#### 3️⃣ AI 위험 감지 로직 설계  - [상세 보기 - WIKI 이동](https://github.com/joomong0620/walker/wiki/%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C(AI-%EC%9C%84%ED%97%98-%EA%B0%90%EC%A7%80-%EB%B0%8F-%EA%B2%BD%EA%B3%A0-%EC%8B%9C%EC%8A%A4%ED%85%9C))
단순 YOLO 결과 반환 ❌
→ 위험도 계산 구조 설계 ⭕

- YOLO 감지 로직
- BASE RISK TABLE 위험도 계산 로직
- 알림 레벨 (STOP/SLOW/CAUTION/NORMAL) 분류 로직

👉 AI 모델 결과를
의사결정 가능한 지표로 재가공

#### 4️⃣ 실시간 경고 시스템  - [상세 보기 - WIKI 이동](https://github.com/joomong0620/walker/wiki/%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C(AI-%EC%9C%84%ED%97%98-%EA%B0%90%EC%A7%80-%EB%B0%8F-%EA%B2%BD%EA%B3%A0-%EC%8B%9C%EC%8A%A4%ED%85%9C))

- 센서 데이터 + AI 결과 통합 처리
- 하드웨어와 API 연동
- 위험 레벨에 따른 경고 신호 라즈베리파이와 연동
- 반복 테스트를 통한 안정성 확보

### 🚀 Server Deployment  - [상세 보기 - WIKI 이동](https://github.com/joomong0620/walker/wiki/%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C(%EC%84%9C%EB%B2%84-%EB%B0%B0%ED%8F%AC))
- Docker 기반 컨테이너화
- Railway 배포
- 환경 변수 분리
- 서버–AI 연동 구조 설계





## 🧠 What I Focused On

- AI 결과를 그대로 사용하는 것이 아니라 서비스 구조 안에서 재해석
- 위험 판단 로직 설계
- 데이터 무결성 확보
- 실시간 처리 안정성
- 하드웨어–서버–AI 통합 구조 설계



## 🌱 Key Learning
- 모델 성능만으로는 서비스가 완성되지 않는다.
- 데이터 흐름 설계가 곧 시스템 안정성이다.
- 예외 처리와 구조 설계가 실제 사용자 안전을 좌우한다.











