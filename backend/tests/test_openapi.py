import re
from collections import Counter
from typing import Any

import pytest
from fastapi import FastAPI

from tests.conftest import make_config

from zheka.api.app import app_factory

# контракт мини-аппа: метод, путь и имя операции из плана. Правка этого списка
# ломает фронт, поэтому она обсуждается, а не делается по ходу задачи
CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)

CONTRACT: tuple[tuple[str, str, str], ...] = (
    ("get", "/api/healthcheck", "healthcheck"),
    ("get", "/api/me", "get_me"),
    ("post", "/api/me/consent", "accept_consent"),
    ("get", "/api/me/notifications", "get_notification_settings"),
    ("put", "/api/me/notifications", "update_notification_settings"),
    ("post", "/api/events", "track_event"),
    ("get", "/api/geo/cities", "list_cities"),
    ("get", "/api/geo/streets", "list_streets"),
    ("get", "/api/houses", "search_houses"),
    ("get", "/api/houses/nearby", "search_houses_nearby"),
    ("get", "/api/houses/{house_id}", "get_house_card"),
    ("post", "/api/houses/{house_id}/link", "link_house"),
    ("delete", "/api/residencies/{resident_id}", "unlink_house"),
    ("post", "/api/houses/{house_id}/demand", "create_demand_signal"),
    ("get", "/api/houses/{house_id}/flats", "list_house_flats"),
    ("get", "/api/flats/{flat_id}", "get_flat_card"),
    ("post", "/api/flats/{flat_id}/verify", "verify_flat"),
    ("post", "/api/flats/{flat_id}/verification-request", "request_flat_verification"),
    ("get", "/api/flats/{flat_id}/residents", "list_flat_residents"),
    ("post", "/api/flats/{flat_id}/invites", "create_flat_invite"),
    ("get", "/api/flats/{flat_id}/invites", "list_flat_invites"),
    ("delete", "/api/flat-invites/{code}", "revoke_flat_invite"),
    ("post", "/api/flat-invites/{code}/activate", "activate_flat_invite"),
    ("get", "/api/request-categories", "list_request_categories"),
    ("get", "/api/requests", "list_my_requests"),
    ("get", "/api/requests/similar", "find_similar_requests"),
    ("post", "/api/requests", "create_request"),
    ("get", "/api/requests/{request_id}", "get_request"),
    ("post", "/api/requests/{request_id}/rating", "rate_request"),
    ("post", "/api/requests/{request_id}/repeat", "create_repeat_request"),
    ("post", "/api/requests/{request_id}/review", "review_request"),
    ("get", "/api/requests/{request_id}/export", "export_request"),
    ("get", "/api/flats/{flat_id}/meters", "list_flat_meters"),
    ("get", "/api/flats/{flat_id}/reading-periods", "list_reading_periods"),
    ("get", "/api/meters/{meter_id}/readings", "list_meter_readings"),
    ("post", "/api/meters/{meter_id}/readings", "submit_reading"),
    ("get", "/api/houses/{house_id}/tariffs", "list_house_tariffs"),
    ("get", "/api/flats/{flat_id}/charges", "list_flat_charges"),
    ("get", "/api/charges/{charge_id}", "get_charge"),
    ("get", "/api/charges/{charge_id}/breakdown", "get_charge_breakdown"),
    ("post", "/api/charges/{charge_id}/dispute", "dispute_charge"),
    ("post", "/api/charges/{charge_id}/pay", "pay_charge_demo"),
    ("get", "/api/houses/{house_id}/polls", "list_polls"),
    ("post", "/api/houses/{house_id}/polls", "create_poll"),
    ("get", "/api/polls/{poll_id}", "get_poll"),
    ("post", "/api/polls/{poll_id}/vote", "vote_in_poll"),
    ("get", "/api/polls/{poll_id}/results", "get_poll_results"),
    ("get", "/api/polls/{poll_id}/non-voters", "list_poll_non_voters"),
    ("post", "/api/polls/{poll_id}/close", "close_poll"),
    ("get", "/api/announcements", "list_announcements"),
    ("get", "/api/houses/{house_id}/reception-slots", "list_reception_slots"),
    ("get", "/api/appointments", "list_my_appointments"),
    ("post", "/api/appointments", "book_appointment"),
    ("delete", "/api/appointments/{appointment_id}", "cancel_appointment"),
    ("get", "/api/access-requests", "list_my_access_requests"),
    (
        "post",
        "/api/access-requests/{access_request_id}/slots/{slot_id}",
        "pick_access_slot",
    ),
    ("post", "/api/files", "upload_file"),
    ("get", "/files/{name}", "download_file"),
    ("post", "/api/orgs/lookup", "lookup_org"),
    ("post", "/api/orgs", "register_org"),
    ("post", "/api/org-invites/{code}/activate", "activate_org_invite"),
    ("post", "/api/demo/activate", "activate_demo"),
    ("get", "/api/admin/org", "get_org"),
    ("get", "/api/admin/org/settings", "get_org_settings"),
    ("put", "/api/admin/org/settings", "update_org_settings"),
    ("get", "/api/admin/org/members", "list_org_members"),
    ("delete", "/api/admin/org/members/{user_id}", "remove_org_member"),
    ("get", "/api/admin/org/invites", "list_org_invites"),
    ("post", "/api/admin/org/invites", "create_org_invite"),
    ("delete", "/api/admin/org/invites/{code}", "revoke_org_invite"),
    ("get", "/api/admin/houses", "list_org_houses"),
    ("get", "/api/admin/houses/{house_id}", "get_admin_house_card"),
    ("post", "/api/admin/houses/{house_id}/binding-code", "rotate_house_binding_code"),
    ("get", "/api/admin/houses/{house_id}/residents", "list_house_residents"),
    ("post", "/api/admin/residents/{resident_id}/block", "block_resident"),
    ("post", "/api/admin/residents/{resident_id}/unblock", "unblock_resident"),
    (
        "post",
        "/api/admin/residents/{resident_id}/revoke-verification",
        "revoke_flat_verification",
    ),
    ("post", "/api/admin/residents/{resident_id}/chairman", "set_chairman"),
    ("get", "/api/admin/verification-requests", "list_verification_requests"),
    (
        "post",
        "/api/admin/verification-requests/{verification_id}/approve",
        "approve_verification_request",
    ),
    (
        "post",
        "/api/admin/verification-requests/{verification_id}/reject",
        "reject_verification_request",
    ),
    ("get", "/api/admin/requests", "list_org_requests"),
    ("get", "/api/admin/requests/{request_id}", "get_org_request"),
    ("post", "/api/admin/requests/{request_id}/status", "change_request_status"),
    ("post", "/api/admin/requests/{request_id}/reply", "reply_to_request"),
    ("post", "/api/admin/requests/{request_id}/assign", "assign_request_executor"),
    ("get", "/api/admin/request-groups/{group_id}", "get_request_group"),
    (
        "post",
        "/api/admin/request-groups/{group_id}/status",
        "change_request_group_status",
    ),
    ("post", "/api/admin/requests/phone", "create_phone_request"),
    ("get", "/api/admin/executors", "list_org_executors"),
    ("get", "/api/admin/houses/{house_id}/readings", "list_house_readings"),
    ("get", "/api/admin/announcements", "list_org_announcements"),
    ("post", "/api/admin/announcements", "create_announcement"),
    ("get", "/api/admin/polls", "list_org_polls"),
    ("post", "/api/admin/polls", "create_org_poll"),
    ("get", "/api/admin/reception/windows", "list_reception_windows"),
    ("put", "/api/admin/reception/windows", "set_reception_windows"),
    ("get", "/api/admin/appointments", "list_org_appointments"),
    ("post", "/api/admin/access-requests", "create_access_request"),
    ("get", "/api/admin/access-requests", "list_org_access_requests"),
    (
        "get",
        "/api/admin/access-requests/{access_request_id}",
        "get_access_request_grid",
    ),
    ("get", "/api/admin/analytics/dashboard", "get_dashboard"),
    ("get", "/api/admin/analytics/meters-season", "get_meters_season"),
    ("post", "/api/admin/analytics/meters-season/remind", "remind_not_submitted"),
    ("get", "/api/admin/analytics/executors", "get_executors_stats"),
    ("get", "/api/admin/analytics/channels", "get_channels_split"),
    ("get", "/api/admin/analytics/benchmark", "get_benchmark"),
)


# make_dispatcher включает модульные роутеры, поэтому приложение в процессе
# может быть построено только один раз
@pytest.fixture(scope="module")
def app() -> FastAPI:
    return app_factory(make_config())


@pytest.fixture(scope="module")
def openapi(app: FastAPI) -> dict[str, Any]:
    return app.openapi()


def test_openapi_is_served_under_api_prefix(app: FastAPI) -> None:
    assert app.openapi_url == "/api/openapi.json"


def test_operation_ids_are_unique(openapi: dict[str, Any]) -> None:
    ids = [
        operation["operationId"]
        for methods in openapi["paths"].values()
        for operation in methods.values()
    ]
    duplicates = [name for name, count in Counter(ids).items() if count > 1]

    assert not duplicates


def test_contract_endpoints_are_registered(openapi: dict[str, Any]) -> None:
    declared = {
        (method, path, operation["operationId"])
        for path, methods in openapi["paths"].items()
        for method, operation in methods.items()
    }

    assert declared == set(CONTRACT)


def test_every_route_has_russian_summary(openapi: dict[str, Any]) -> None:
    not_russian = [
        operation["operationId"]
        for methods in openapi["paths"].values()
        for operation in methods.values()
        if not CYRILLIC.search(operation.get("summary", ""))
    ]

    assert not not_russian


def test_no_unreachable_validation_response(openapi: dict[str, Any]) -> None:
    # валидация отвечает 400 конвертом ApiError, автоматический 422 от FastAPI
    # описывал бы форму, которую приложение не отдает никогда
    with_422 = [
        operation["operationId"]
        for methods in openapi["paths"].values()
        for operation in methods.values()
        if "422" in operation["responses"]
    ]

    assert not with_422
    assert "HTTPValidationError" not in openapi["components"]["schemas"]


@pytest.mark.parametrize("schema_name", ["RequestCard", "AdminRequestCard"])
def test_request_cards_expose_nullable_org_and_required_normative_hours(
    openapi: dict[str, Any],
    schema_name: str,
) -> None:
    schema = openapi["components"]["schemas"][schema_name]

    assert schema["properties"]["org_name"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert schema["properties"]["normative_hours"]["type"] == "integer"
    assert {"org_name", "normative_hours"} <= set(schema["required"])


@pytest.mark.parametrize("schema_name", ["RequestListItem", "AdminRequestListItem"])
def test_request_list_items_do_not_expose_card_org_and_normative_hours(
    openapi: dict[str, Any],
    schema_name: str,
) -> None:
    properties = openapi["components"]["schemas"][schema_name]["properties"]

    assert "org_name" not in properties
    assert "normative_hours" not in properties
