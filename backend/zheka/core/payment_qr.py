import re
from typing import Self

from zheka.base import ZhekaType
from zheka.core.errors import InvalidRequest

NOT_PAYMENT_QR = "Это не платежный QR квитанции"
ENCODINGS = {"1": "cp1251", "2": "utf-8", "3": "koi8-r"}


class PaymentQr(ZhekaType):
    name: str | None
    payee_inn: str | None
    pers_acc: str | None
    payer_address: str | None

    @classmethod
    def parse(cls, raw: str) -> Self:
        text = raw.strip()
        header = re.match(r"ST0001([123])\|", text)
        if header is None:
            raise InvalidRequest(NOT_PAYMENT_QR)

        fields: dict[str, str] = {}
        for field in _redecoded(text, ENCODINGS[header[1]]).split("|")[1:]:
            key, _, value = field.partition("=")
            fields[key.strip().casefold()] = value.strip()
        return cls(
            name=fields.get("name") or None,
            payee_inn=fields.get("payeeinn") or None,
            pers_acc=fields.get("persacc") or None,
            payer_address=fields.get("payeraddress") or None,
        )


def _redecoded(text: str, encoding: str) -> str:
    for codec in ("latin-1", "cp1252"):
        try:
            return text.encode(codec).decode(encoding)
        except UnicodeError:
            continue
    return text
