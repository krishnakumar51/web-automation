# app/curp_utils.py
import random, string
from datetime import datetime

def gen_password(n=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(alphabet) for _ in range(n))

def gen_email_from_curp(curp: str, domain="outlook.com"):
    # deterministic-ish + random suffix
    core = (curp[:4].lower() if curp else "user")
    suffix = random.randint(100, 999)
    return f"{core}{suffix}@{domain}"
