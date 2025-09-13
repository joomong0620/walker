from fastapi import FastAPI, UploadFile, File, Depends, Query, APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse
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

# YOLO 모델 로드 (세그멘테이션 지원 모델)
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


# ================== 이미지 저장 유틸 ==================
def draw_with_polygons(frame, result):
    """YOLO 결과를 바운딩박스 + 폴리곤 라인으로 그린 프레임 반환"""
    annotated = frame.copy()

    # 1. 바운딩 박스
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf = float(box.conf[0])
        cls = int(box.cls[0])
        label = model.names[cls]

        pt1, pt2 = (int(x1), int(y1)), (int(x2), int(y2))
        cv2.rectangle(annotated, pt1, pt2, (0, 255, 0), 2)
        cv2.putText(
            annotated, f"{label} {conf:.2f}",
            (pt1[0], max(0, pt1[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA
        )

    # 2. 세그멘테이션 폴리곤
    if result.masks is not None:
        for seg in result.masks.xy:
            pts = np.array(seg, dtype=np.int32)
            cv2.polylines(annotated, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
            # 내부 채우려면 아래 사용:
            # cv2.fillPoly(annotated, [pts], color=(0, 0, 255))

    return annotated


def save_annotated(frame, result, save_dir, filename_prefix):
    os.makedirs(save_dir, exist_ok=True)
    annotated = draw_with_polygons(frame, result)
    out_path = os.path.join(save_dir, f"{filename_prefix}.jpg")
    cv2.imwrite(out_path, annotated)
    return out_path


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

        labels_all, high_conf_boxes = [], []
        is_detected = 0
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    label = model.names[cls]
                    labels_all.append(label)
                    if conf >= 0.5:
                        is_detected = 1
                        high_conf_boxes.append(box)

        label_str = str(labels_all) if labels_all else "[]"
        detection_time = datetime.utcnow()
        crack_id = f"stream_{uuid.uuid4()}"

        # ✅ 감지되면 이미지 저장
        if is_detected == 1:
            try:
                saved_image_path = save_annotated(frame, results[0], SAVE_DIR_STREAM, crack_id)
                logger.info(f"스트리밍 이미지 저장: {saved_image_path}")
            except Exception as e:
                logger.error(f"스트리밍 이미지 저장 실패: {e}")

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
        labels_all, high_conf_boxes = [], []
        is_detected = 0

        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    label = model.names[cls]
                    labels_all.append(label)
                    if conf >= 0.5:
                        is_detected = 1
                        high_conf_boxes.append(box)

        label_str = str(labels_all) if labels_all else "[]"
        crack_id = f"upload_{uuid.uuid4()}"
        detection_time = datetime.utcnow()

        # ✅ 감지되면 Annotated 이미지 저장
        saved_image_path = None
        if is_detected == 1:
            saved_image_path = save_annotated(frame, results[0], SAVE_DIR_UPLOAD, crack_id)

        # ✅ DB 저장
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
            "saved_image_path": saved_image_path,
            "saved": success
        }
    except Exception as e:
        logger.error(f"Upload 처리 실패: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ================== 저장된 이미지 반환 API ==================
@router.get("/pothole/image/{crack_id}")
async def get_crack_image(crack_id: str):
    """저장된 균열 이미지를 반환"""
    try:
        upload_path = os.path.join(SAVE_DIR_UPLOAD, f"{crack_id}.jpg")
        if os.path.exists(upload_path):
            return FileResponse(upload_path, media_type="image/jpeg")

        stream_path = os.path.join(SAVE_DIR_STREAM, f"{crack_id}.jpg")
        if os.path.exists(stream_path):
            return FileResponse(stream_path, media_type="image/jpeg")

        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"이미지 반환 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
