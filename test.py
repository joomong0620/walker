# test.py

from dotenv import load_dotenv
import os

load_dotenv()  # 👈 반드시 먼저 호출돼야 함

print("✅ DATABASE_URL = ", repr(os.getenv("DATABASE_URL")))
