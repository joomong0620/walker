# 고령자를 위한 AI 기반 스마트 안전 보행기 시스템 - 길벗이

----

## 📂 프로젝트 소개
노인 또는 거동이 불편한 모든 사람을 타겟으로 AI· 센서 데이터와 실시간 안전 관리를 기반한 안전한 보행 가능 시스템을 만드는 프로젝트 입니다. 

## 🕰️ 개발 기간
* 24.09.02일 ~ 25.09.17일


### 👩‍💻 멤버구성
- 김주연(팀장, Backend) : 데이터베이스 설계, 데이터베이스 구축 및 연동, API 서버 구축 및 배포, AI 인식 시스템 개발
- 이어진(HardWare) : 보행기 하드웨어 구성 및 회로 설계, 센서 데이터 처리 및 연동 구현, 하드웨어 기반 경고 시스템 구현, 프로토타입 제작 및 테스트 주도
- 유예린(AI) : 장애물 인식 AI 모델 제작, 차선 및 횡단보도와 포트홀 인식 AI 모델 제작 
- 김우주(Frontend) : 애플리케이션 디자인 및 제작, 서버 및 하드웨어 연동
- Kosimov(Frontend) : 웹 대시보드 화면 구성 및 제작, 음성 알림 경고 제작  


### ⚙️개발 환경
- **Language**: Python 3.12  
- **Backend Framework**: FastAPI  
- **AI / Computer Vision**: YOLOv8, OpenCV  
- **Database**: PostgreSQL    
- **Server / Infra**: Railway (CI/CD), Docker, Uvicorn (ASGI)  
- **Streaming**: Real-time video processing (OpenCV + Queue)   


## 📌 주요 기능
#### DB 구축 - [상세 보기 - WIKI 이동](https://github.com/joomong0620/walker/wiki/%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C(DB-%EA%B5%AC%EC%B6%95))
- Postgree DB 구축


#### API 구축 - [상세 보기 - WIKI 이동](https://github.com/joomong0620/walker/wiki/%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C(API-%EA%B5%AC%EC%B6%95))
- 활동시간, 심박수
- 레포트 평균 데이터
- 실시간 감지 API

  
#### AI 위험 감지 및 경고 시스템 - [상세 보기 - WIKI 이동](https://github.com/joomong0620/walker/wiki/%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C(AI-%EC%9C%84%ED%97%98-%EA%B0%90%EC%A7%80-%EB%B0%8F-%EA%B2%BD%EA%B3%A0-%EC%8B%9C%EC%8A%A4%ED%85%9C))
- YOLO 감지 로직
- BASE RISK TABLE 위험도 계산 로직
- 알림 레벨 (STOP/SLOW/CAUTION/NORMAL) 분류 로직


#### 서버 배포 - [상세 보기 - WIKI 이동](https://github.com/joomong0620/walker/wiki/%EC%A3%BC%EC%9A%94-%EA%B8%B0%EB%8A%A5-%EC%86%8C%EA%B0%9C(%EC%84%9C%EB%B2%84-%EB%B0%B0%ED%8F%AC))
- docker 컨테이너화
- Railway 배포 및 호스팅












