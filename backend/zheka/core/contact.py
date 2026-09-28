import hashlib
import hmac
from datetime import datetime, timedelta

from zheka.core.errors import InvalidRequest

CONTACT_TTL = timedelta(days=1)
CLOCK_SKEW = timedelta(minutes=1)
MILLISECONDS_FROM = 10**12
PHONE_DIGITS = range(10, 16)
BAD_CONTACT = "Номер не подтвержден MAX, попробуйте еще раз"


def verify_bridge_contact(
    phone: str,
    auth_date: str,
    signature: str,
    max_user_id: int,
    token: str,
    now: datetime,
) -> str:
    digits = phone.strip().removeprefix("+")
    signed = f"authDate={auth_date}\nphone={digits}\nuserId={max_user_id}"
    expected = hmac.new(token.encode(), signed.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.strip().lower()):
        raise InvalidRequest(BAD_CONTACT)
    if not auth_date.isdecimal():
        raise InvalidRequest(BAD_CONTACT)
    stamp = int(auth_date)
    seconds = stamp / 1000 if stamp >= MILLISECONDS_FROM else stamp
    age = now - datetime.fromtimestamp(seconds, now.tzinfo)
    if age > CONTACT_TTL or age < -CLOCK_SKEW:
        raise InvalidRequest(BAD_CONTACT)
    if not digits.isdecimal() or len(digits) not in PHONE_DIGITS:
        raise InvalidRequest(BAD_CONTACT)
    return f"+{digits}"
