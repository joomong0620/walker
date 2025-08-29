from fastapi import FastAPI, UploadFile, File, Depends, Query, APIRouter
from fastapi.responses import JSONResponse
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

app = FastAPI()
router = APIRouter()

# YOLO 모델 로드
model = YOLO("lane_seg_best.pt")
model.fuse()

# 스트리밍 URL
STREAM_URL = "https://bear-hampton-hc-sound.trycloudflare.com/?action=stream"

# 프레임 큐
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
    except Exception as e:
        await session.rollback()
        print(f"❌ DB 저장 실패: {e}")

# ✅ 실시간 감지 루프
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
        print(f"🚨 감지 결과: is_detected={is_detected}, labels={label_str}")

        detection_time = datetime.utcnow()
        crack_id = f"crack_{uuid.uuid4()}"

        db_start = asyncio.get_event_loop().time()
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
        db_elapsed = asyncio.get_event_loop().time() - db_start

        if is_detected:
            print(f"✅ DB 저장 성공 (0.5 이상 감지!) - 저장 시간: {db_elapsed:.3f}s")
        else:
            print(f"✅ DB 저장 성공 (0.5 미만) - 저장 시간: {db_elapsed:.3f}s")

        total_elapsed = asyncio.get_event_loop().time() - start_time
        print(f"🔁 전체 루프 시간: {total_elapsed:.3f}s")
        await asyncio.sleep(max(0, 1.0 - total_elapsed))

# ✅ 이미지 업로드 감지 API
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
        print(f"🚨 감지 결과: is_detected={is_detected}, labels={label_str}")

        crack_id = f"crack_{uuid.uuid4()}"
        detection_time = datetime.utcnow()

        await save_to_db_safe(
            session=db,
            crack_id=crack_id,
            user_id=user_id,
            crack_type=label_str,
            detection_time=detection_time,
            walker_id=walker_id,
            is_detected=is_detected
        )

        return {"message": "이미지 처리 완료", "is_detected": is_detected}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ✅ 실시간 감지 시작 API
@router.post("/pothole/stream/start")
async def start_detection(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    global frame_grabber
    frame_grabber = FrameGrabber(STREAM_URL)
    frame_grabber.start()

    asyncio.create_task(detect_from_queue(user_id, walker_id, async_session))
    return {"message": "스트리밍 감지를 시작했습니다."}

# ✅ 최신 감지 결과 API
@app.get("/pothole/latest")
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

# ✅ 라우터 등록
app.include_router(router)
