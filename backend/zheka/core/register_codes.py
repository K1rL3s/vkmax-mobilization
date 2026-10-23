import hashlib
import hmac
import secrets
from base64 import urlsafe_b64encode

from zheka.core.ids import OrgId


def org_register_code(secret: str, org_id: OrgId) -> str:
    return f"{org_id}-{_signature(secret, org_id)}"


def is_shared_register_code(secret: str, code: str) -> bool:
    return code.isascii() and secrets.compare_digest(code, secret)


def signed_register_org(secret: str, code: str) -> OrgId | None:
    raw_id, _, signature = code.partition("-")
    if not code.isascii() or not raw_id.isdecimal():
        return None
    org_id = OrgId(int(raw_id))
    if not secrets.compare_digest(signature, _signature(secret, org_id)):
        return None
    return org_id


def _signature(secret: str, org_id: OrgId) -> str:
    digest = hmac.new(
        secret.encode(),
        f"org-register:{org_id}".encode(),
        hashlib.sha256,
    ).digest()
    return urlsafe_b64encode(digest).decode().rstrip("=")[:22]
