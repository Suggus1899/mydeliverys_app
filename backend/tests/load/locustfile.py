import random

from locust import HttpUser, between, events, task


class DeliveryUser(HttpUser):
    """Simulates a customer browsing restaurants, creating orders, and reporting payments."""

    wait_time = between(1, 5)
    network_timeout = 10.0

    def on_start(self):
        """Login and get tokens."""
        self.phone = f"+58414{random.randint(1000000, 9999999)}"
        self.otp = "123456"  # In test, we'll mock OTP verification
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        self.address_id = None
        self.current_order_id = None

        # Request OTP
        with self.client.post(
            "/api/v1/auth/request-otp",
            json={"phone": self.phone},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                pass  # OTP sent (mocked in test env)
            else:
                response.failure(f"Request OTP failed: {response.status_code}")

        # Verify OTP (mocked - in test env we'd need a test OTP)
        # For load testing, we'll skip actual auth and use a test token
        # This is a simplified version - real tests would use test users

    @task(70)
    def browse_restaurants(self):
        """Browse restaurants list (cached)."""
        self.client.get("/api/v1/restaurants", name="/api/v1/restaurants")

    @task(70)
    def browse_menu(self):
        """Browse a random restaurant's menu."""
        # First get restaurants list
        with self.client.get("/api/v1/restaurants", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data"):
                    restaurants = data["data"]
                    restaurant = random.choice(restaurants)
                    self.client.get(
                        f"/api/v1/restaurants/{restaurant['id']}/menu",
                        name="/api/v1/restaurants/[id]/menu",
                    )

    @task(15)
    def create_draft_order(self):
        """Create a draft order (checkout)."""
        if not self.access_token:
            return

        # Get a restaurant and menu item
        with self.client.get("/api/v1/restaurants", catch_response=True) as resp:
            if resp.status_code != 200:
                return
            data = resp.json()
            if not data.get("data"):
                return

        restaurant = random.choice(data["data"])
        restaurant_id = restaurant["id"]

        # Get menu
        with self.client.get(
            f"/api/v1/restaurants/{restaurant_id}/menu", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                return
            menu_data = resp.json()

        # Pick random items
        if not menu_data.get("data", {}).get("products"):
            return

        products = menu_data["data"]["products"]
        _product = random.choice(products)
        _quantity = random.randint(1, 3)

        # Need address - skip for now in load test
        # In real test, we'd create a test user with addresses

    @task(10)
    def report_payment(self):
        """Report payment for an order."""
        if not self.current_order_id or not self.access_token:
            return

        self.client.post(
            f"/api/v1/payments/{self.current_order_id}/report",
            json={
                "phase": "FIRST_HALF",
                "method": "PAGO_MOVIL",
                "reference_number": f"REF{random.randint(100000, 999999)}",
                "origin_bank": "BDV",
            },
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Idempotency-Key": f"{random.uuid4()}",
            },
            name="/api/v1/payments/[id]/report",
        )

    @task(5)
    def check_order_status(self):
        """Check order status."""
        if not self.current_order_id or not self.access_token:
            return

        self.client.get(
            f"/api/v1/orders/{self.current_order_id}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            name="/api/v1/orders/[id]",
        )


class DriverUser(HttpUser):
    """Simulates a driver accepting orders, updating location, completing deliveries."""

    wait_time = between(3, 10)
    network_timeout = 10.0

    def on_start(self):
        self.driver_id = None
        self.access_token = None
        self.current_order_id = None
        self.ws = None

    @task(50)
    def update_location(self):
        """Send GPS location via WebSocket (simulated as HTTP for load test)."""
        if not self.current_order_id:
            return

        # Simulate WebSocket ping via HTTP for load testing
        self.client.post(
            "/api/v1/tracking/location",
            json={
                "order_id": str(self.current_order_id),
                "latitude": 9.75 + random.uniform(-0.05, 0.05),
                "longitude": -67.35 + random.uniform(-0.05, 0.05),
                "heading": random.uniform(0, 360),
                "battery_level": random.randint(20, 100),
            },
            name="/api/v1/tracking/location",
        )

    @task(20)
    def accept_order(self):
        """Accept an available order."""
        if not self.access_token:
            return

        # In real test, would query available orders
        pass

    @task(10)
    def pickup_order(self):
        """Mark order as picked up."""
        if not self.current_order_id or not self.access_token:
            return

        self.client.post(
            f"/api/v1/driver/orders/{self.current_order_id}/pickup",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Idempotency-Key": f"{random.uuid4()}",
            },
            name="/api/v1/driver/orders/[id]/pickup",
        )

    @task(10)
    def arrive_customer(self):
        """Mark arrival at customer."""
        if not self.current_order_id or not self.access_token:
            return

        self.client.post(
            f"/api/v1/driver/orders/{self.current_order_id}/arrived",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Idempotency-Key": f"{random.uuid4()}",
            },
            name="/api/v1/driver/orders/[id]/arrived",
        )

    @task(5)
    def collect_cash(self):
        """Collect cash payment."""
        if not self.current_order_id or not self.access_token:
            return

        self.client.post(
            f"/api/v1/driver/orders/{self.current_order_id}/collect-cash",
            json={"amount_usd": "7.50"},
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Idempotency-Key": f"{random.uuid4()}",
            },
            name="/api/v1/driver/orders/[id]/collect-cash",
        )


class AdminUser(HttpUser):
    """Simulates Super Admin verifying payments."""

    wait_time = between(2, 5)
    network_timeout = 10.0

    @task(30)
    def list_pending_payments(self):
        """List pending payments for reconciliation."""
        self.client.get("/api/v1/admin/payments/pending", name="/api/v1/admin/payments/pending")

    @task(20)
    def verify_payment(self):
        """Verify a payment."""
        # In real test, would pick from pending list
        pass

    @task(10)
    def view_map(self):
        """View operations map (WebSocket)."""
        pass


# Custom load shape for 1,500 - 8,000 CCU
class StagesShape:
    stages = [
        {"duration": 120, "users": 500, "spawn_rate": 25},  # Warmup: 0-2 min
        {"duration": 1200, "users": 1500, "spawn_rate": 50},  # Sustained: 2-22 min
        {"duration": 600, "users": 8000, "spawn_rate": 100},  # Stress: 22-32 min
        {"duration": 300, "users": 1500, "spawn_rate": 50},  # Cool down: 32-37 min
        {"duration": 60, "users": 0, "spawn_rate": 100},  # Shutdown: 37-38 min
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None


# Event hooks for metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("Load test starting...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("Load test stopped.")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    if exception:
        print(f"Request failed: {name} - {exception}")
