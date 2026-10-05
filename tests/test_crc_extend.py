"""CR-C: atbildes termiņa pagarināšana (POST /submissions/{id}/extend)."""

import logging
from datetime import date, datetime, timezone

import pytest

from app import clock, storage
from app.main import add_months

REASON = "Jāsaņem būvvaldes atzinums"

# Sintētiski, unikāli personas dati: AC9 testā tos meklē žurnālā un kļūdās.
PERSON = {
    "personalCode": "32000000777",
    "fullName": "Kārlis Testiņš-Pagarinātājs",
    "email": "karlis.pagarinatajs@example.com",
    "preferredChannel": "EMAIL",
    "topic": "ROADS",
    "subject": "Ielas apgaismojums Kalna ielā",
    "body": "Kalna ielā pie 7. mājas jau mēnesi nedeg laterna.",
}


def _add(status="RECEIVED", received_at="2026-09-25T13:40:00+00:00", due="2026-10-26"):
    record = storage.add(
        {
            **PERSON,
            "status": status,
            "receivedAt": received_at,
            "dueDate": due,
            "replyChannel": "EMAIL",
            "reasonCode": None,
        }
    )
    return record["id"]


def _extend(client, submission_id, new_due_date, reason=REASON):
    return client.post(
        f"/submissions/{submission_id}/extend",
        json={"newDueDate": new_due_date, "reason": reason},
    )


def _assert_unchanged(client, submission_id, due="2026-10-26"):
    assert client.get(f"/submissions/{submission_id}").json()["dueDate"] == due
    actions = [
        e["action"] for e in client.get(f"/submissions/{submission_id}/audit").json()
    ]
    assert "EXTEND" not in actions


# --- +4 kalendāra mēneši (PO1) ---


@pytest.mark.parametrize(
    "start, expected",
    [
        (date(2026, 9, 25), date(2027, 1, 25)),
        (date(2026, 5, 31), date(2026, 9, 30)),
        (date(2026, 10, 31), date(2027, 2, 28)),
        (date(2027, 10, 31), date(2028, 2, 29)),
        (date(2026, 11, 30), date(2027, 3, 30)),
    ],
)
def test_crc_add_months(start, expected):
    assert add_months(start, 4) == expected


def test_crc_month_end_clamped_via_api(client):
    submission_id = _add(
        status="IN_PROGRESS", received_at="2026-05-31T07:20:00+00:00", due="2026-06-30"
    )
    assert _extend(client, submission_id, "2026-10-01").status_code == 400
    assert _extend(client, submission_id, "2026-09-30").status_code == 200


# --- AC1–AC6 ---


@pytest.mark.parametrize("status", ["RECEIVED", "IN_PROGRESS"])
def test_crc_ac1_extends_due_date(client, status):
    submission_id = _add(status=status)

    response = _extend(client, submission_id, "2026-12-15")

    assert response.status_code == 200
    assert response.json()["dueDate"] == "2026-12-15"
    assert response.json()["status"] == status  # PO7: statuss nemainās
    stored = client.get(f"/submissions/{submission_id}").json()
    assert stored["dueDate"] == "2026-12-15"
    assert stored["status"] == status


def test_crc_ac2_exact_four_month_boundary_allowed(client):
    submission_id = _add()

    response = _extend(client, submission_id, "2027-01-25")

    assert response.status_code == 200
    assert response.json()["dueDate"] == "2027-01-25"


def test_crc_ac3_beyond_four_months_rejected(client):
    submission_id = _add()

    response = _extend(client, submission_id, "2027-01-26")

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "INVALID_DUE_DATE", "message": "New due date is not allowed"}
    }
    _assert_unchanged(client, submission_id)


@pytest.mark.parametrize("new_due_date", ["2026-10-26", "2026-10-25"])
def test_crc_ac4_not_later_than_current_rejected(client, new_due_date):
    submission_id = _add()

    response = _extend(client, submission_id, new_due_date)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DUE_DATE"
    _assert_unchanged(client, submission_id)


@pytest.mark.parametrize("status", ["FORWARDED", "ANSWERED", "WITHDRAWN"])
def test_crc_ac5_invalid_state_rejected(client, status):
    submission_id = _add(status=status)

    response = _extend(client, submission_id, "2026-12-15")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "INVALID_STATE",
            "message": "Action not allowed in the current status",
        }
    }
    _assert_unchanged(client, submission_id)


def test_crc_ac5_state_checked_before_date(client):
    # PO6: neatļauts statuss (409) ir pirms neatļauta datuma (400).
    submission_id = _add(status="FORWARDED")
    assert _extend(client, submission_id, "2027-01-26").status_code == 409


def test_crc_ac6_unknown_id_404(client):
    response = _extend(client, "IES-2026-999999", "2026-12-15")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_crc_ac6_validation_before_not_found(client):
    # PO6: vispirms pieprasījuma validācija, tikai tad ID.
    response = _extend(client, "IES-2026-999999", "15.12.2026")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- AC7 ---

VALID = {"newDueDate": "2026-12-15", "reason": REASON}


@pytest.mark.parametrize(
    "body, field, issue",
    [
        ({"reason": REASON}, "newDueDate", "REQUIRED"),
        ({"newDueDate": "2026-12-15"}, "reason", "REQUIRED"),
        ({}, "newDueDate", "REQUIRED"),
        ({**VALID, "newDueDate": "15.12.2026"}, "newDueDate", "INVALID_FORMAT"),
        ({**VALID, "newDueDate": "2026-13-01"}, "newDueDate", "INVALID_FORMAT"),
        ({**VALID, "newDueDate": "2026-02-30"}, "newDueDate", "INVALID_FORMAT"),
        ({**VALID, "newDueDate": 20261215}, "newDueDate", "INVALID_FORMAT"),
        (
            {**VALID, "newDueDate": "2026-12-15T00:00:00"},
            "newDueDate",
            "INVALID_FORMAT",
        ),
        ({**VALID, "newDueDate": None}, "newDueDate", "INVALID_FORMAT"),
        ({**VALID, "reason": "a" * 9}, "reason", "INVALID_FORMAT"),
        ({**VALID, "reason": " " * 20}, "reason", "INVALID_FORMAT"),
        ({**VALID, "reason": "   abc     "}, "reason", "INVALID_FORMAT"),
        ({**VALID, "reason": "a" * 501}, "reason", "TOO_LONG"),
    ],
)
def test_crc_ac7_validation_error(client, body, field, issue):
    submission_id = _add()

    response = client.post(f"/submissions/{submission_id}/extend", json=body)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {"field": field, "issue": issue} in error["details"]
    _assert_unchanged(client, submission_id)


@pytest.mark.parametrize("length", [10, 500])
def test_crc_ac7_reason_length_boundaries(client, length):
    submission_id = _add()
    assert _extend(client, submission_id, "2026-12-15", "a" * length).status_code == 200


def test_crc_ac7_reason_trimmed_before_length_check(client):
    submission_id = _add()
    reason = "  " + "a" * 500 + "  "
    assert _extend(client, submission_id, "2026-12-15", reason).status_code == 200


# --- AC8 ---


def test_crc_ac8_audit_has_extend_with_reason(client, valid_payload, monkeypatch):
    fixed = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(clock, "now", lambda: fixed)
    created = client.post("/submissions", json=valid_payload).json()

    response = _extend(client, created["id"], "2026-12-15", f"  {REASON}  ")
    audit = client.get(f"/submissions/{created['id']}/audit").json()

    assert response.status_code == 200
    assert audit == [
        {"at": "2026-10-05T12:00:00Z", "action": "CREATE", "detail": None},
        {"at": "2026-10-05T12:00:00Z", "action": "EXTEND", "detail": REASON},
    ]


# --- AC9 ---


def test_crc_ac9_no_personal_data_in_logs_or_errors(client, caplog):
    active = _add()
    forwarded = _add(status="FORWARDED")

    with caplog.at_level(logging.INFO):
        ok = _extend(client, active, "2026-12-15")
        errors = [
            _extend(client, active, "2027-01-26"),  # 400 INVALID_DUE_DATE
            _extend(client, active, "15.12.2026"),  # 400 VALIDATION_ERROR
            _extend(client, active, "2026-12-20", "par īsu"),  # 400 VALIDATION_ERROR
            _extend(client, "IES-2026-999999", "2026-12-15"),  # 404
            _extend(client, forwarded, "2026-12-15"),  # 409
        ]

    assert ok.status_code == 200
    assert [r.status_code for r in errors] == [400, 400, 400, 404, 409]
    assert active in caplog.text
    for value in ("personalCode", "fullName", "email", "subject", "body"):
        assert PERSON[value] not in caplog.text
        for response in errors:
            assert PERSON[value] not in response.text


# --- PO lēmumi un precizējumi ---


def test_crc_overdue_due_date_can_be_extended_into_past(client, monkeypatch):
    # PO2, PO3: pārbaudes pret šodienas datumu nav.
    fixed = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(clock, "now", lambda: fixed)
    submission_id = _add(
        status="IN_PROGRESS", received_at="2026-08-20T10:00:00+00:00", due="2026-09-21"
    )

    response = _extend(client, submission_id, "2026-10-01")

    assert response.status_code == 200
    assert response.json()["dueDate"] == "2026-10-01"


def test_crc_can_extend_multiple_times(client):
    submission_id = _add()

    assert _extend(client, submission_id, "2026-11-15").status_code == 200
    assert _extend(client, submission_id, "2026-12-15").status_code == 200
    assert _extend(client, submission_id, "2026-12-15").status_code == 400

    audit = client.get(f"/submissions/{submission_id}/audit").json()
    assert [e["action"] for e in audit] == ["EXTEND", "EXTEND"]
    assert client.get(f"/submissions/{submission_id}").json()["dueDate"] == "2026-12-15"


# --- A1: konkurējoši pieprasījumi (pārskatīšanas atradums) ---


def _concurrent_change_after_read(monkeypatch, change):
    """Konkurējošā darbība notiek starp pārbaudes lasījumu un ierakstu."""
    real_get = storage.get
    done = []

    def get_then_change(submission_id):
        record = real_get(submission_id)
        if not done:
            done.append(submission_id)
            change(submission_id)
        return record

    monkeypatch.setattr(storage, "get", get_then_change)


def test_crc_a1_concurrent_extend_cannot_shorten_due_date(client, monkeypatch):
    submission_id = _add()  # dueDate 2026-10-26
    # Pieprasījums A pagarina līdz 2026-12-15, kamēr B jau ir izlasījis 2026-10-26.
    _concurrent_change_after_read(
        monkeypatch, lambda sid: storage.update_due_date(sid, "2026-12-15")
    )

    response = _extend(client, submission_id, "2026-11-01")  # pieprasījums B
    monkeypatch.undo()

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DUE_DATE"
    _assert_unchanged(client, submission_id, due="2026-12-15")


def test_crc_a1_concurrent_status_change_returns_409(client, monkeypatch):
    submission_id = _add()
    _concurrent_change_after_read(
        monkeypatch, lambda sid: storage.update_status(sid, "FORWARDED")
    )

    response = _extend(client, submission_id, "2026-12-15")
    monkeypatch.undo()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"
    _assert_unchanged(client, submission_id)
