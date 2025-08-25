# utils/sms.py
import os
from solapi import Message

API_KEY = os.getenv("SOLAPI_API_KEY")
API_SECRET = os.getenv("SOLAPI_API_SECRET")
SMS_FROM = os.getenv("SMS_FROM")  # 사전 인증된 발신번호(숫자만)

if not API_KEY or not API_SECRET or not SMS_FROM:
    raise RuntimeError("SOLAPI_API_KEY / SOLAPI_API_SECRET / SMS_FROM 환경변수를 확인하세요.")

_client = Message(API_KEY, API_SECRET)

def send_sms_sync(to: str, text: str, _from: str | None = None) -> dict:
    """
    동기 발송. FastAPI에서는 BackgroundTasks로 호출 권장.
    to/from: 반드시 숫자만 전달(하이픈 제거). (-) 금지. 
    """
    payload = {
        "to": to.replace("-", ""),
        "from": (_from or SMS_FROM).replace("-", ""),
        "text": text,
        # 길이에 따라 SMS/LMS 자동 판정. 필요하면 "type": "SMS" 강제 가능.
    }
    return _client.send(payload)
