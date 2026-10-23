import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from .models import AccountProfile, Category, Food, Order, PricingSettings, Restaurant


class OrderWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer = user_model.objects.create_user(
            username="customer@example.test",
            email="customer@example.test",
            first_name="Test Customer",
            password="StrongPass!2026",
        )
        AccountProfile.objects.create(
            user=self.customer,
            role=AccountProfile.Role.CUSTOMER,
            phone="9000000000",
        )
        self.restaurant_user = user_model.objects.create_user(
            username="restaurant@example.test",
            email="restaurant@example.test",
            first_name="Restaurant Owner",
            password="StrongPass!2026",
        )
        AccountProfile.objects.create(
            user=self.restaurant_user,
            role=AccountProfile.Role.RESTAURANT,
            phone="9111111111",
            approved=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.restaurant_user,
            name="Test Kitchen",
            owner_name="Restaurant Owner",
            email="restaurant@example.test",
            approved=True,
            latitude=Decimal("0.000000"),
            longitude=Decimal("0.000000"),
            commission_percentage=Decimal("5.00"),
            max_commission_percentage=Decimal("10.00"),
        )
        self.delivery_user = user_model.objects.create_user(
            username="driver@example.test",
            email="driver@example.test",
            first_name="Test Driver",
            password="StrongPass!2026",
        )
        self.delivery_profile = AccountProfile.objects.create(
            user=self.delivery_user,
            role=AccountProfile.Role.DELIVERY_PARTNER,
            phone="9222222222",
            approved=True,
            latitude=Decimal("0.000000"),
            longitude=Decimal("0.000000"),
            location_updated_at=timezone.now(),
        )
        self.category = Category.objects.create(name="Meals")
        self.food = Food.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Test meal",
            price=Decimal("100.00"),
        )
        PricingSettings.objects.create(
            delivery_fee=Decimal("20.00"),
            delivery_platform_fee=Decimal("10.00"),
            minimum_commission=Decimal("1.00"),
        )
        self.customer_client = Client()
        self.customer_client.force_login(self.customer)
        self._set_cart(self.customer_client)

    def _set_cart(self, client):
        session = client.session
        session["cart"] = {str(self.food.id): 1}
        session.save()

    def _json_post(self, client, path, payload):
        return client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _create_order(self, order_type):
        payload = {"orderType": order_type}
        if order_type == Order.OrderType.DELIVERY:
            payload["deliveryAddress"] = "12 Main Road, Delhi"
        response = self._json_post(
            self.customer_client, "/api/customer/orders", payload
        )
        self.assertEqual(response.status_code, 201, response.content)
        result = response.json()
        self.assertEqual(len(result["confirmationCode"]), 4)
        self.assertTrue(result["confirmationCode"].isdigit())
        return Order.objects.get(id=result["orderId"]), result["confirmationCode"]

    def test_customer_registration_then_login_redirects_to_home(self):
        client = Client()
        registration = self._json_post(
            client,
            "/api/auth/register",
            {
                "fullname": "New Customer",
                "email": "new@example.test",
                "mobile": "9333333333",
                "password": "GoodPass!2026",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.content)
        self.assertEqual(registration.json()["redirect"], "/login.html")

        login_response = self._json_post(
            client,
            "/api/auth/login",
            {"email": "new@example.test", "password": "GoodPass!2026"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["redirect"], "/")
        self.assertEqual(client.get("/").status_code, 200)

    def test_homepage_is_available_without_login_for_food_browsing(self):
        response = Client().get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Food")
        self.assertContains(response, 'id="accountLink"')
        self.assertContains(response, 'id="customerProfile"')
        self.assertContains(response, 'id="customerProfileName"')
        self.assertContains(response, 'id="orderHistory"')
        self.assertContains(response, 'href="#orderHistory">Order history</a>')
        self.assertContains(response, "Sign in")
        self.assertNotContains(response, "localStorage")
        self.assertRedirects(
            Client().get("/login/"),
            "/login.html",
            fetch_redirect_response=False,
        )

    def test_auth_pages_set_csrf_cookie_for_session_api_posts(self):
        for page in (
            "/login.html",
            "/register.html",
            "/resturentloginpage.html",
            "/resturentregisterpage.html",
            "/deliveryregister.html",
        ):
            with self.subTest(page=page):
                response = Client().get(page)
                self.assertEqual(response.status_code, 200)
                self.assertIn("csrftoken", response.cookies)

    def test_food_search_matches_restaurant_name(self):
        response = Client().get("/api/customer/foods?search=Test%20Kitchen")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["restaurantName"], "Test Kitchen")

    def test_nearby_restaurants_match_pincode_then_city(self):
        self.restaurant.city = "Lucknow"
        self.restaurant.pincode = "226001"
        self.restaurant.save(update_fields=["city", "pincode"])
        nearby_restaurant = Restaurant.objects.create(
            name="Nearby Kitchen",
            email="nearby@example.test",
            city="Lucknow",
            pincode="226002",
            approved=True,
        )
        Food.objects.create(
            restaurant=nearby_restaurant,
            category=self.category,
            name="Nearby meal",
            price=Decimal("120.00"),
        )

        response = Client().get(
            "/api/customer/restaurants?city=Lucknow&pincode=226001"
        )

        self.assertEqual(response.status_code, 200)
        restaurants = response.json()["restaurants"]
        self.assertEqual(
            [restaurant["name"] for restaurant in restaurants],
            ["Test Kitchen", "Nearby Kitchen"],
        )
        self.assertEqual(restaurants[0]["proximityMatch"], "Same PIN code")
        self.assertEqual(restaurants[1]["proximityMatch"], "Same city")

    def test_nearby_restaurants_are_ranked_by_gps_distance(self):
        self.restaurant.latitude = Decimal("0.000000")
        self.restaurant.longitude = Decimal("0.020000")
        self.restaurant.save(update_fields=["latitude", "longitude"])
        closest_restaurant = Restaurant.objects.create(
            name="Closest Kitchen",
            email="closest@example.test",
            latitude=Decimal("0.000000"),
            longitude=Decimal("0.010000"),
            approved=True,
        )
        Food.objects.create(
            restaurant=closest_restaurant,
            category=self.category,
            name="Closest meal",
            price=Decimal("120.00"),
        )

        response = Client().get(
            "/api/customer/restaurants?latitude=0&longitude=0"
        )

        self.assertEqual(response.status_code, 200, response.content)
        restaurants = response.json()["restaurants"]
        self.assertEqual(
            [restaurant["name"] for restaurant in restaurants],
            ["Closest Kitchen", "Test Kitchen"],
        )
        self.assertEqual(restaurants[0]["proximityMatch"], "1.1 km away")
        self.assertEqual(restaurants[0]["latitude"], 0)
        self.assertAlmostEqual(restaurants[0]["distanceKm"], 1.11, places=2)

        foods = Client().get(
            "/api/customer/foods?latitude=0&longitude=0"
        ).json()
        self.assertEqual(foods[0]["name"], "Closest meal")
        self.assertAlmostEqual(foods[0]["restaurantDistanceKm"], 1.11, places=2)

    def test_gps_restaurant_search_requires_a_valid_coordinate_pair(self):
        incomplete = Client().get(
            "/api/customer/restaurants?latitude=12.5"
        )
        self.assertEqual(incomplete.status_code, 400)
        invalid = Client().get(
            "/api/customer/restaurants?latitude=91&longitude=0"
        )
        self.assertEqual(invalid.status_code, 400)

    def test_restaurant_results_rank_landmark_market_pincode_then_city(self):
        self.restaurant.city = "Lucknow"
        self.restaurant.pincode = "226001"
        self.restaurant.nearby_landmark = "City Hospital"
        self.restaurant.market = "Other Market"
        self.restaurant.save(
            update_fields=["city", "pincode", "nearby_landmark", "market"]
        )
        match_data = (
            ("A Landmark Match", "City Hospital", "Central Market", "Lucknow", "226002"),
            ("B Market Match", "Other Landmark", "Central Market", "Lucknow", "226002"),
            ("C PIN Match", "Other Landmark", "Other Market", "Kanpur", "226001"),
            ("D City Match", "Other Landmark", "Other Market", "Lucknow", "226003"),
            ("E Far Away", "City Hospital", "Central Market", "Kanpur", "208001"),
        )
        for name, landmark, market, city, pincode in match_data:
            restaurant = Restaurant.objects.create(
                name=name,
                email=f"{name.split()[0].lower()}@example.test",
                nearby_landmark=landmark,
                market=market,
                city=city,
                pincode=pincode,
                approved=True,
            )
            Food.objects.create(
                restaurant=restaurant,
                category=self.category,
                name=f"{name} meal",
                price=Decimal("100.00"),
            )

        response = Client().get(
            "/api/customer/restaurants",
            {
                "nearbyLandmark": "City Hospital",
                "market": "Central Market",
                "pincode": "226001",
                "city": "Lucknow",
            },
        )

        self.assertEqual(response.status_code, 200)
        restaurants = response.json()["restaurants"]
        self.assertEqual(
            [item["name"] for item in restaurants],
            [
                "A Landmark Match",
                "Test Kitchen",
                "B Market Match",
                "C PIN Match",
                "D City Match",
            ],
        )
        self.assertEqual(
            [item["proximityMatch"] for item in restaurants],
            [
                "Nearby landmark",
                "Nearby landmark",
                "Same market",
                "Same PIN code",
                "Same city",
            ],
        )
        self.assertNotIn("E Far Away", [item["name"] for item in restaurants])

    def test_restaurant_profile_saves_market_and_landmark_and_validates_location(self):
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        payload = {
            "restaurantName": self.restaurant.name,
            "ownerName": self.restaurant.owner_name,
            "email": self.restaurant.email,
            "phone": "9000000000",
            "address": "1 Main Road",
            "nearbyLandmark": "City Hospital",
            "market": "Central Market",
            "city": "Lucknow",
            "pincode": "226001",
            "latitude": "26.8467",
            "longitude": "80.9462",
        }

        invalid = dict(payload, pincode="2260")
        invalid_response = restaurant_client.put(
            "/api/restaurant/profile",
            data=json.dumps(invalid),
            content_type="application/json",
        )
        self.assertEqual(invalid_response.status_code, 400)

        saved = restaurant_client.put(
            "/api/restaurant/profile",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(saved.json()["nearbyLandmark"], "City Hospital")
        self.assertEqual(saved.json()["market"], "Central Market")
        self.assertAlmostEqual(saved.json()["latitude"], 26.8467)
        self.assertAlmostEqual(saved.json()["longitude"], 80.9462)
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.city, "Lucknow")
        self.assertEqual(self.restaurant.pincode, "226001")
        self.assertEqual(self.restaurant.nearby_landmark, "City Hospital")
        self.assertEqual(self.restaurant.market, "Central Market")
        self.assertEqual(self.restaurant.latitude, Decimal("26.846700"))
        self.assertEqual(self.restaurant.longitude, Decimal("80.946200"))

        self.restaurant.longitude = None
        with self.assertRaises(ValidationError):
            self.restaurant.full_clean()

    def test_nearby_restaurants_reject_invalid_pincode(self):
        response = Client().get(
            "/api/customer/restaurants?city=Lucknow&pincode=123"
        )

        self.assertEqual(response.status_code, 400)
        missing_location = Client().get(
            "/api/customer/restaurants?city=Lucknow"
        )
        self.assertEqual(missing_location.status_code, 400)

    def test_restaurant_browse_page_uses_dynamic_location_results(self):
        response = Client().get("/resturentpage.html")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="restaurant-browse-ad-slot"')
        self.assertContains(response, 'id="restaurantLocationForm"')
        self.assertContains(response, 'id="nearbyLandmark"')
        self.assertContains(response, 'id="market"')
        self.assertContains(response, 'id="address"')
        self.assertContains(response, 'id="city"')
        self.assertContains(response, 'id="useCurrentLocationButton"')
        self.assertContains(response, 'id="restaurant-list"')
        self.assertNotContains(response, 'id="restaurant-1"')

    def test_restaurant_registration_and_profile_capture_optional_coordinates(self):
        registration_page = Client().get("/resturentregisterpage.html")
        self.assertEqual(registration_page.status_code, 200)
        self.assertContains(registration_page, 'id="captureRestaurantLocationButton"')

        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        profile_page = restaurant_client.get("/resturentprofilepage.html")
        self.assertEqual(profile_page.status_code, 200)
        self.assertContains(profile_page, 'id="restaurantLatitude"')
        self.assertContains(profile_page, 'id="restaurantLongitude"')
        self.assertContains(profile_page, "Use this device's current location")

    def test_customer_homepage_has_an_ad_slot_after_the_hero(self):
        response = Client().get("/homepage.html")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="homepage-ad-slot"')
        main_start = response.content.index(b"<main>")
        self.assertLess(
            response.content.index(b"</section>", main_start),
            response.content.index(b'id="homepage-ad-slot"'),
        )

    def test_food_list_can_be_filtered_to_one_restaurant(self):
        response = Client().get(
            f"/api/customer/foods?restaurantId={self.restaurant.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["restaurantId"], self.restaurant.id)

    def test_homepage_cart_count_can_load_from_backend_cart(self):
        response = self.customer_client.get("/api/customer/cart")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["quantity"], 1)

    def test_current_order_endpoint_returns_clear_empty_state(self):
        response = self.customer_client.get("/api/customer/orders/current")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["message"], "No current order.")

    def test_customer_order_history_returns_only_the_customers_orders(self):
        first_order, _ = self._create_order(Order.OrderType.PICKUP)
        self._set_cart(self.customer_client)
        second_order, _ = self._create_order(Order.OrderType.DELIVERY)

        response = self.customer_client.get("/api/customer/orders/history")

        self.assertEqual(response.status_code, 200)
        orders = response.json()["orders"]
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0]["id"], str(second_order.id))
        self.assertEqual(orders[1]["id"], str(first_order.id))
        self.assertEqual(orders[0]["restaurantName"], self.restaurant.name)
        self.assertEqual(orders[0]["items"][0]["name"], self.food.name)

    def test_customer_order_history_requires_customer_login(self):
        response = Client().get("/api/customer/orders/history")

        self.assertEqual(response.status_code, 401)

    def test_customer_homepage_stays_available_while_restaurant_is_logged_in(self):
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        response = restaurant_client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Food")

        dashboard_response = restaurant_client.get("/resturenthomepage.html")
        self.assertEqual(dashboard_response.status_code, 200)

    def test_restaurant_dashboard_contains_menu_and_order_management(self):
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)

        response = restaurant_client.get("/resturenthomepage.html")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="productForm"')
        self.assertContains(response, 'id="restaurant-orders"')
        self.assertContains(response, 'id="restaurantOrderList"')
        self.assertContains(response, 'id="refreshDashboardBtn"')
        self.assertNotContains(response, "setInterval")
        self.assertContains(response, 'id="total-orders"')
        self.assertContains(response, 'id="restaurant-header-name"')
        self.assertContains(response, 'id="restaurant-profile"')
        self.assertContains(response, 'id="profileSummaryName"')
        self.assertContains(response, 'class="back-to-dashboard"')
        self.assertContains(response, 'id="restaurantLogoutButton"')
        profile_response = restaurant_client.get("/resturentprofilepage.html")
        self.assertContains(profile_response, 'id="restaurantLogoutButton"')
        self.assertContains(
            profile_response,
            'href="/resturenthomepage.html">← Dashboard',
        )
        settings_response = restaurant_client.get("/resturentsettingpage.html")
        self.assertContains(settings_response, 'id="restaurantLogoutButton"')
        self.assertContains(
            settings_response,
            'href="/resturenthomepage.html">← Dashboard',
        )
        self.assertRedirects(
            restaurant_client.get("/resturentorderpage.html"),
            "/resturenthomepage.html#restaurant-orders",
            fetch_redirect_response=False,
        )

    def test_restaurant_dashboard_counts_all_orders_by_status(self):
        orders = []
        for _ in range(3):
            self._set_cart(self.customer_client)
            order, _code = self._create_order(Order.OrderType.PICKUP)
            orders.append(order)

        orders[1].status = Order.Status.ACCEPTED
        orders[1].save(update_fields=["status"])
        orders[2].status = Order.Status.COMPLETED
        orders[2].save(update_fields=["status"])

        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        response = restaurant_client.get("/api/restaurant/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["totalOrders"], 3)
        self.assertEqual(response.json()["pendingOrders"], 1)
        self.assertEqual(response.json()["completedOrders"], 1)
        self.assertEqual(response.json()["notificationCount"], 1)

    def test_customer_registration_form_posts_with_csrf_cookie(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get("/register.html")
        token = page.cookies["csrftoken"].value
        response = client.post(
            "/api/auth/register",
            data=json.dumps(
                {
                    "fullname": "CSRF Customer",
                    "email": "csrf-customer@example.test",
                    "mobile": "9444444440",
                    "password": "SecureCustomer!2026",
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_restaurant_and_delivery_signup_need_admin_approval(self):
        client = Client()
        restaurant_signup = self._json_post(
            client,
            "/api/restaurant/register",
            {
                "restaurantName": "New Diner",
                "ownerName": "New Owner",
                "email": "new-restaurant@example.test",
                "phone": "9444444444",
                "address": "New Road",
                "nearbyLandmark": "City Hospital",
                "market": "Central Market",
                "city": "Lucknow",
                "pincode": "226001",
                "password": "StrongOwner!2026",
            },
        )
        self.assertEqual(restaurant_signup.status_code, 201)
        new_restaurant = Restaurant.objects.get(email="new-restaurant@example.test")
        self.assertEqual(new_restaurant.city, "Lucknow")
        self.assertEqual(new_restaurant.pincode, "226001")
        self.assertEqual(new_restaurant.nearby_landmark, "City Hospital")
        self.assertEqual(new_restaurant.market, "Central Market")
        restaurant_login = self._json_post(
            client,
            "/api/auth/login",
            {
                "email": "new-restaurant@example.test",
                "password": "StrongOwner!2026",
            },
        )
        self.assertEqual(restaurant_login.status_code, 403)
        self.assertIn("approval", restaurant_login.json()["message"])
        self.assertTrue(new_restaurant.registration_number.startswith("HC-"))
        self.assertIsNone(new_restaurant.certificate_issued_at)
        self.assertEqual(
            client.get("/api/restaurant/certificate").status_code, 401
        )
        new_restaurant.approved = True
        new_restaurant.save(update_fields=["approved"])
        self.assertIsNone(new_restaurant.certificate_issued_at)
        new_restaurant.owner.account_profile.approved = True
        new_restaurant.owner.account_profile.save(update_fields=["approved"])
        new_restaurant.refresh_from_db()
        self.assertIsNotNone(new_restaurant.certificate_issued_at)
        approved_login = self._json_post(
            client,
            "/api/auth/login",
            {
                "email": "new-restaurant@example.test",
                "password": "StrongOwner!2026",
            },
        )
        self.assertEqual(approved_login.json()["redirect"], "/resturenthomepage.html")
        self.assertEqual(client.get("/resturenthomepage.html").status_code, 200)

        certificate = client.get("/api/restaurant/certificate")
        self.assertEqual(certificate.status_code, 200)
        self.assertContains(certificate, "Certificate of Authorized Partnership")
        self.assertContains(certificate, "/static/headshot_with_R_logo_icon.png")
        self.assertContains(certificate, "Vishal Shukla")
        self.assertContains(certificate, "CHIEF EXECUTIVE OFFICER · RAMJICART")
        self.assertContains(certificate, new_restaurant.registration_number)
        self.assertContains(certificate, "DATE OF ISSUE")
        self.assertNotContains(certificate, "VALID TILL")
        self.assertContains(certificate, "data:image/svg+xml;base64,")

        verification_url = (
            f"/api/certificate/verify/{new_restaurant.registration_number}"
        )
        verification = Client().get(verification_url)
        self.assertEqual(verification.status_code, 200)
        self.assertContains(verification, "Certificate Verified")
        self.assertContains(verification, "issued by Ramjicart")

        new_restaurant.approved = False
        new_restaurant.save(update_fields=["approved"])
        revoked_verification = Client().get(verification_url)
        self.assertContains(revoked_verification, "Not Verified")

        driver_signup = self._json_post(
            client,
            "/api/delivery/register",
            {
                "name": "New Driver",
                "email": "new-driver@example.test",
                "phone": "9555555555",
                "password": "StrongDriver!2026",
            },
        )
        self.assertEqual(driver_signup.status_code, 201)
        self.assertFalse(
            AccountProfile.objects.get(
                user__email="new-driver@example.test"
            ).approved
        )
        driver = AccountProfile.objects.get(user__email="new-driver@example.test")
        driver.approved = True
        driver.save(update_fields=["approved"])
        driver_client = Client()
        approved_driver_login = self._json_post(
            driver_client,
            "/api/auth/login",
            {
                "email": "new-driver@example.test",
                "password": "StrongDriver!2026",
            },
        )
        self.assertEqual(
            approved_driver_login.json()["redirect"], "/resturentdeliverypage.html"
        )

    def test_customer_cart_and_checkout_require_customer_login(self):
        anonymous = Client()
        self.assertEqual(anonymous.get("/api/customer/cart").status_code, 401)
        self.assertEqual(
            self._json_post(
                anonymous,
                "/api/customer/orders",
                {"orderType": Order.OrderType.PICKUP},
            ).status_code,
            401,
        )

    def test_delivery_quote_has_platform_fee_and_no_gateway_dependency(self):
        response = self._json_post(
            self.customer_client,
            "/api/customer/checkout/quote",
            {"orderType": "delivery"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deliveryFee"], 20.0)
        self.assertEqual(response.json()["platformFee"], 10.0)
        self.assertEqual(response.json()["customerTotal"], 130.0)
        self.assertEqual(response.json()["restaurantPayout"], 95.0)
        self.assertEqual(response.json()["gatewayAmount"], 35.0)
        self.assertEqual(response.json()["onlinePaymentAmount"], 35.0)
        self.assertEqual(
            response.json()["gatewayAmount"],
            response.json()["commissionAmount"]
            + response.json()["deliveryFee"]
            + response.json()["platformFee"],
        )
        self.assertEqual(response.json()["payLaterAmount"], 95.0)
        self.assertEqual(response.json()["payLaterRecipient"], "delivery partner")

    def test_pickup_quote_includes_platform_fee_but_no_delivery_fee(self):
        pricing = PricingSettings.current()
        pricing.pickup_platform_fee = Decimal("6.00")
        pricing.delivery_platform_fee = Decimal("14.00")
        pricing.save()

        response = self._json_post(
            self.customer_client,
            "/api/customer/checkout/quote",
            {"orderType": "pickup"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deliveryFee"], 0.0)
        self.assertEqual(response.json()["platformFee"], 6.0)
        self.assertEqual(response.json()["customerTotal"], 106.0)
        self.assertEqual(response.json()["restaurantPayout"], 95.0)
        self.assertEqual(response.json()["gatewayAmount"], 11.0)
        self.assertEqual(response.json()["onlinePaymentAmount"], 11.0)
        self.assertEqual(response.json()["payLaterAmount"], 95.0)
        self.assertEqual(response.json()["payLaterRecipient"], "restaurant")

        delivery_response = self._json_post(
            self.customer_client,
            "/api/customer/checkout/quote",
            {"orderType": "delivery"},
        )
        self.assertEqual(delivery_response.status_code, 200)
        self.assertEqual(delivery_response.json()["platformFee"], 14.0)
        self.assertEqual(delivery_response.json()["customerTotal"], 134.0)

    def test_checkout_shows_payment_split_without_gateway_collection(self):
        response = self.customer_client.get("/checkout.html")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="commissionFee"')
        self.assertContains(response, 'id="onlinePaymentAmount"')
        self.assertContains(response, "data.gatewayAmount")
        self.assertContains(response, 'id="payLaterAmount"')
        self.assertContains(response, "no online money is collected right now")
        self.assertNotContains(response, "Razorpay")

    def test_admin_can_edit_delivery_and_platform_fees(self):
        admin_user = get_user_model().objects.create_superuser(
            username="admin@example.test",
            email="admin@example.test",
            password="StrongAdmin!2026",
        )
        admin_client = Client()
        admin_client.force_login(admin_user)

        response = admin_client.get("/admin/orders/pricingsettings/1/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="delivery_fee"')
        self.assertContains(response, 'name="pickup_platform_fee"')
        self.assertContains(response, 'name="delivery_platform_fee"')

        update_response = admin_client.post(
            "/admin/orders/pricingsettings/1/change/",
            {
                "delivery_fee": "25.00",
                "pickup_platform_fee": "6.00",
                "delivery_platform_fee": "15.00",
                "_save": "Save",
            },
        )

        self.assertEqual(update_response.status_code, 302)
        pricing = PricingSettings.current()
        self.assertEqual(pricing.delivery_fee, Decimal("25.00"))
        self.assertEqual(pricing.pickup_platform_fee, Decimal("6.00"))
        self.assertEqual(pricing.delivery_platform_fee, Decimal("15.00"))

    def test_pickup_workflow_is_restaurant_confirmed_by_customer_code(self):
        order, code = self._create_order(Order.OrderType.PICKUP)
        self.assertEqual(order.status, Order.Status.PLACED)

        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        for status in ("confirmed", "preparing", "ready"):
            response = restaurant_client.put(
                f"/api/restaurant/orders/{order.id}",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, response.content)

        wrong_code = self._json_post(
            restaurant_client,
            f"/api/restaurant/orders/{order.id}/confirm-pickup",
            {"confirmationCode": "0000" if code != "0000" else "0001"},
        )
        self.assertEqual(wrong_code.status_code, 400)
        confirmed = self._json_post(
            restaurant_client,
            f"/api/restaurant/orders/{order.id}/confirm-pickup",
            {"confirmationCode": code},
        )
        self.assertEqual(confirmed.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_accepted_order_remains_in_restaurant_order_feed(self):
        order, _code = self._create_order(Order.OrderType.PICKUP)
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)

        accepted = restaurant_client.put(
            f"/api/restaurant/orders/{order.id}",
            data=json.dumps({"status": "confirmed"}),
            content_type="application/json",
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)

        orders_response = restaurant_client.get("/api/restaurant/orders")
        self.assertEqual(orders_response.status_code, 200)
        listed_order = next(
            item
            for item in orders_response.json()["orders"]
            if item["id"] == str(order.id)
        )
        self.assertEqual(listed_order["status"], "confirmed")

    def test_dispatch_offers_stay_open_and_are_broadcast_to_nearby_partners(self):
        order, _code = self._create_order(Order.OrderType.DELIVERY)
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        for status in ("confirmed", "preparing", "ready"):
            restaurant_client.put(
                f"/api/restaurant/orders/{order.id}",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )

        driver_client = Client()
        driver_client.force_login(self.delivery_user)
        self.delivery_profile.latitude = Decimal("0.200000")
        self.delivery_profile.save(update_fields=["latitude"])
        out_of_range = driver_client.get("/api/delivery/orders/available").json()
        self.assertEqual(out_of_range["orders"][0]["id"], str(order.id))
        self.assertFalse(out_of_range["orders"][0]["eligible"])
        self.assertEqual(out_of_range["eligibleCount"], 0)
        self.assertEqual(out_of_range["orders"][0]["customer"]["phone"], "")
        rejected = driver_client.put(f"/api/delivery/orders/{order.id}/accept")
        self.assertEqual(rejected.status_code, 409)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.READY_FOR_PICKUP)
        self.assertIsNone(order.delivery_partner_id)

        online = self._json_post(
            driver_client,
            "/api/delivery/location",
            {"latitude": "0.000000", "longitude": "0.000000"},
        )
        self.assertEqual(online.status_code, 200, online.content)
        second_user = get_user_model().objects.create_user(
            username="nearby-driver@example.test",
            email="nearby-driver@example.test",
            password="StrongPass!2026",
        )
        AccountProfile.objects.create(
            user=second_user,
            role=AccountProfile.Role.DELIVERY_PARTNER,
            approved=True,
            latitude=Decimal("0.010000"),
            longitude=Decimal("0.000000"),
            location_updated_at=timezone.now(),
        )
        for user in (self.delivery_user, second_user):
            client = Client()
            client.force_login(user)
            offer = client.get("/api/delivery/orders/available").json()
            self.assertEqual(offer["eligibleCount"], 1)
            self.assertEqual(offer["orders"][0]["id"], str(order.id))
            self.assertTrue(offer["orders"][0]["eligible"])

        accepted = driver_client.put(f"/api/delivery/orders/{order.id}/accept")
        self.assertEqual(accepted.status_code, 200, accepted.content)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.ASSIGNED)

    def test_delivery_workflow_requires_assigned_driver_and_customer_code(self):
        order, code = self._create_order(Order.OrderType.DELIVERY)
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        for status in ("confirmed", "preparing", "ready"):
            response = restaurant_client.put(
                f"/api/restaurant/orders/{order.id}",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, response.content)

        driver_client = Client()
        driver_client.force_login(self.delivery_user)
        delivery_page = driver_client.get("/resturentdeliverypage.html")
        self.assertEqual(delivery_page.status_code, 200)
        self.assertContains(delivery_page, "Available Delivery Orders")
        self.assertContains(delivery_page, 'id="deliveryHistory"')
        available = driver_client.get("/api/delivery/orders/available")
        self.assertEqual(available.status_code, 200)
        self.assertEqual(available.json()["orders"][0]["id"], str(order.id))
        self.assertEqual(
            available.json()["orders"][0]["restaurantPayout"],
            float(order.restaurant_payout),
        )
        self.assertNotIn("total", available.json()["orders"][0])

        accepted = driver_client.put(f"/api/delivery/orders/{order.id}/accept")
        self.assertEqual(accepted.status_code, 200, accepted.content)
        accepted_order = accepted.json()["order"]
        self.assertEqual(accepted_order["statusCode"], Order.Status.ASSIGNED)
        self.assertEqual(accepted_order["items"][0]["name"], "Test meal")
        self.assertEqual(
            accepted_order["restaurantPayout"],
            float(order.restaurant_payout),
        )
        self.assertNotIn("total", accepted_order)
        self.assertIn("phone", accepted_order["customer"])
        current = driver_client.get("/api/delivery/orders/current")
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["order"]["id"], str(order.id))
        self.assertEqual(
            current.json()["order"]["restaurantPayout"],
            float(order.restaurant_payout),
        )
        driver_client.put(
            f"/api/delivery/orders/{order.id}/status",
            data=json.dumps({"status": "PICKED_UP"}),
            content_type="application/json",
        )
        driver_client.put(
            f"/api/delivery/orders/{order.id}/status",
            data=json.dumps({"status": "ON_THE_WAY"}),
            content_type="application/json",
        )
        wrong_code = self._json_post(
            driver_client,
            f"/api/delivery/orders/{order.id}/complete",
            {"confirmationCode": "0000" if code != "0000" else "0001"},
        )
        self.assertEqual(wrong_code.status_code, 400)
        completed = self._json_post(
            driver_client,
            f"/api/delivery/orders/{order.id}/complete",
            {"confirmationCode": code},
        )
        self.assertEqual(completed.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.delivery_partner_id, self.delivery_profile.id)
        self.assertEqual(order.status, Order.Status.COMPLETED)
        dashboard = driver_client.get("/api/delivery/dashboard")
        self.assertFalse(dashboard.json()["earningsTracked"])
        self.assertEqual(
            dashboard.json()["recentCompleted"][0]["id"],
            str(order.id),
        )

    def test_delivery_partner_can_share_and_stop_location(self):
        order, _code = self._create_order(Order.OrderType.DELIVERY)
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        for status in ("confirmed", "preparing", "ready"):
            restaurant_client.put(
                f"/api/restaurant/orders/{order.id}",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )

        driver_client = Client()
        driver_client.force_login(self.delivery_user)
        accepted = driver_client.put(
            f"/api/delivery/orders/{order.id}/accept"
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)
        for status in ("PICKED_UP", "ON_THE_WAY"):
            response = driver_client.put(
                f"/api/delivery/orders/{order.id}/status",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, response.content)

        location_response = self._json_post(
            driver_client,
            f"/api/delivery/orders/{order.id}/location",
            {"latitude": "28.6139", "longitude": "77.2090"},
        )
        self.assertEqual(location_response.status_code, 200)
        live_location = self.customer_client.get(
            f"/api/customer/orders/{order.id}"
        ).json()["deliveryLocation"]
        self.assertEqual(
            {key: live_location[key] for key in ("latitude", "longitude")},
            {"latitude": 28.6139, "longitude": 77.209},
        )

        stopped = driver_client.delete(
            f"/api/delivery/orders/{order.id}/location"
        )
        self.assertEqual(stopped.status_code, 200, stopped.content)
        self.delivery_profile.refresh_from_db()
        self.assertIsNone(self.delivery_profile.latitude)
        self.assertIsNone(self.delivery_profile.longitude)
        self.assertIsNone(
            self.customer_client.get(
                f"/api/customer/orders/{order.id}"
            ).json()["deliveryLocation"]
        )

    def test_delivery_end_to_end_rejects_invalid_steps_and_tracks_every_stage(self):
        order, code = self._create_order(Order.OrderType.DELIVERY)
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        driver_client = Client()
        driver_client.force_login(self.delivery_user)

        response = driver_client.put(f"/api/delivery/orders/{order.id}/accept")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            driver_client.get("/api/delivery/orders/available").json()["orders"],
            [],
        )

        premature_status = driver_client.put(
            f"/api/delivery/orders/{order.id}/status",
            data=json.dumps({"status": "PICKED_UP"}),
            content_type="application/json",
        )
        self.assertEqual(premature_status.status_code, 404)

        transition_cases = (
            ("preparing", 409),
            ("ready", 409),
        )
        for status, expected_status in transition_cases:
            with self.subTest(restaurant_status=status):
                response = restaurant_client.put(
                    f"/api/restaurant/orders/{order.id}",
                    data=json.dumps({"status": status}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, expected_status)

        for status in ("confirmed", "preparing", "ready"):
            response = restaurant_client.put(
                f"/api/restaurant/orders/{order.id}",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, response.content)
            order.refresh_from_db()
            expected = {
                "confirmed": Order.Status.ACCEPTED,
                "preparing": Order.Status.PREPARING,
                "ready": Order.Status.READY_FOR_PICKUP,
            }[status]
            self.assertEqual(order.status, expected)

        available_order = driver_client.get("/api/delivery/orders/available")
        self.assertEqual(
            available_order.json()["orders"][0]["id"], str(order.id)
        )
        accepted = driver_client.put(f"/api/delivery/orders/{order.id}/accept")
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertEqual(
            accepted.json()["order"]["statusCode"], Order.Status.ASSIGNED
        )

        invalid_driver_steps = (
            ("ON_THE_WAY", 409),
            ("COMPLETED", 409),
            ("PICKED_UP", 200),
            ("PICKED_UP", 409),
            ("ON_THE_WAY", 200),
            ("PICKED_UP", 409),
        )
        for status, expected_status in invalid_driver_steps:
            with self.subTest(driver_status=status, expected=expected_status):
                response = driver_client.put(
                    f"/api/delivery/orders/{order.id}/status",
                    data=json.dumps({"status": status}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, expected_status)

        customer_detail = self.customer_client.get(
            f"/api/customer/orders/{order.id}"
        )
        self.assertEqual(customer_detail.status_code, 200)
        self.assertEqual(
            customer_detail.json()["status"], Order.Status.OUT_FOR_DELIVERY
        )
        self.assertEqual(customer_detail.json()["confirmationCode"], code)
        self.assertEqual(
            driver_client.get("/api/delivery/orders/current").json()["order"][
                "id"
            ],
            str(order.id),
        )
        self.assertNotIn(
            "confirmationCode",
            driver_client.get("/api/delivery/orders/current").json()["order"],
        )

        invalid_codes = ("", "12", "abcd", "12345")
        for invalid_code in invalid_codes:
            with self.subTest(confirmation_code=invalid_code):
                response = self._json_post(
                    driver_client,
                    f"/api/delivery/orders/{order.id}/complete",
                    {"confirmationCode": invalid_code},
                )
                self.assertEqual(response.status_code, 400)

        wrong_code = "0000" if code != "0000" else "0001"
        wrong_response = self._json_post(
            driver_client,
            f"/api/delivery/orders/{order.id}/complete",
            {"confirmationCode": wrong_code},
        )
        self.assertEqual(wrong_response.status_code, 400)
        completed = self._json_post(
            driver_client,
            f"/api/delivery/orders/{order.id}/complete",
            {"confirmationCode": code},
        )
        self.assertEqual(completed.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertIsNone(
            driver_client.get("/api/delivery/orders/current").json()["order"]
        )
        self.assertEqual(
            driver_client.get("/api/delivery/dashboard").json()[
                "completedDeliveries"
            ],
            1,
        )

    def test_protected_order_and_delivery_api_role_matrix(self):
        order, _code = self._create_order(Order.OrderType.DELIVERY)
        self._set_cart(self.customer_client)
        other_user = get_user_model().objects.create_user(
            username="other-matrix@example.test",
            email="other-matrix@example.test",
            password="OtherCustomer!2026",
        )
        AccountProfile.objects.create(
            user=other_user,
            role=AccountProfile.Role.CUSTOMER,
            phone="9333333333",
        )
        other_customer_client = Client()
        other_customer_client.force_login(other_user)
        self._set_cart(other_customer_client)

        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        driver_client = Client()
        driver_client.force_login(self.delivery_user)
        actors = (
            ("anonymous", Client()),
            ("order owner", self.customer_client),
            ("other customer", other_customer_client),
            ("restaurant", restaurant_client),
            ("delivery partner", driver_client),
        )
        routes = (
            (
                "customer cart",
                "get",
                "/api/customer/cart",
                (401, 200, 200, 403, 403),
                None,
            ),
            (
                "customer quote",
                "post",
                "/api/customer/checkout/quote",
                (401, 200, 200, 403, 403),
                {"orderType": "delivery"},
            ),
            (
                "customer history",
                "get",
                "/api/customer/orders/history",
                (401, 200, 200, 403, 403),
                None,
            ),
            (
                "customer current order",
                "get",
                "/api/customer/orders/current",
                (401, 200, 404, 403, 403),
                None,
            ),
            (
                "customer order detail",
                "get",
                f"/api/customer/orders/{order.id}",
                (401, 200, 404, 403, 403),
                None,
            ),
            (
                "restaurant profile",
                "get",
                "/api/restaurant/profile",
                (401, 403, 403, 200, 403),
                None,
            ),
            (
                "restaurant dashboard",
                "get",
                "/api/restaurant/dashboard",
                (401, 403, 403, 200, 403),
                None,
            ),
            (
                "restaurant products",
                "get",
                "/api/restaurant/products",
                (401, 403, 403, 200, 403),
                None,
            ),
            (
                "restaurant orders",
                "get",
                "/api/restaurant/orders",
                (401, 403, 403, 200, 403),
                None,
            ),
            (
                "delivery profile",
                "get",
                "/api/delivery/profile",
                (401, 403, 403, 403, 200),
                None,
            ),
            (
                "delivery dashboard",
                "get",
                "/api/delivery/dashboard",
                (401, 403, 403, 403, 200),
                None,
            ),
            (
                "available deliveries",
                "get",
                "/api/delivery/orders/available",
                (401, 403, 403, 403, 200),
                None,
            ),
            (
                "current delivery",
                "get",
                "/api/delivery/orders/current",
                (401, 403, 403, 403, 200),
                None,
            ),
        )

        case_count = 0
        for route_name, method, path, expected_statuses, payload in routes:
            for (actor_name, client), expected_status in zip(
                actors, expected_statuses
            ):
                with self.subTest(route=route_name, actor=actor_name):
                    if method == "get":
                        response = client.get(path)
                    else:
                        response = self._json_post(client, path, payload)
                    self.assertEqual(
                        response.status_code,
                        expected_status,
                        response.content,
                    )
                    case_count += 1
        self.assertEqual(case_count, 65)

    def test_ordering_validation_matrix_rejects_bad_inputs_without_creating_orders(self):
        cases = (
            ("unknown order type", {"orderType": "express"}, ""),
            ("missing order type", {}, ""),
            ("delivery without address", {"orderType": "delivery"}, ""),
            (
                "delivery address over limit",
                {"orderType": "delivery", "deliveryAddress": "x" * 2001},
                "",
            ),
            ("empty cart", {"orderType": "pickup"}, "empty"),
        )
        case_count = 0
        for name, payload, cart_state in cases:
            with self.subTest(case=name):
                client = Client()
                client.force_login(self.customer)
                if cart_state != "empty":
                    self._set_cart(client)
                response = self._json_post(
                    client, "/api/customer/orders", payload
                )
                self.assertEqual(response.status_code, 400)
                case_count += 1

        cart_quantities = (0, -1, 100, "not-a-number", None)
        for quantity in cart_quantities:
            with self.subTest(cart_quantity=quantity):
                response = self._json_post(
                    self.customer_client,
                    "/api/customer/cart",
                    {"foodId": self.food.id, "quantity": quantity},
                )
                self.assertEqual(response.status_code, 400)
                case_count += 1

        quote_types = ("", "pickup-now", "DELIVERY", 1, None)
        for order_type in quote_types:
            with self.subTest(quote_order_type=order_type):
                response = self._json_post(
                    self.customer_client,
                    "/api/customer/checkout/quote",
                    {"orderType": order_type},
                )
                self.assertEqual(response.status_code, 400)
                case_count += 1

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(case_count, 15)

    def test_website_pages_and_logo_route_matrix(self):
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        driver_client = Client()
        driver_client.force_login(self.delivery_user)
        customer_pages = ("/cartpage.html", "/checkout.html", "/orderpage.html")
        restaurant_pages = (
            "/resturenthomepage.html",
            "/resturentprofilepage.html",
            "/resturentsettingpage.html",
        )
        public_pages = (
            "/login.html",
            "/register.html",
            "/resturentloginpage.html",
            "/resturentregisterpage.html",
            "/deliveryregister.html",
            "/contact.html",
            "/terms.html",
            "/privacy.html",
            "/resturentpage.html",
            "/",
        )
        cases = [
            (Client(), path, 200, None)
            for path in public_pages
        ] + [
            (self.customer_client, path, 200, None)
            for path in customer_pages
        ] + [
            (restaurant_client, path, 200, None)
            for path in restaurant_pages
        ] + [
            (driver_client, "/resturentdeliverypage.html", 200, None),
            (
                restaurant_client,
                "/resturentorderpage.html",
                302,
                "/resturenthomepage.html#restaurant-orders",
            ),
        ]
        for client, path, status, redirect_to in cases:
            with self.subTest(page=path):
                response = client.get(path)
                self.assertEqual(response.status_code, status)
                if redirect_to:
                    self.assertEqual(response["Location"], redirect_to)
        self.assertContains(Client().get("/terms.html"), "Terms and Conditions")
        self.assertContains(Client().get("/privacy.html"), "Privacy Policy")
        self.assertContains(
            Client().get("/register.html"),
            'href="/terms.html"',
        )
        self.assertContains(
            Client().get("/register.html"),
            'href="/privacy.html"',
        )

        logo_path = finders.find("logo (2).png")
        self.assertIsNotNone(logo_path)
        with open(logo_path, "rb") as logo_file:
            logo_contents = logo_file.read()
        self.assertTrue(logo_contents.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(logo_contents), 1000)

        logo_pages = (
            (Client(), "/", 200),
            (Client(), "/homepage.html", 200),
            (self.customer_client, "/cartpage.html", 200),
            (self.customer_client, "/checkout.html", 200),
            (Client(), "/contact.html", 200),
            (Client(), "/login.html", 200),
            (Client(), "/register.html", 200),
            (self.customer_client, "/orderpage.html", 200),
            (Client(), "/deliveryregister.html", 200),
            (Client(), "/resturentloginpage.html", 200),
            (Client(), "/resturentregisterpage.html", 200),
            (Client(), "/resturentpage.html", 200),
            (Client(), "/api/certificate/verify/unknown", 404),
        )
        logo_case_count = 0
        for client, path, expected_status in logo_pages:
            with self.subTest(logo_page=path):
                response = client.get(path)
                if expected_status == 404:
                    self.assertEqual(response.status_code, expected_status)
                else:
                    self.assertEqual(response.status_code, expected_status)
                    self.assertContains(
                        response,
                        "/static/logo%20(2).png",
                    )
                logo_case_count += 1
        self.assertEqual(logo_case_count, 13)

    def test_food_fallback_asset_exists_and_old_missing_image_paths_are_gone(self):
        placeholder_path = finders.find("food-placeholder.svg")
        self.assertIsNotNone(placeholder_path)
        with open(placeholder_path, "rb") as placeholder_file:
            self.assertIn(b"<svg", placeholder_file.read())

        for page_name in (
            "cartpage.html",
            "orderpage.html",
            "resturenthomepage.html",
        ):
            with self.subTest(page=page_name):
                with open(
                    finders.find(page_name) or page_name,
                    encoding="utf-8",
                ) as page_file:
                    content = page_file.read()
                self.assertNotIn("food-placeholder.jpg", content)
                self.assertNotIn("burger-fries.png", content)
                self.assertIn("/static/food-placeholder.svg", content)

    def test_delivery_partner_can_accept_and_update_multiple_active_deliveries(self):
        first_order, first_code = self._create_order(Order.OrderType.DELIVERY)
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        for status in ("confirmed", "preparing", "ready"):
            restaurant_client.put(
                f"/api/restaurant/orders/{first_order.id}",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )

        driver_client = Client()
        driver_client.force_login(self.delivery_user)
        accepted = driver_client.put(
            f"/api/delivery/orders/{first_order.id}/accept"
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)

        self._set_cart(self.customer_client)
        second_order, second_code = self._create_order(Order.OrderType.DELIVERY)
        for status in ("confirmed", "preparing", "ready"):
            response = restaurant_client.put(
                f"/api/restaurant/orders/{second_order.id}",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, response.content)

        second_accept = driver_client.put(
            f"/api/delivery/orders/{second_order.id}/accept"
        )
        self.assertEqual(second_accept.status_code, 200, second_accept.content)

        current = driver_client.get("/api/delivery/orders/current")
        self.assertEqual(current.status_code, 200)
        active_orders = current.json()["orders"]
        self.assertEqual(len(active_orders), 2)
        self.assertEqual(
            {item["id"] for item in active_orders},
            {str(first_order.id), str(second_order.id)},
        )

        first_pickup = driver_client.put(
            f"/api/delivery/orders/{first_order.id}/status",
            data=json.dumps({"status": "PICKED_UP"}),
            content_type="application/json",
        )
        self.assertEqual(first_pickup.status_code, 200, first_pickup.content)
        current = driver_client.get("/api/delivery/orders/current").json()
        status_by_id = {item["id"]: item["statusCode"] for item in current["orders"]}
        self.assertEqual(status_by_id[str(first_order.id)], Order.Status.PICKED_UP)
        self.assertEqual(status_by_id[str(second_order.id)], Order.Status.ASSIGNED)

        first_complete = self._json_post(
            driver_client,
            f"/api/delivery/orders/{first_order.id}/complete",
            {"confirmationCode": first_code},
        )
        self.assertEqual(first_complete.status_code, 200, first_complete.content)
        remaining = driver_client.get("/api/delivery/orders/current").json()[
            "orders"
        ]
        self.assertEqual([item["id"] for item in remaining], [str(second_order.id)])

        second_pickup = driver_client.put(
            f"/api/delivery/orders/{second_order.id}/status",
            data=json.dumps({"status": "PICKED_UP"}),
            content_type="application/json",
        )
        self.assertEqual(second_pickup.status_code, 200, second_pickup.content)
        second_complete = self._json_post(
            driver_client,
            f"/api/delivery/orders/{second_order.id}/complete",
            {"confirmationCode": second_code},
        )
        self.assertEqual(second_complete.status_code, 200, second_complete.content)
        self.assertEqual(
            driver_client.get("/api/delivery/orders/current").json()["orders"],
            [],
        )

    def test_customer_confirmation_code_is_not_visible_to_other_customers(self):
        order, _ = self._create_order(Order.OrderType.DELIVERY)
        other = get_user_model().objects.create_user(
            username="other@example.test",
            email="other@example.test",
            password="StrongPass!2026",
        )
        AccountProfile.objects.create(user=other, role=AccountProfile.Role.CUSTOMER)
        other_client = Client()
        other_client.force_login(other)
        response = other_client.get(f"/api/customer/orders/{order.id}")
        self.assertEqual(response.status_code, 404)

    def test_confirmation_code_locks_after_five_wrong_attempts(self):
        order, code = self._create_order(Order.OrderType.PICKUP)
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        for status in ("confirmed", "preparing", "ready"):
            restaurant_client.put(
                f"/api/restaurant/orders/{order.id}",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )
        wrong_code = "0000" if code != "0000" else "0001"
        for _ in range(5):
            response = self._json_post(
                restaurant_client,
                f"/api/restaurant/orders/{order.id}/confirm-pickup",
                {"confirmationCode": wrong_code},
            )
            self.assertEqual(response.status_code, 400)
        blocked = self._json_post(
            restaurant_client,
            f"/api/restaurant/orders/{order.id}/confirm-pickup",
            {"confirmationCode": code},
        )
        self.assertEqual(blocked.status_code, 429)

    def test_commission_cannot_exceed_approved_cap(self):
        self.restaurant.commission_percentage = Decimal("11.00")
        with self.assertRaises(ValidationError):
            self.restaurant.full_clean()

    def test_customer_checkout_page_is_served(self):
        response = self.customer_client.get("/checkout.html")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Place order")

    def test_delivery_order_keeps_destination_coordinates_for_map_links(self):
        self.restaurant.latitude = Decimal("26.846700")
        self.restaurant.longitude = Decimal("80.946200")
        self.restaurant.save(update_fields=["latitude", "longitude"])

        response = self._json_post(
            self.customer_client,
            "/api/customer/orders",
            {
                "orderType": "delivery",
                "deliveryAddress": "12 Main Road, Delhi",
                "latitude": "28.613900",
                "longitude": "77.209000",
            },
        )

        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get(id=response.json()["orderId"])
        self.assertEqual(order.delivery_latitude, Decimal("28.613900"))
        self.assertEqual(order.delivery_longitude, Decimal("77.209000"))
        detail = self.customer_client.get(
            f"/api/customer/orders/{order.id}"
        ).json()
        self.assertEqual(
            detail["deliveryCoordinates"],
            {"latitude": 28.6139, "longitude": 77.209},
        )
        self.assertEqual(
            detail["restaurant"]["location"],
            {"latitude": 26.8467, "longitude": 80.9462},
        )

    def test_restaurant_can_add_menu_item_and_update_order_settings(self):
        restaurant_client = Client()
        restaurant_client.force_login(self.restaurant_user)
        created = restaurant_client.post(
            "/api/restaurant/products",
            {
                "productName": "New meal",
                "productCategory": "Rice",
                "productPrice": "45.50",
                "productDescription": "Freshly cooked",
                "productImage": "",
            },
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["name"], "New meal")
        listed = restaurant_client.get("/api/restaurant/products")
        self.assertEqual(len(listed.json()), 2)

        settings_response = restaurant_client.put(
            "/api/restaurant/settings",
            data=json.dumps(
                {
                    "acceptOrders": False,
                    "orderNotifications": True,
                    "orderSound": False,
                    "email": self.restaurant_user.email,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(settings_response.status_code, 200)
        self.restaurant.refresh_from_db()
        self.assertFalse(self.restaurant.accepting_orders)
