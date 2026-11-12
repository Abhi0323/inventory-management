"""
Tests for restocking order API endpoints.
"""
from datetime import date, timedelta

import pytest

import main


@pytest.fixture(autouse=True)
def reset_submitted_orders():
    """Keep the in-memory submitted orders list isolated between tests."""
    main.submitted_orders.clear()
    yield
    main.submitted_orders.clear()


def _forecasts_by_sku(client):
    response = client.get("/api/demand")
    return {f["item_sku"]: f for f in response.json()}


class TestRestockOrderEndpoints:
    """Test suite for restocking order endpoints."""

    def test_demand_includes_cost_and_lead_time(self, client):
        """Test that demand forecasts expose unit_cost and lead_time_days."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        for forecast in response.json():
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["lead_time_days"] > 0

    def test_get_restock_orders_empty(self, client):
        """Test that no restock orders exist initially."""
        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restock_order(self, client):
        """Test submitting a restock order uses server prices and max lead time."""
        forecasts = _forecasts_by_sku(client)
        wdg, flt = forecasts["WDG-001"], forecasts["FLT-405"]

        payload = {
            "budget": 100000,
            "items": [
                {"sku": "WDG-001", "quantity": 10},
                {"sku": "FLT-405", "quantity": 20},
            ],
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        expected_total = 10 * wdg["unit_cost"] + 20 * flt["unit_cost"]
        assert abs(order["total_cost"] - expected_total) < 0.01
        assert order["status"] == "Submitted"
        assert order["order_number"] == "RST-0001"
        assert order["budget"] == 100000
        assert order["items"][0]["name"] == wdg["item_name"]

        expected_lead = max(wdg["lead_time_days"], flt["lead_time_days"])
        assert order["lead_time_days"] == expected_lead
        assert order["submitted_date"] == date.today().isoformat()
        assert order["expected_delivery"] == (
            date.today() + timedelta(days=expected_lead)
        ).isoformat()

    def test_created_order_appears_in_list_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        item = {"sku": "GSK-203", "quantity": 1}
        client.post("/api/restock-orders", json={"budget": 1000, "items": [item]})
        client.post("/api/restock-orders", json={"budget": 1000, "items": [item]})

        response = client.get("/api/restock-orders")
        assert response.status_code == 200

        data = response.json()
        assert [o["order_number"] for o in data] == ["RST-0002", "RST-0001"]

    def test_create_restock_order_unknown_sku(self, client):
        """Test that an unknown SKU is rejected."""
        payload = {
            "budget": 1000,
            "items": [{"sku": "NOPE-999", "quantity": 1}],
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 400
        assert "unknown sku" in response.json()["detail"].lower()
        assert main.submitted_orders == []

    def test_create_restock_order_over_budget(self, client):
        """Test that an order exceeding the budget is rejected."""
        payload = {
            "budget": 100,
            "items": [{"sku": "WDG-001", "quantity": 100}],
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 400
        assert "exceeds budget" in response.json()["detail"].lower()
        assert main.submitted_orders == []

    def test_create_restock_order_duplicate_sku(self, client):
        """Test that the same SKU cannot appear twice in one order."""
        payload = {
            "budget": 100000,
            "items": [
                {"sku": "WDG-001", "quantity": 1},
                {"sku": "WDG-001", "quantity": 1},
            ],
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 400
        assert "duplicate" in response.json()["detail"].lower()
        assert main.submitted_orders == []

    def test_create_restock_order_empty_items(self, client):
        """Test that an order with no items fails validation."""
        response = client.post("/api/restock-orders", json={"budget": 1000, "items": []})
        assert response.status_code == 422

    @pytest.mark.parametrize("quantity", [0, -5])
    def test_create_restock_order_invalid_quantity(self, client, quantity):
        """Test that non-positive quantities fail validation."""
        payload = {
            "budget": 1000,
            "items": [{"sku": "WDG-001", "quantity": quantity}],
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 422
