import pytest
from pydantic import TypeAdapter, ValidationError

from zheka.api.schemas.flats import VerifyFlatByQrRequest, VerifyFlatRequest
from zheka.core.errors import InvalidRequest
from zheka.core.payment_qr import NOT_PAYMENT_QR, PaymentQr

NAME = "Демо-УК “Жэка Коммуналкин” №1"
ADDRESS = "г. Москва, ул. Демо, д. 1, кв. 12"


def test_reads_the_fields_by_any_key_case() -> None:
    qr = PaymentQr.parse(
        f" ST00012|NAME={NAME}|payeeinn=9900000001|PersAcc= 0000000012 "
        f"|PAYERADDRESS={ADDRESS}|Sum=150000 ",
    )

    assert qr == PaymentQr(
        name=NAME,
        payee_inn="9900000001",
        pers_acc="0000000012",
        payer_address=ADDRESS,
    )


@pytest.mark.parametrize("scanner_codec", ["latin-1", "cp1252"])
def test_repairs_cp1251_read_by_the_scanner_as_a_western_codec(
    scanner_codec: str,
) -> None:
    raw = f"ST00011|Name={NAME}|persAcc=0000000012|payerAddress={ADDRESS}"

    qr = PaymentQr.parse(raw.encode("cp1251").decode(scanner_codec))

    assert qr.name == NAME
    assert qr.payer_address == ADDRESS
    assert qr.pers_acc == "0000000012"


@pytest.mark.parametrize("flag", ["1", "2"])
def test_keeps_a_correctly_decoded_string(flag: str) -> None:
    qr = PaymentQr.parse(f"ST0001{flag}|Name={NAME}|persAcc=0000000012")

    assert qr.name == NAME


def test_repairs_utf8_read_by_the_scanner_as_latin1() -> None:
    raw = f"ST00012|Name={NAME}|persAcc=0000000012"

    qr = PaymentQr.parse(raw.encode().decode("latin-1"))

    assert qr.name == NAME


@pytest.mark.parametrize(
    "raw",
    [
        "https://vkmax.k1rles.ru/",
        "persAcc=0000000012",
        "ST00012",
        "ST00014|persAcc=0000000012",
        "ST00022|persAcc=0000000012",
    ],
)
def test_refuses_a_qr_that_is_not_a_gost_payment_one(raw: str) -> None:
    with pytest.raises(InvalidRequest, match=NOT_PAYMENT_QR):
        PaymentQr.parse(raw)


def test_leaves_a_missing_or_empty_account_empty() -> None:
    assert PaymentQr.parse(f"ST00012|Name={NAME}|persAcc=").pers_acc is None
    assert PaymentQr.parse(f"ST00012|Name={NAME}").pers_acc is None


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"account_no": "0000000012", "payment_qr": "ST00012|persAcc=0000000012"},
        {"payment_qr": "ST00012|persAcc=0000000012|Purpose=" + "0" * 3000},
    ],
)
def test_verify_body_takes_exactly_one_of_account_and_qr(body: dict[str, str]) -> None:
    adapter: TypeAdapter[VerifyFlatRequest | VerifyFlatByQrRequest] = TypeAdapter(
        VerifyFlatRequest | VerifyFlatByQrRequest,
    )

    with pytest.raises(ValidationError):
        adapter.validate_python(body)
