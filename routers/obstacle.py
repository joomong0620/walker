from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse
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
import logging
import os
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# YOLO 모델 로드
model = YOLO("obsUpper.pt")
model.fuse()

# 스트리밍 URL
STREAM_URL = "http://192.168.0.142:8080/?action=stream"

# 프레임 큐 (최신 프레임 하나만 유지)
frame_queue = queue.Queue(maxsize=1)

# 전역 실행 컨트롤
frame_grabber = None
detection_task = None

# 저장 경로
SAVE_DIR_STREAM = "runs/obstacles/stream"
SAVE_DIR_UPLOAD = "runs/obstacles/upload"


def draw_boxes(frame, boxes, labels):
    """프레임 위에 바운딩 박스와 라벨을 그림(저장 안 함). np.ndarray 반환."""
    annotated = frame.copy()
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf = float(box.conf[0])
        pt1 = (int(x1), int(y1))
        pt2 = (int(x2), int(y2))
        cv2.rectangle(annotated, pt1, pt2, (0, 255, 0), 2)
        label_text = labels[i] if i < len(labels) else "obj"
        text = f"{label_text} {conf:.2f}"
        cv2.putText(
            annotated, text, (pt1[0], max(0, pt1[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA
        )
    return annotated


def draw_and_save(frame, boxes, labels, save_dir, filename_prefix):
    """프레임 위에 바운딩 박스를 그리고 디스크에 저장."""
    os.makedirs(save_dir, exist_ok=True)
    annotated = draw_boxes(frame, boxes, labels)
    out_path = os.path.join(save_dir, f"{filename_prefix}.jpg")
    cv2.imwrite(out_path, annotated)
    return out_path


class FrameGrabber(threading.Thread):
    def __init__(self, stream_url):
        super().__init__()
        self.stream_url = stream_url
        self.cap = cv2.VideoCapture(self.stream_url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.running = True

    def run(self):
        if not self.cap.isOpened():
            logger.error("Failed to open camera.")
            return
        logger.info("FrameGrabber started.")
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
        logger.info("FrameGrabber stopped.")


async def save_to_db_safe(obstacle_id, user_id, obstacle_type, detection_time, walker_id, is_detected):
    """DB에 안전하게 저장."""
    try:
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
            logger.info(f"Saved to DB: {obstacle_id}")
            return True
    except Exception as e:
        logger.error(f"DB save failed: {e}")
        return False


async def detect_from_queue(user_id: str, walker_id: str):
    """프레임 큐에서 이미지를 가져와 감지하고 DB에 저장."""
    logger.info("Detection loop started.")
    while True:
        start_time = asyncio.get_event_loop().time()
        try:
            frame = frame_queue.get(timeout=5)
        except queue.Empty:
            logger.warning("No frame available.")
            await asyncio.sleep(0.1)
            continue

        try:
            t0 = asyncio.get_event_loop().time()
            results = model.predict(frame, conf=0.3, imgsz=224, device="cpu", stream=False)
            logger.info(f"YOLO infer time: {asyncio.get_event_loop().time() - t0:.3f}s")

            boxes = results[0].boxes
            high_conf_boxes = [box for box in boxes if box.conf[0] >= 0.6]
            is_detected = 1 if len(high_conf_boxes) > 0 else 0
            logger.info(f"Detected (>=0.6): {is_detected}")

            labels = []
            for box in high_conf_boxes:
                class_id = int(box.cls[0])
                label = model.names[class_id]
                labels.append(label)

            label_str = str(labels) if labels else "[]"
            detection_time = datetime.utcnow()
            obstacle_id = f"stream_{uuid.uuid4()}"

            if is_detected == 1:
                try:
                    saved_image_path = draw_and_save(
                        frame=frame,
                        boxes=high_conf_boxes,
                        labels=labels,
                        save_dir=SAVE_DIR_STREAM,
                        filename_prefix=obstacle_id
                    )
                    logger.info(f"Saved stream annotated image: {saved_image_path}")
                except Exception as e:
                    logger.error(f"Stream image save failed: {e}")

            t1 = asyncio.get_event_loop().time()
            success = await save_to_db_safe(
                obstacle_id, user_id, label_str, detection_time, walker_id, is_detected
            )
            logger.info(f"DB save time: {asyncio.get_event_loop().time() - t1:.3f}s" if success else "DB save error")
        except Exception as e:
            logger.error(f"Detection loop error: {e}")

        total_elapsed = asyncio.get_event_loop().time() - start_time
        await asyncio.sleep(max(0, 1.0 - total_elapsed))


@router.post("/obstacle/stream/start")
async def start_detection(user_id: str, walker_id: str, db: AsyncSession = Depends(get_db)):
    global frame_grabber, detection_task
    try:
        if frame_grabber and frame_grabber.is_alive():
            frame_grabber.stop()
            frame_grabber.join(timeout=2)
        if detection_task and not detection_task.done():
            detection_task.cancel()

        frame_grabber = FrameGrabber(STREAM_URL)
        frame_grabber.start()

        detection_task = asyncio.create_task(detect_from_queue(user_id, walker_id))
        logger.info(f"Stream detection started: user_id={user_id}, walker_id={walker_id}")
        return {"message": "Stream detection started.", "user_id": user_id, "walker_id": walker_id}
    except Exception as e:
        logger.error(f"Failed to start detection: {e}")
        return {"error": f"start failed: {str(e)}"}


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
            return {"message": "No data."}
    except Exception as e:
        logger.error(f"Latest query failed: {e}")
        return {"error": str(e)}


@router.post("/obstacle/upload")
async def upload_obstacle_image(
    file: UploadFile = File(...),
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """업로드한 이미지를 감지하고, 감지된 경우에만 디스크에 저장 + DB 기록 + JSON 반환."""
    try:
        image_bytes = await file.read()
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"error": "Failed to read image."}

        results = model.predict(frame, conf=0.3, imgsz=224, device="cpu", stream=False)
        boxes = results[0].boxes
        high_conf_boxes = [box for box in boxes if box.conf[0] >= 0.7]

        bbox_list = []
        for box in high_conf_boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bbox_list.append({"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)})

        is_detected = 1 if len(high_conf_boxes) > 0 else 0
        logger.info(f"(upload) detected(>=0.7): {is_detected}")

        labels = []
        for box in high_conf_boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]
            labels.append(label)

        label_str = str(labels) if labels else "[]"
        detection_time = datetime.utcnow()
        obstacle_id = f"upload_{uuid.uuid4()}"

        saved_image_path = None
        if is_detected == 1:
            try:
                saved_image_path = draw_and_save(
                    frame=frame,
                    boxes=high_conf_boxes,
                    labels=labels,
                    save_dir=SAVE_DIR_UPLOAD,
                    filename_prefix=obstacle_id
                )
                logger.info(f"Saved upload annotated image: {saved_image_path}")
            except Exception as e:
                logger.error(f"(upload) image save failed: {e}")

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

        return {
            "message": "Processed upload image.",
            "is_detected": is_detected,
            "obstacle_id": obstacle_id,
            "labels": labels,
            "boxes": bbox_list,
            "saved_image_path": saved_image_path
        }
    except Exception as e:
        logger.error(f"Upload processing failed: {e}")
        await db.rollback()
        return {"error": str(e)}


@router.post("/obstacle/upload/preview")
async def upload_obstacle_preview(
    file: UploadFile = File(...),
    user_id: str = Query(...),
    walker_id: str = Query(...),
):
    """
    업로드 이미지를 감지하고, 바운딩 박스가 그려진 이미지를 즉시 JPEG로 반환.
    디스크 저장 및 DB 기록은 하지 않음(미리보기 용).
    감지가 없으면 원본 이미지를 반환.
    """
    try:
        image_bytes = await file.read()
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"error": "Failed to read image."}

        results = model.predict(frame, conf=0.3, imgsz=224, device="cpu", stream=False)
        boxes = results[0].boxes
        high_conf_boxes = [box for box in boxes if box.conf[0] >= 0.7]

        labels = []
        for box in high_conf_boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]
            labels.append(label)

        if len(high_conf_boxes) > 0:
            annotated = draw_boxes(frame, high_conf_boxes, labels)
        else:
            annotated = frame

        ok, buffer = cv2.imencode(".jpg", annotated)
        if not ok:
            return {"error": "Failed to encode image."}

        return StreamingResponse(io.BytesIO(buffer.tobytes()), media_type="image/jpeg")
    except Exception as e:
        logger.error(f"Preview generation failed: {e}")
        return {"error": str(e)}


@router.post("/obstacle/stream/stop")
async def stop_detection():
    global frame_grabber, detection_task
    try:
        stopped = []
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
            logger.info(f"Stopped components: {stopped}")
            return {"message": f"Stopped: {stopped}"}
        else:
            return {"message": "Nothing was running."}
    except Exception as e:
        logger.error(f"Stop failed: {e}")
        return {"error": f"stop failed: {str(e)}"}


@router.get("/obstacle/status")
async def get_detection_status():
    """현재 감지 상태를 확인."""
    global frame_grabber, detection_task
    status = {
        "frame_grabber_running": frame_grabber is not None and frame_grabber.is_alive(),
        "detection_task_running": detection_task is not None and not detection_task.done(),
        "queue_size": frame_queue.qsize()
    }
    return status
