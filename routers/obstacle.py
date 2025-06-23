from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database import get_db, async_session
from model.models import ObstacleData
from ultralytics import YOLO
from datetime import datetime
import uuid
import cv2
import asyncio
import threading
import queue
import numpy as np
from fastapi import UploadFile, File
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# YOLO 모델 로드 (경량) - 모델 obstacle_best.pt는 yolov8s.pt 모델이어서, ylolv8n.pt로 변경
model = YOLO("obstacle_best.pt")
model.fuse()

# 스트리밍 URL
STREAM_URL = "http://192.168.0.142:8080/?action=stream"

# 프레임 큐 (최신 프레임 하나만 유지)
frame_queue = queue.Queue(maxsize=1)

# 전역 변수 초기화
frame_grabber = None
detection_task = None

# 프레임 캡쳐 스레드
class FrameGrabber(threading.Thread):
    def __init__(self, stream_url):
        super().__init__()
        self.stream_url = stream_url
        self.cap = cv2.VideoCapture(self.stream_url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.running = True

    def run(self):
        if not self.cap.isOpened():
            logger.error("❌ 카메라 열기 실패")
            return

        logger.info("📸 FrameGrabber 시작됨")
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            # 기존 프레임 버리기
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
            frame_queue.put(frame)

    def stop(self):
        self.running = False
        self.cap.release()
        logger.info("🛑 FrameGrabber 종료됨")

# ✅ DB 저장 함수 (수정됨)
async def save_to_db_safe(obstacle_id, user_id, obstacle_type, detection_time, walker_id, is_detected):
    """DB에 안전하게 저장하는 함수"""
    try:
        # 새로운 세션 생성
        async with async_session() as session:
            obstacle = ObstacleData(
                obstacle_id=obstacle_id,
                user_id=user_id,
                obstacle_type=obstacle_type,
                detection_time=detection_time,
                walker_id=walker_id,
                is_detected=is_detected
            )
            session.add(obstacle)
            await session.commit()
            logger.info(f"✅ DB 저장 성공: {obstacle_id}")
            return True
    except Exception as e:
        logger.error(f"❌ DB 저장 실패: {e}")
        return False

# ✅ 감지 루프 (YOLO + DB) - 수정됨
async def detect_from_queue(user_id: str, walker_id: str):
    """프레임 큐에서 이미지를 가져와서 감지하고 DB에 저장"""
    logger.info("🧠 감지 루프 시작됨")

    while True:
        start_time = asyncio.get_event_loop().time()

        try:
            # 프레임 가져오기 (타임아웃 5초)
            frame = frame_queue.get(timeout=5)
        except queue.Empty:
            logger.warning("⏳ 프레임 없음")
            await asyncio.sleep(0.1)
            continue

        try:
            # YOLO 감지
            detect_start = asyncio.get_event_loop().time()
            results = model.predict(frame, conf=0.3, imgsz=224, device="cpu", stream=False)
            detect_elapsed = asyncio.get_event_loop().time() - detect_start
            logger.info(f"🧠 YOLO 추론 시간: {detect_elapsed:.3f}s")

            # 결과 처리
            boxes = results[0].boxes
            high_conf_boxes = [box for box in boxes if box.conf[0] >= 0.2]
            is_detected = 1 if len(high_conf_boxes) > 0 else 0
            logger.info(f"🚨 감지 결과 (0.2 이상): {is_detected}")

            # 라벨 추출
            labels = []
            for box in high_conf_boxes:
                class_id = int(box.cls[0])
                label = model.names[class_id]
                labels.append(label)

            label_str = str(labels) if labels else "[]"
            detection_time = datetime.utcnow()
            obstacle_id = f"stream_{uuid.uuid4()}"

            # DB 저장
            db_start = asyncio.get_event_loop().time()
            success = await save_to_db_safe(
                obstacle_id,
                user_id,
                label_str,
                detection_time,
                walker_id,
                is_detected
            )
            db_elapsed = asyncio.get_event_loop().time() - db_start
            
            if success:
                logger.info(f"💾 DB 저장 시간: {db_elapsed:.3f}s")
            else:
                logger.error("💾 DB 저장 실패")

        except Exception as e:
            logger.error(f"❌ 감지 루프 오류: {e}")

        # 전체 루프 시간 계산 및 대기
        total_elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"🔁 전체 루프 시간: {total_elapsed:.3f}s")
        await asyncio.sleep(max(0, 1.0 - total_elapsed))

# ✅ 감지 시작 API (수정됨)
@router.post("/obstacle/stream/start")
async def start_detection(user_id: str, walker_id: str, db: AsyncSession = Depends(get_db)):
    global frame_grabber, detection_task
    
    try:
        # 기존 감지가 실행 중이면 중지
        if frame_grabber and frame_grabber.is_alive():
            frame_grabber.stop()
            frame_grabber.join(timeout=2)
        
        if detection_task and not detection_task.done():
            detection_task.cancel()

        # 프레임 캡쳐 스레드 시작
        frame_grabber = FrameGrabber(STREAM_URL)
        frame_grabber.start()

        # 감지 루프 시작
        detection_task = asyncio.create_task(detect_from_queue(user_id, walker_id))
        
        logger.info(f"🚀 스트리밍 감지 시작 - user_id: {user_id}, walker_id: {walker_id}")
        return {"message": "스트리밍 감지를 시작했습니다.", "user_id": user_id, "walker_id": walker_id}
        
    except Exception as e:
        logger.error(f"❌ 감지 시작 실패: {e}")
        return {"error": f"감지 시작 실패: {str(e)}"}

# ✅ 최신 감지 결과 반환 API
@router.get("/obstacle/latest")
async def get_latest_obstacle_data(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(ObstacleData)
            .where(ObstacleData.user_id == user_id, ObstacleData.walker_id == walker_id)
            .order_by(desc(ObstacleData.detection_time))
            .limit(1)
        )
        latest_data = result.scalar_one_or_none()

        if latest_data:
            return {
                "obstacle_id": latest_data.obstacle_id,
                "user_id": latest_data.user_id,
                "walker_id": latest_data.walker_id,
                "obstacle_type": latest_data.obstacle_type,
                "detection_time": latest_data.detection_time.isoformat(),
                "is_detected": latest_data.is_detected,
            }
        else:
            return {"message": "데이터가 없습니다."}
    except Exception as e:
        logger.error(f"❌ 최신 데이터 조회 실패: {e}")
        return {"error": str(e)}

# ✅ 이미지 업로드 감지 API (수정됨)
@router.post("/obstacle/upload")
async def upload_obstacle_image(
    file: UploadFile = File(...),
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        # 이미지 읽기
        image_bytes = await file.read()
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return {"error": "이미지를 읽을 수 없습니다."}

        # YOLO 감지
        results = model.predict(frame, conf=0.3, imgsz=224, device="cpu", stream=False)
        boxes = results[0].boxes
        high_conf_boxes = [box for box in boxes if box.conf[0] >= 0.50]
        is_detected = 1 if len(high_conf_boxes) > 0 else 0
        logger.info(f"🚨 (업로드) 감지 결과 (0.50 이상): {is_detected}")

        # 라벨 추출
        labels = []
        for box in high_conf_boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]
            labels.append(label)

        label_str = str(labels) if labels else "[]"
        detection_time = datetime.utcnow()
        obstacle_id = f"upload_{uuid.uuid4()}"

        # DB 저장 (수정된 방식)
        obstacle = ObstacleData(
            obstacle_id=obstacle_id,
            user_id=user_id,
            obstacle_type=label_str,
            detection_time=detection_time,
            walker_id=walker_id,
            is_detected=is_detected
        )
        
        db.add(obstacle)
        await db.commit()
        await db.refresh(obstacle)
        
        logger.info(f"✅ 업로드 이미지 DB 저장 성공: {obstacle_id}")
        return {
            "message": "업로드 이미지 처리 완료", 
            "is_detected": is_detected,
            "obstacle_id": obstacle_id,
            "labels": labels
        }

    except Exception as e:
        logger.error(f"❌ 업로드 이미지 처리 실패: {e}")
        await db.rollback()
        return {"error": str(e)}
    
# ✅ 감지 중지 API (수정됨)
@router.post("/obstacle/stream/stop")
async def stop_detection():
    global frame_grabber, detection_task
    
    try:
        stopped_components = []
        
        # 프레임 캡쳐 스레드 중지
        if frame_grabber and frame_grabber.is_alive():
            frame_grabber.stop()
            frame_grabber.join(timeout=5)  # 최대 5초 대기
            stopped_components.append("frame_grabber")
        
        # 감지 태스크 중지
        if detection_task and not detection_task.done():
            detection_task.cancel()
            try:
                await detection_task
            except asyncio.CancelledError:
                pass
            stopped_components.append("detection_task")
        
        if stopped_components:
            logger.info(f"🛑 중지된 컴포넌트: {stopped_components}")
            return {"message": f"스트리밍 감지를 중지했습니다. 중지된 컴포넌트: {stopped_components}"}
        else:
            return {"message": "감지 스레드가 실행 중이 아닙니다."}
            
    except Exception as e:
        logger.error(f"❌ 감지 중지 실패: {e}")
        return {"error": f"감지 중지 실패: {str(e)}"}

# ✅ 상태 확인 API (추가)
@router.get("/obstacle/status")
async def get_detection_status():
    """현재 감지 상태를 확인하는 API"""
    global frame_grabber, detection_task
    
    status = {
        "frame_grabber_running": frame_grabber is not None and frame_grabber.is_alive(),
        "detection_task_running": detection_task is not None and not detection_task.done(),
        "queue_size": frame_queue.qsize()
    }
    
    return status