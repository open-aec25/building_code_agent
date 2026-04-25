"""API tests for the FastAPI backend and deterministic conversation controller."""

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


def _send(session_id: str, message: str):
    return client.post(f"/session/{session_id}/message", json={"message": message})


def test_new_session_returns_session_state():
    response = client.post("/session/new")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["session_state"]["session_id"] == body["session_id"]
    assert body["session_state"]["current_phase"] == 1
    assert body["session_state"]["current_question_id"] == "Q1"
    assert body["session_state"]["collected_inputs"] == {}
    assert body["session_state"]["branch_flags"] == {}
    assert body["session_state"]["messages"] == []
    assert body["session_state"]["ready_to_calculate"] is False


def test_get_session_state_returns_existing_session():
    session_id = _new_session()

    response = client.get(f"/session/{session_id}/state")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["last_calculation"] is None


def test_message_endpoint_persists_user_and_controller_response_messages():
    session_id = _new_session()

    response = _send(session_id, "office")

    assert response.status_code == 200
    body = response.json()
    assert "Approximately how many people" in body["response"]
    assert body["session_state"]["current_question_id"] == "Q2"
    assert body["session_state"]["collected_inputs"]["occupancy_type"] == "office"
    messages = body["session_state"]["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "office"
    assert "Approximately how many people" in messages[1]["content"]

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

    first_message = _send(first_session_id, "office")
    second_calculation = client.post(
        f"/session/{second_session_id}/calculate",
        json=_valid_calculation_payload(basic_wind_speed_V=130.0),
    )

    assert first_message.status_code == 200
    assert second_calculation.status_code == 200

    first_state = client.get(f"/session/{first_session_id}/state").json()
    second_state = client.get(f"/session/{second_session_id}/state").json()

    assert first_state["session_id"] != second_state["session_id"]
    assert first_state["messages"][0]["content"] == "office"
    assert first_state["last_calculation"] is None
    assert second_state["messages"] == []
    assert second_state["collected_inputs"]["basic_wind_speed_V"] == 130.0
    assert second_state["last_calculation"]["summary"]["qh_psf"] != 29.929


def test_conversation_collects_flat_roof_flow_and_runs_calculation_on_confirm():
    session_id = _new_session()
    answers = [
        "office",
        "45",
        "no",
        "no",
        "Chicago, IL",
        "115",
        "C",
        "no",
        "40",
        "100",
        "50",
        "flat",
        "MWFRS",
        "LRFD",
    ]

    last_response = None
    for answer in answers:
        last_response = _send(session_id, answer)
        assert last_response.status_code == 200

    body = last_response.json()
    assert body["session_state"]["current_question_id"] == "CONFIRM"
    assert body["session_state"]["ready_to_calculate"] is True
    assert "Before I run the calculations" in body["response"]
    assert "Roof Type: flat" in body["response"]
    assert "Ridge Orientation" not in body["response"]

    confirm_response = _send(session_id, "yes")

    assert confirm_response.status_code == 200
    confirm_body = confirm_response.json()
    assert "Calculation complete" in confirm_body["response"]
    assert confirm_body["session_state"]["current_question_id"] == "COMPLETE"
    assert confirm_body["session_state"]["last_calculation"]["summary"]["qh_psf"] == 29.929


def test_location_step_resolves_massachusetts_wind_speed_and_skips_manual_entry():
    session_id = _new_session()
    for answer in ["office", "45", "no", "no"]:
        response = _send(session_id, answer)
        assert response.status_code == 200

    response = _send(session_id, "Boston, MA")

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["current_question_id"] == "Q6"
    assert body["session_state"]["branch_flags"]["wind_speed_lookup_available"] is True
    assert body["session_state"]["branch_flags"]["wind_speed_lookup_failed"] is False
    assert body["session_state"]["collected_inputs"]["basic_wind_speed_V"] == 120.0
    assert body["session_state"]["collected_inputs"]["resolved_municipality"] == "Boston"
    assert "780 CMR Table 1604.11" in body["response"]
    assert "V is 120 mph" in body["response"]


def test_massachusetts_lookup_uses_risk_category_specific_wind_speed():
    session_id = _new_session()
    for answer in ["minor storage", "3", "no", "no"]:
        response = _send(session_id, answer)
        assert response.status_code == 200

    response = _send(session_id, "Boston, Massachusetts")

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["current_question_id"] == "Q6"
    assert body["session_state"]["collected_inputs"]["risk_category"] == "I"
    assert body["session_state"]["collected_inputs"]["basic_wind_speed_V"] == 110.0
    assert "Risk Category I" in body["response"]
    assert "V is 110 mph" in body["response"]


def test_massachusetts_lookup_warns_for_note_ref_2_special_wind_region():
    session_id = _new_session()
    for answer in ["office", "45", "no", "no"]:
        response = _send(session_id, answer)
        assert response.status_code == 200

    response = _send(session_id, "Adams, MA")

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["current_question_id"] == "Q6"
    assert body["session_state"]["collected_inputs"]["basic_wind_speed_V"] == 111.0
    assert "note ref 2" in body["response"]
    assert "Special Wind Region" in body["response"]


def test_unresolved_massachusetts_location_uses_manual_wind_speed_fallback():
    session_id = _new_session()
    for answer in ["office", "45", "no", "no"]:
        response = _send(session_id, answer)
        assert response.status_code == 200

    response = _send(session_id, "Atlantis, MA")

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["current_question_id"] == "MANUAL_WIND_SPEED"
    assert body["session_state"]["branch_flags"]["wind_speed_lookup_available"] is False
    assert body["session_state"]["branch_flags"]["wind_speed_lookup_failed"] is True
    assert "did not resolve to a supported Massachusetts city or town" in body["response"]
    assert "Figure 26.5-1A" in body["response"]


def test_non_massachusetts_location_uses_manual_wind_speed_fallback():
    session_id = _new_session()
    for answer in ["office", "45", "no", "no"]:
        response = _send(session_id, answer)
        assert response.status_code == 200

    response = _send(session_id, "Chicago, IL")

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["current_question_id"] == "MANUAL_WIND_SPEED"
    assert body["session_state"]["branch_flags"]["wind_speed_lookup_available"] is False
    assert body["session_state"]["branch_flags"]["wind_speed_lookup_failed"] is True
    assert "Please look up the basic wind speed" in body["response"]
    assert "Figure 26.5-1A" in body["response"]


def test_manual_wind_speed_must_be_positive_and_keeps_question_active():
    session_id = _new_session()
    for answer in ["office", "45", "no", "no", "Chicago, IL"]:
        response = _send(session_id, answer)
        assert response.status_code == 200

    response = _send(session_id, "0")

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["current_question_id"] == "MANUAL_WIND_SPEED"
    assert "number greater than 0" in body["response"]
    assert "basic_wind_speed_V" not in body["session_state"]["collected_inputs"]


def test_risk_category_iii_is_derived_for_large_school():
    session_id = _new_session()
    for answer in ["school", "300", "no"]:
        response = _send(session_id, answer)
        assert response.status_code == 200

    response = _send(session_id, "no")

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["collected_inputs"]["risk_category"] == "III"
    assert body["session_state"]["collected_inputs"]["wind_speed_figure"] == "26.5-1C"
    assert "Risk Category III" in body["response"]


def test_risk_category_iv_is_derived_for_essential_hospital():
    session_id = _new_session()
    for answer in ["hospital", "100", "yes"]:
        response = _send(session_id, answer)
        assert response.status_code == 200

    response = _send(session_id, "no")

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["collected_inputs"]["risk_category"] == "IV"
    assert body["session_state"]["collected_inputs"]["wind_speed_figure"] == "26.5-1C"
    assert "Risk Category IV" in body["response"]


def test_risk_category_i_is_derived_for_minor_storage():
    session_id = _new_session()
    for answer in ["minor storage", "3", "no"]:
        response = _send(session_id, answer)
        assert response.status_code == 200

    response = _send(session_id, "no")

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["collected_inputs"]["risk_category"] == "I"
    assert body["session_state"]["collected_inputs"]["wind_speed_figure"] == "26.5-1B"
    assert "Risk Category I" in body["response"]


def test_conversation_collects_gable_roof_slope_and_ridge_orientation():
    session_id = _new_session()
    answers = [
        "warehouse",
        "20",
        "no",
        "no",
        "Chicago, IL",
        "115",
        "B",
        "no",
        "30",
        "120",
        "60",
        "gable",
        "18.4",
        "normal",
        "MWFRS",
        "ASD",
    ]

    for answer in answers:
        response = _send(session_id, answer)
        assert response.status_code == 200

    state = client.get(f"/session/{session_id}/state").json()
    assert state["current_question_id"] == "CONFIRM"
    assert state["collected_inputs"]["roof_type"] == "gable"
    assert state["collected_inputs"]["roof_slope_deg"] == 18.4
    assert state["collected_inputs"]["ridge_orientation"] == "normal"


def test_conversation_topographic_feature_branch_collects_detail_questions():
    session_id = _new_session()
    answers = [
        "office",
        "20",
        "no",
        "no",
        "Denver, CO",
        "115",
        "C",
        "yes",
        "3D hill",
        "100",
        "200",
        "50",
        "40",
        "100",
        "50",
        "flat",
        "MWFRS",
        "LRFD",
    ]

    for answer in answers:
        response = _send(session_id, answer)
        assert response.status_code == 200

    state = client.get(f"/session/{session_id}/state").json()
    assert state["branch_flags"]["topographic_feature_present"] is True
    assert state["collected_inputs"]["topo_feature_type"] == "3D_hill"
    assert state["collected_inputs"]["topo_H"] == 100.0
    assert state["current_question_id"] == "CONFIRM"


def test_confirmation_correction_updates_field_and_redisplays_summary():
    session_id = _new_session()
    answers = [
        "office",
        "45",
        "no",
        "no",
        "Chicago, IL",
        "115",
        "C",
        "no",
        "40",
        "100",
        "50",
        "flat",
        "MWFRS",
        "LRFD",
    ]
    for answer in answers:
        response = _send(session_id, answer)
        assert response.status_code == 200

    correction = _send(session_id, "change wind speed to 130 mph")

    assert correction.status_code == 200
    body = correction.json()
    assert body["session_state"]["current_question_id"] == "CONFIRM"
    assert body["session_state"]["collected_inputs"]["basic_wind_speed_V"] == 130.0
    assert "Basic Wind Speed (V): 130.0" in body["response"]
