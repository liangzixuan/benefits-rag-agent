import pytest
from unittest.mock import patch, MagicMock
from main import (
    lookup_benefit_term,
    calculate_benefit_cost,
    schedule_appointment,
    load_and_chunk_pdfs,
    app,
)

# --------------------- Test lookup_benefit_term ---------------------
def test_lookup_benefit_term():
    assert lookup_benefit_term("HSA") == "Health Savings Account lets you save pre-tax money for medical expenses."
    assert lookup_benefit_term("PPO") == "Preferred Provider Organization is a type of health insurance plan."
    assert lookup_benefit_term("Unknown") == "Definition for 'Unknown' not found."

# --------------------- Test calculate_benefit_cost ---------------------
def test_calculate_benefit_cost():
    assert calculate_benefit_cost("PPO", 350, 1000) == "The estimated annual cost for a PPO plan is $5200.00."
    assert calculate_benefit_cost("HMO", 200, 500) == "The estimated annual cost for a HMO plan is $2900.00."
    assert calculate_benefit_cost("PPO", "invalid", 1000) == "Invalid input for benefit calculation."

# --------------------- Test schedule_appointment ---------------------
@patch("main.get_calendar_service")
def test_schedule_appointment(mock_get_calendar_service):
    mock_service = MagicMock()
    mock_get_calendar_service.return_value = mock_service
    mock_service.events().insert().execute.return_value = {"htmlLink": "http://example.com/event"}

    result = schedule_appointment("2025-04-20", "14:00", "Benefits consultation")
    assert result == "Appointment scheduled successfully. View it here: http://example.com/event"

    mock_service.events().insert().execute.side_effect = Exception("Google Calendar error")
    result = schedule_appointment("2025-04-20", "14:00", "Benefits consultation")
    assert result == "Failed to schedule the appointment. Please try again later."

# --------------------- Test load_and_chunk_pdfs ---------------------
@patch("main.glob.glob")
@patch("main.PyPDF2.PdfReader")
def test_load_and_chunk_pdfs(mock_pdf_reader, mock_glob):
    mock_glob.return_value = ["file1.pdf", "file2.pdf"]
    mock_pdf_reader.return_value.pages = [MagicMock(extract_text=lambda: "Page 1 text"), MagicMock(extract_text=lambda: "Page 2 text")]

    chunks, metadata = load_and_chunk_pdfs("./pdfs")
    assert len(chunks) > 0
    assert metadata == ["file1.pdf", "file1.pdf", "file2.pdf", "file2.pdf"]

# --------------------- Test Flask /chat Endpoint ---------------------
@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@patch("main.client.embeddings.create")
@patch("main.index.search")
def test_chat_endpoint(mock_search, mock_embeddings, client):
    mock_embeddings.return_value = MagicMock(data=[{"embedding": [0.1, 0.2, 0.3]}])
    mock_search.return_value = (None, [[0, 1]])

    response = client.post("/chat", json={"query": "What is HSA?"})
    assert response.status_code == 200
    assert "answer" in response.get_json()

    response = client.post("/chat", json={})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Missing 'query' field."