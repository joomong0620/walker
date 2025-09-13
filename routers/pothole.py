from fastapi import FastAPI, UploadFile, File, Depends, Query, APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database import get_db, async_session
from model.models import CrackData
from ultralytics import YOLO
from datetime import datetime
import uuid
import numpy as np
import cv2
import asyncio
import threading
import queue
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
router = APIRouter()

# YOLO 모델 로드
model = YOLO("lane_seg_best.pt")
model.fuse()

# 스트리밍 URL
STREAM_URL = "https://bear-hampton-hc-sound.trycloudflare.com/?action=stream"

# 프레임 큐
frame_queue = queue.Queue(maxsize=1)

# 실행 컨트롤
frame_grabber = None
detection_task = None

# 저장 경로
SAVE_DIR_STREAM = "runs/cracks/stream"
SAVE_DIR_UPLOAD = "runs/cracks/upload"


# ================== FrameGrabber ==================
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


# ================== DB 저장 함수 ==================
async def save_to_db_safe(session, crack_id, user_id, crack_type, detection_time, walker_id, is_detected):
    try:
        crack = CrackData(
            crack_id=crack_id,
            user_id=user_id,
            crack_type=crack_type,
            detection_time=detection_time,
            walker_id=walker_id,
            is_detected=is_detected
        )
        session.add(crack)
        await session.commit()
        logger.info(f"✅ DB 저장 성공: {crack_id}")
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ DB 저장 실패: {e}")
        return False


# ================== 감지 루프 ==================
async def detect_from_queue(user_id: str, walker_id: str, db_session_maker):
    logger.info("🧠 감지 루프 시작됨")
    while True:
        start_time = asyncio.get_event_loop().time()
        try:
            frame = frame_queue.get(timeout=5)
        except queue.Empty:
            logger.warning("⏳ 프레임 없음")
            await asyncio.sleep(0.1)
            continue

        t0 = asyncio.get_event_loop().time()
        results = model.predict(frame, conf=0.3, imgsz=224, device="cpu", stream=False)
        logger.info(f"YOLO 추론 시간: {asyncio.get_event_loop().time() - t0:.3f}s")

        labels_all = []
        is_detected = 0
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                confs = boxes.conf.cpu().numpy()
                classes = boxes.cls.cpu().numpy()
                for conf, cls in zip(confs, classes):
                    label = model.names[int(cls)]
                    labels_all.append(label)
                    if conf >= 0.5:
                        is_detected = 1

        label_str = str(labels_all) if labels_all else "[]"
        detection_time = datetime.utcnow()
        crack_id = f"stream_{uuid.uuid4()}"

        async with db_session_maker() as session:
            await save_to_db_safe(
                session,
                crack_id,
                user_id,
                label_str,
                detection_time,
                walker_id,
                is_detected
            )

        logger.info(f"🚨 감지 결과: is_detected={is_detected}, labels={label_str}")
        total_elapsed = asyncio.get_event_loop().time() - start_time
        await asyncio.sleep(max(0, 1.0 - total_elapsed))


# ================== 업로드 감지 API ==================
@router.post("/pothole/upload")
async def upload_image(
    file: UploadFile = File(...),
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        image_bytes = await file.read()
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"error": "이미지를 읽을 수 없음"}

        results = model.predict(frame, conf=0.3, imgsz=224, device="cpu", stream=False)
        labels_all = []
        is_detected = 0

        for result in results:
            boxes = result.boxes
            if boxes is not None:
                confs = boxes.conf.cpu().numpy()
                classes = boxes.cls.cpu().numpy()
                for conf, cls in zip(confs, classes):
                    label = model.names[int(cls)]
                    labels_all.append(label)
                    if conf >= 0.5:
                        is_detected = 1

        label_str = str(labels_all) if labels_all else "[]"
        crack_id = f"upload_{uuid.uuid4()}"
        detection_time = datetime.utcnow()

        success = await save_to_db_safe(
            session=db,
            crack_id=crack_id,
            user_id=user_id,
            crack_type=label_str,
            detection_time=detection_time,
            walker_id=walker_id,
            is_detected=is_detected
        )

        return {
            "message": "이미지 처리 완료",
            "is_detected": is_detected,
            "labels": labels_all,
            "crack_id": crack_id,
            "saved": success
        }
    except Exception as e:
        logger.error(f"Upload 처리 실패: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ================== 스트리밍 시작 ==================
@router.post("/pothole/stream/start")
async def start_detection(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    global frame_grabber, detection_task
    try:
        if frame_grabber and frame_grabber.is_alive():
            frame_grabber.stop()
            frame_grabber.join(timeout=2)
        if detection_task and not detection_task.done():
            detection_task.cancel()

        frame_grabber = FrameGrabber(STREAM_URL)
        frame_grabber.start()

        detection_task = asyncio.create_task(detect_from_queue(user_id, walker_id, async_session))
        logger.info(f"스트리밍 감지 시작됨: user_id={user_id}, walker_id={walker_id}")
        return {"message": "스트리밍 감지를 시작했습니다."}
    except Exception as e:
        return {"error": str(e)}


# ================== 스트리밍 종료 ==================
@router.post("/pothole/stream/stop")
async def stop_detection():
    global frame_grabber, detection_task
    stopped = []
    try:
        if frame_grabber and frame_grabber.is_alive():
            frame_grabber.stop()
            frame_grabber.join(timeout=5)
            stopped.append("frame_grabber")

        if detection_task and not detection_task.done():
            detection_task.cancel()
            try:
                await detection_task
            except asyncio.CancelledError:
                pass
            stopped.append("detection_task")

        if stopped:
            return {"message": f"중지됨: {stopped}"}
        else:
            return {"message": "실행 중이 아님"}
    except Exception as e:
        return {"error": str(e)}


# ================== 상태 확인 ==================
@router.get("/pothole/status")
async def get_detection_status():
    global frame_grabber, detection_task
    return {
        "frame_grabber_running": frame_grabber is not None and frame_grabber.is_alive(),
        "detection_task_running": detection_task is not None and not detection_task.done(),
        "queue_size": frame_queue.qsize()
    }


# ================== 최신 데이터 ==================
@router.get("/pothole/latest")
async def get_latest_crack_data(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(CrackData)
            .where(CrackData.user_id == user_id, CrackData.walker_id == walker_id)
            .order_by(desc(CrackData.detection_time))
            .limit(1)
        )
        latest_data = result.scalar_one_or_none()
        if latest_data:
            return {
                "crack_id": latest_data.crack_id,
                "user_id": latest_data.user_id,
                "walker_id": latest_data.walker_id,
                "crack_type": latest_data.crack_type,
                "detection_time": latest_data.detection_time.isoformat(),
                "is_detected": latest_data.is_detected,
            }
        else:
            return {"message": "데이터가 없습니다."}
    except Exception as e:
        return {"error": str(e)}


# ================== 라우터 등록 ==================
app.include_router(router)
