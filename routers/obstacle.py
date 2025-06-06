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

router = APIRouter()

# YOLO 모델 로드 (경량) - 모델 obstacle_best.pt는 yolov8s.pt 모델이어서, ylolv8n.pt로 변경
model = YOLO("obstacle_best.pt")
model.fuse()

# 스트리밍 URL
STREAM_URL = "http://192.168.0.142:8080/?action=stream"

# 프레임 큐 (최신 프레임 하나만 유지)
frame_queue = queue.Queue(maxsize=1)

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
            print("❌ 카메라 열기 실패")
            return

        print("📸 FrameGrabber 시작됨")
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
        print("🛑 FrameGrabber 종료됨")

# ✅ DB 저장 함수
async def save_to_db_safe(session, obstacle_id, user_id, obstacle_type, detection_time, walker_id, is_detected):
    try:
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
        print("✅ DB 저장 성공")
    except Exception as e:
        await session.rollback()
        print(f"❌ DB 저장 실패: {e}")

# ✅ 감지 루프 (YOLO + DB)
async def detect_from_queue(user_id: str, walker_id: str, db_session_maker):
    print("🧠 감지 루프 시작됨")

    while True:
        start_time = asyncio.get_event_loop().time()

        try:
            frame = frame_queue.get(timeout=5)
        except queue.Empty:
            print("⏳ 프레임 없음")
            await asyncio.sleep(0.1)
            continue

        detect_start = asyncio.get_event_loop().time()
        results = model.predict(frame, conf=0.3, imgsz=224, device="cpu", stream=False)
        detect_elapsed = asyncio.get_event_loop().time() - detect_start
        print(f"🧠 YOLO 추론 시간: {detect_elapsed:.3f}s")

        boxes = results[0].boxes
        high_conf_boxes = [box for box in boxes if box.conf[0] >= 0.85]
        is_detected = 1 if len(high_conf_boxes) > 0 else 0
        print(f"🚨 감지 결과 (0.85 이상): {is_detected}")

        labels = []
        for box in high_conf_boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]
            labels.append(label)

        label_str = str(labels) if labels else "[]"
        detection_time = datetime.utcnow()
        obstacle_id = f"stream_{uuid.uuid4()}"

        # ✅ 감지 여부와 관계없이 무조건 DB 저장
        db_start = asyncio.get_event_loop().time()
        async with db_session_maker() as session:
            await save_to_db_safe(
                session,
                obstacle_id,
                user_id,
                label_str,
                detection_time,
                walker_id,
                is_detected
            )
        db_elapsed = asyncio.get_event_loop().time() - db_start
        print(f"💾 DB 저장 시간: {db_elapsed:.3f}s")

        total_elapsed = asyncio.get_event_loop().time() - start_time
        print(f"🔁 전체 루프 시간: {total_elapsed:.3f}s")
        await asyncio.sleep(max(0, 1.0 - total_elapsed))


# ✅ 감지 시작 API
@router.post("/obstacle/stream/start")
async def start_detection(user_id: str, walker_id: str, db: AsyncSession = Depends(get_db)):
    # 프레임 캡쳐 스레드 시작
    global frame_grabber
    frame_grabber = FrameGrabber(STREAM_URL)
    frame_grabber.start()

    # 감지 루프 시작
    asyncio.create_task(detect_from_queue(user_id, walker_id, async_session))
    return {"message": "스트리밍 감지를 시작했습니다."}

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
        return {"error": str(e)}
    
@router.post("/obstacle/upload")
async def upload_obstacle_image(
    file: UploadFile = File(...),
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        image_bytes = await file.read()
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        results = model.predict(frame, conf=0.3, imgsz=224, device="cpu", stream=False)
        boxes = results[0].boxes
        high_conf_boxes = [box for box in boxes if box.conf[0] >= 0.50]
        is_detected = 1 if len(high_conf_boxes) > 0 else 0
        print(f"🚨 (업로드) 감지 결과 (0.50 이상): {is_detected}")

        labels = []
        for box in high_conf_boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]
            labels.append(label)

        label_str = str(labels) if labels else "[]"
        detection_time = datetime.utcnow()
        obstacle_id = f"upload_{uuid.uuid4()}"

        # ✅ 감지 여부와 관계없이 무조건 DB 저장
        await save_to_db_safe(
            session=db,
            obstacle_id=obstacle_id,
            user_id=user_id,
            obstacle_type=label_str,
            detection_time=detection_time,
            walker_id=walker_id,
            is_detected=is_detected
        )

        return {"message": "업로드 이미지 처리 완료", "is_detected": is_detected}

    except Exception as e:
        return {"error": str(e)}
