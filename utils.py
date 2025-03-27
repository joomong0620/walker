# utils.py
from sqlalchemy.ext.declarative import DeclarativeMeta

def sqlalchemy_to_dict(obj):
    """
    SQLAlchemy 객체를 dict로 변환
    """
    if not isinstance(obj.__class__, DeclarativeMeta):
        raise ValueError("Provided object is not a SQLAlchemy model")

    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}

def detect_abnormal_heartrate(heartrate):
    """
    심박수 이상 여부를 확인
    """
    normal_range = (60, 100)  # 정상 심박수 범위
    if heartrate < normal_range[0]:
        return "low"
    elif heartrate > normal_range[1]:
        return "high"
    return "normal"
