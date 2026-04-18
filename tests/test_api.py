"""API tests for the Phase 2 FastAPI backend skeleton."""

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def _new_session() -> str:
    response = client.post("/session/new")
    assert response.status_code == 200
    return response.json()["session_id"]


def _valid_calculation_payload(**overrides):
    payload = {
        "risk_category": "II",
        "basic_wind_speed_V": 115.0,
        "exposure_category": "C",
        "mean_roof_height_h": 40.0,
        "building_length_L": 100.0,
        "building_width_B": 50.0,
        "roof_type": "flat",
        "analysis_type": "MWFRS",
        "design_standard": "LRFD",
    }
    payload.update(overrides)
    return payload


def test_new_session_returns_session_state():
    response = client.post("/session/new")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["session_state"]["session_id"] == body["session_id"]
    assert body["session_state"]["current_phase"] == 1
    assert body["session_state"]["collected_inputs"] == {}
    assert body["session_state"]["messages"] == []
    assert body["session_state"]["ready_to_calculate"] is False


def test_get_session_state_returns_existing_session():
    session_id = _new_session()

    response = client.get(f"/session/{session_id}/state")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["last_calculation"] is None


def test_message_endpoint_persists_user_and_placeholder_assistant_messages():
    session_id = _new_session()

    response = client.post(
        f"/session/{session_id}/message",
        json={"message": "Use an office building in Boston."},
    )

    assert response.status_code == 200
    body = response.json()
    assert "Message received" in body["response"]
    messages = body["session_state"]["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Use an office building in Boston."
    assert "deterministic conversation controller" in messages[1]["content"]

    state_response = client.get(f"/session/{session_id}/state")
    assert state_response.json()["messages"] == messages


def test_calculate_with_valid_payload_returns_engine_results_and_updates_session():
    session_id = _new_session()
    payload = _valid_calculation_payload()

    response = client.post(f"/session/{session_id}/calculate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["results"]["summary"]["qh_psf"] == 29.929
    assert body["results"]["inputs"]["roof_type"] == "flat"
    assert "wall_pressures" in body["results"]
    assert body["session_state"]["ready_to_calculate"] is True
    assert body["session_state"]["collected_inputs"]["basic_wind_speed_V"] == 115.0
    assert body["session_state"]["last_calculation"]["summary"]["qh_psf"] == 29.929


def test_invalid_calculation_payload_returns_validation_error():
    session_id = _new_session()
    payload = _valid_calculation_payload(mean_roof_height_h=-1)

    response = client.post(f"/session/{session_id}/calculate", json=payload)

    assert response.status_code == 422
    assert "mean_roof_height_h" in str(response.json()["detail"])


def test_engine_validation_error_returns_422():
    session_id = _new_session()
    payload = _valid_calculation_payload(
        roof_type="gable",
        roof_slope_deg=20.0,
        ridge_orientation=None,
    )

    response = client.post(f"/session/{session_id}/calculate", json=payload)

    assert response.status_code == 422
    assert "Ridge orientation is required" in response.json()["detail"]


def test_unknown_session_returns_404():
    response = client.get("/session/does-not-exist/state")

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_unknown_session_message_returns_404():
    response = client.post(
        "/session/does-not-exist/message",
        json={"message": "hello"},
    )

    assert response.status_code == 404


def test_unknown_session_calculate_returns_404():
    response = client.post(
        "/session/does-not-exist/calculate",
        json=_valid_calculation_payload(),
    )

    assert response.status_code == 404


def test_two_sessions_remain_isolated():
    first_session_id = _new_session()
    second_session_id = _new_session()

    first_message = client.post(
        f"/session/{first_session_id}/message",
        json={"message": "first session message"},
    )
    second_calculation = client.post(
        f"/session/{second_session_id}/calculate",
        json=_valid_calculation_payload(basic_wind_speed_V=130.0),
    )

    assert first_message.status_code == 200
    assert second_calculation.status_code == 200

    first_state = client.get(f"/session/{first_session_id}/state").json()
    second_state = client.get(f"/session/{second_session_id}/state").json()

    assert first_state["session_id"] != second_state["session_id"]
    assert first_state["messages"][0]["content"] == "first session message"
    assert first_state["last_calculation"] is None
    assert second_state["messages"] == []
    assert second_state["collected_inputs"]["basic_wind_speed_V"] == 130.0
    assert second_state["last_calculation"]["summary"]["qh_psf"] != 29.929
