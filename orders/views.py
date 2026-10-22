import base64
import json
import secrets
from io import BytesIO
from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST
import qrcode
from qrcode.image.svg import SvgPathImage

from .models import Category, Food, Order, OrderItem, PricingSettings, Restaurant
from .models import AccountProfile
from .pricing import money, quote_order


MAX_CART_QUANTITY = 99
FRONTEND_PAGES = {
    "homepage",
    "cartpage",
    "checkout",
    "orderpage",
    "contact",
    "terms",
    "privacy",
    "login",
    "register",
    "resturentpage",
    "resturentloginpage",
    "resturentregisterpage",
    "resturenthomepage",
    "resturentorderpage",
    "resturentprofilepage",
    "resturentsettingpage",
    "resturentdeliverypage",
    "deliveryregister",
}


@ensure_csrf_cookie
def homepage(request):
    return render(request, "homepage.html")


@ensure_csrf_cookie
def frontend_page(request, page):
    if page not in FRONTEND_PAGES:
        return JsonResponse({"message": "Page not found."}, status=404)
    if page in {"resturenthomepage", "resturentorderpage", "resturentprofilepage", "resturentsettingpage"}:
        if not request.user.is_authenticated:
            return redirect_login(request)
        profile = _account_profile(request)
        if not profile or profile.role != AccountProfile.Role.RESTAURANT:
            return JsonResponse({"message": "Restaurant account required."}, status=403)
        if page == "resturentorderpage":
            return redirect("/resturenthomepage.html#restaurant-orders")
    if page == "resturentdeliverypage":
        if not request.user.is_authenticated:
            return redirect_login(request)
        profile = _account_profile(request)
        if not profile or profile.role != AccountProfile.Role.DELIVERY_PARTNER:
            return JsonResponse({"message": "Delivery partner account required."}, status=403)
    if page in {"cartpage", "checkout", "orderpage"}:
        if not request.user.is_authenticated:
            return redirect_login(request)
        profile = _account_profile(request)
        if not profile or profile.role != AccountProfile.Role.CUSTOMER:
            return JsonResponse({"message": "Customer account required."}, status=403)
    return render(request, f"{page}.html")


def redirect_login(_request):
    from django.shortcuts import redirect

    return redirect("/login.html")


def _account_profile(request):
    if not request.user.is_authenticated:
        return None
    try:
        return request.user.account_profile
    except AccountProfile.DoesNotExist:
        return None


def _profile_is_approved(profile):
    if not profile.approved:
        return False
    if profile.role == AccountProfile.Role.RESTAURANT:
        try:
            return profile.user.restaurant.approved
        except Restaurant.DoesNotExist:
            return False
    return True


def _require_role(request, *roles):
    if not request.user.is_authenticated:
        return _error("Please log in first.", 401)
    profile = _account_profile(request)
    if profile is None or profile.role not in roles:
        return _error("Your account is not allowed to perform this action.", 403)
    if profile.role != AccountProfile.Role.CUSTOMER and not _profile_is_approved(profile):
        return _error("Your account is waiting for administrator approval.", 403)
    return None


def _role_redirect(profile):
    if profile.role == AccountProfile.Role.RESTAURANT:
        return "/resturenthomepage.html"
    if profile.role == AccountProfile.Role.DELIVERY_PARTNER:
        return "/resturentdeliverypage.html"
    return "/"


def _json_body(request):
    try:
        value = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Request body must be valid JSON.")
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object.")
    return value


def _error(message, status=400):
    return JsonResponse({"message": message}, status=status)


def _cart_items(request):
    raw_cart = request.session.get("cart", {})
    if not isinstance(raw_cart, dict):
        return []
    food_ids = []
    for raw_id, quantity in raw_cart.items():
        try:
            food_id = int(raw_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue
        if food_id > 0 and 1 <= quantity <= MAX_CART_QUANTITY:
            food_ids.append(food_id)
    foods = Food.objects.filter(
        id__in=food_ids,
        available=True,
        restaurant__approved=True,
        restaurant__accepting_orders=True,
    ).select_related("restaurant", "category")
    food_by_id = {food.id: food for food in foods}
    items = []
    for raw_id, raw_quantity in raw_cart.items():
        try:
            food_id = int(raw_id)
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            continue
        food = food_by_id.get(food_id)
        if food and 1 <= quantity <= MAX_CART_QUANTITY:
            items.append((food, quantity))
    return items


def _cart_summary(items):
    item_total = money(
        sum((food.price * quantity for food, quantity in items), Decimal("0"))
    )
    restaurant_ids = {food.restaurant_id for food, _ in items}
    restaurant = (
        Restaurant.objects.get(id=next(iter(restaurant_ids)))
        if len(restaurant_ids) == 1
        else None
    )
    return item_total, restaurant


def _serialize_cart(request):
    items = _cart_items(request)
    item_total, restaurant = _cart_summary(items)
    serialized_items = [
        {
            "id": food.id,
            "productId": food.id,
            "name": food.name,
            "description": food.description,
            "image": food.image,
            "foodType": food.category.name if food.category else "",
            "price": float(food.price),
            "quantity": quantity,
        }
        for food, quantity in items
    ]
    return {
        "items": serialized_items,
        "itemTotal": float(item_total),
        "deliveryFee": 0,
        "discount": 0,
        "total": float(item_total),
        "restaurant": (
            {"id": restaurant.id, "name": restaurant.name} if restaurant else None
        ),
    }


@csrf_protect
@require_POST
def auth_register(request):
    try:
        data = _json_body(request)
    except ValueError as error:
        return _error(str(error))
    name = str(data.get("fullname", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("mobile", "")).strip()
    password = str(data.get("password", ""))
    if not name or len(name) > 150 or not phone or len(phone) > 30:
        return _error("Enter a valid name and phone number.")
    try:
        validate_email(email)
    except ValidationError:
        return _error("Enter a valid email address.")
    if len(email) > 150:
        return _error("Email address must be 150 characters or fewer.")
    if get_user_model().objects.filter(email__iexact=email).exists():
        return _error("An account with this email already exists.", 409)
    user = get_user_model()(username=email, email=email, first_name=name)
    try:
        validate_password(password, user=user)
    except ValidationError as error:
        return _error(" ".join(error.messages))
    with transaction.atomic():
        user.set_password(password)
        user.save()
        AccountProfile.objects.create(
            user=user, role=AccountProfile.Role.CUSTOMER, phone=phone
        )
    return JsonResponse(
        {
            "message": "Registration successful. Please log in.",
            "redirect": "/login.html",
        },
        status=201,
    )


@csrf_protect
@require_POST
def restaurant_register(request):
    try:
        data = _json_body(request)
    except ValueError as error:
        return _error(str(error))
    name = str(data.get("restaurantName", "")).strip()
    owner_name = str(data.get("ownerName", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    address = str(data.get("address", "")).strip()
    nearby_landmark = str(data.get("nearbyLandmark", "")).strip()
    market = str(data.get("market", "")).strip()
    city = str(data.get("city", "")).strip()
    pincode = str(data.get("pincode", "")).strip()
    password = str(data.get("password", ""))
    if (
        not name
        or len(name) > 160
        or not owner_name
        or not phone
        or not address
        or not city
        or not pincode
    ):
        return _error("Complete all restaurant, address, city, PIN code, and owner details.")
    if len(phone) > 30 or len(address) > 2000:
        return _error("Restaurant details are too long.")
    if len(city) > 100 or len(nearby_landmark) > 160 or len(market) > 160:
        return _error("Restaurant location details are too long.")
    if len(pincode) != 6 or not pincode.isdigit():
        return _error("Enter a valid 6-digit restaurant PIN code.")
    try:
        validate_email(email)
    except ValidationError:
        return _error("Enter a valid email address.")
    if len(email) > 150:
        return _error("Email address must be 150 characters or fewer.")
    if get_user_model().objects.filter(email__iexact=email).exists():
        return _error("An account with this email already exists.", 409)
    user = get_user_model()(username=email, email=email, first_name=owner_name)
    try:
        validate_password(password, user=user)
    except ValidationError as error:
        return _error(" ".join(error.messages))
    with transaction.atomic():
        user.set_password(password)
        user.save()
        AccountProfile.objects.create(
            user=user,
            role=AccountProfile.Role.RESTAURANT,
            phone=phone,
            approved=False,
        )
        Restaurant.objects.create(
            owner=user,
            name=name,
            owner_name=owner_name,
            email=email,
            phone=phone,
            address=address,
            nearby_landmark=nearby_landmark,
            market=market,
            city=city,
            pincode=pincode,
            approved=False,
        )
    return JsonResponse(
        {
            "message": (
                "Restaurant registration submitted and is waiting for admin "
                "approval. Your partnership certificate will be available "
                "after approval."
            ),
            "redirect": "/resturentloginpage.html",
        },
        status=201,
    )


@csrf_protect
@require_POST
def delivery_register(request):
    try:
        data = _json_body(request)
    except ValueError as error:
        return _error(str(error))
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))
    if not name or len(name) > 150 or not phone or len(phone) > 30:
        return _error("Enter a valid name and phone number.")
    try:
        validate_email(email)
    except ValidationError:
        return _error("Enter a valid email address.")
    if len(email) > 150:
        return _error("Email address must be 150 characters or fewer.")
    if get_user_model().objects.filter(email__iexact=email).exists():
        return _error("An account with this email already exists.", 409)
    user = get_user_model()(username=email, email=email, first_name=name)
    try:
        validate_password(password, user=user)
    except ValidationError as error:
        return _error(" ".join(error.messages))
    with transaction.atomic():
        user.set_password(password)
        user.save()
        AccountProfile.objects.create(
            user=user,
            role=AccountProfile.Role.DELIVERY_PARTNER,
            phone=phone,
            approved=False,
        )
    return JsonResponse(
        {
            "message": "Delivery partner account created. Admin approval is required before accepting orders.",
            "redirect": "/resturentloginpage.html",
        },
        status=201,
    )


@require_GET
def restaurant_certificate(request):
    restaurant, error = _restaurant_for_request(request)
    if error:
        return error
    if restaurant.certificate_issued_at is None:
        return _error("Your certificate will be available after admin approval.", 403)

    verification_url = request.build_absolute_uri(
        reverse(
            "verify-certificate",
            kwargs={"registration_number": restaurant.registration_number},
        )
    )
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(verification_url)
    qr.make(fit=True)
    qr_image = qr.make_image(image_factory=SvgPathImage)
    qr_buffer = BytesIO()
    qr_image.save(qr_buffer)
    qr_data_uri = "data:image/svg+xml;base64," + base64.b64encode(
        qr_buffer.getvalue()
    ).decode("ascii")
    return render(
        request,
        "certificate.html",
        {
            "restaurant": restaurant,
            "issued_on": timezone.localtime(
                restaurant.certificate_issued_at
            ).date(),
            "qr_data_uri": qr_data_uri,
        },
    )


@require_GET
def verify_certificate(request, registration_number):
    restaurant = get_object_or_404(
        Restaurant, registration_number=registration_number
    )
    profile = None
    if restaurant.owner_id:
        profile = AccountProfile.objects.filter(
            user_id=restaurant.owner_id,
            role=AccountProfile.Role.RESTAURANT,
        ).first()
    verified = bool(
        restaurant.approved
        and restaurant.certificate_issued_at
        and profile
        and profile.approved
    )
    return render(
        request,
        "certificate_verification.html",
        {
            "restaurant": restaurant,
            "verified": verified,
        },
    )


@csrf_protect
@require_POST
def auth_login(request):
    try:
        data = _json_body(request)
    except ValueError as error:
        return _error(str(error))
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = authenticate(request, username=email, password=password)
    if user is None:
        return _error("Email or password is incorrect.", 401)
    profile = _account_profile_for_user(user)
    if profile is None:
        return _error("This account is not configured. Contact support.", 403)
    if profile.role != AccountProfile.Role.CUSTOMER and not _profile_is_approved(profile):
        return _error(
            "Your account is waiting for administrator approval before login.",
            403,
        )
    login(request, user)
    return JsonResponse(
        {
            "message": "Login successful.",
            "role": profile.role,
            "redirect": _role_redirect(profile),
        }
    )


def _account_profile_for_user(user):
    try:
        return user.account_profile
    except AccountProfile.DoesNotExist:
        return None


@csrf_protect
@require_POST
def auth_logout(request):
    logout(request)
    return JsonResponse({"message": "Logged out.", "redirect": "/login.html"})


@require_GET
def auth_me(request):
    if not request.user.is_authenticated:
        return _error("Please log in first.", 401)
    profile = _account_profile(request)
    if profile is None:
        return _error("Account profile is not configured.", 403)
    return JsonResponse(
        {
            "name": request.user.first_name or request.user.email,
            "email": request.user.email,
            "phone": profile.phone,
            "role": profile.role,
            "approved": profile.approved,
        }
    )


@require_GET
def categories(_request):
    data = list(Category.objects.order_by("name").values("id", "name"))
    return JsonResponse(data, safe=False)


@require_GET
def customer_restaurants(request):
    city = request.GET.get("city", "").strip()
    pincode = request.GET.get("pincode", "").strip()
    nearby_landmark = request.GET.get("nearbyLandmark", "").strip()
    market = request.GET.get("market", "").strip()
    if not city or not pincode:
        return _error("Enter your city and 6-digit pincode to find restaurants.")
    if not pincode.isdigit() or len(pincode) != 6:
        return _error("Enter a valid 6-digit pincode.")
    if len(city) > 100 or len(nearby_landmark) > 160 or len(market) > 160:
        return _error("Location details are too long.")

    restaurants = Restaurant.objects.filter(
        approved=True,
        accepting_orders=True,
        foods__available=True,
    ).distinct().prefetch_related("foods__category")
    if city and pincode:
        restaurants = restaurants.filter(
            Q(city__iexact=city) | Q(pincode=pincode)
        )
    elif city:
        restaurants = restaurants.filter(city__iexact=city)
    elif pincode:
        restaurants = restaurants.filter(pincode=pincode)

    restaurant_list = list(restaurants)

    def location_match(restaurant):
        landmark_match = bool(
            nearby_landmark
            and restaurant.nearby_landmark.casefold()
            == nearby_landmark.casefold()
        )
        market_match = bool(
            market and restaurant.market.casefold() == market.casefold()
        )
        pincode_match = bool(pincode and restaurant.pincode == pincode)
        city_match = bool(city and restaurant.city.casefold() == city.casefold())
        return landmark_match, market_match, pincode_match, city_match

    def location_sort_key(restaurant):
        matches = location_match(restaurant)
        supplied = (nearby_landmark, market, pincode, city)
        priority = tuple(
            -int(match)
            for match, value in zip(matches, supplied)
            if value
        )
        return (*priority, restaurant.name.casefold())

    restaurant_list.sort(key=location_sort_key)

    return JsonResponse(
        {
            "restaurants": [
                {
                    "proximityMatch": (
                        "Nearby landmark"
                        if location_match(restaurant)[0]
                        else "Same market"
                        if location_match(restaurant)[1]
                        else "Same PIN code"
                        if location_match(restaurant)[2]
                        else "Same city"
                    ),
                    "id": restaurant.id,
                    "name": restaurant.name,
                    "address": restaurant.address,
                    "city": restaurant.city,
                    "pincode": restaurant.pincode,
                    "nearbyLandmark": restaurant.nearby_landmark,
                    "market": restaurant.market,
                    "logo": _restaurant_logo_url(restaurant),
                    "categories": sorted(
                        {
                            food.category.name
                            for food in restaurant.foods.all()
                            if food.available and food.category
                        }
                    ),
                }
                for restaurant in restaurant_list
            ]
        }
    )


@require_GET
def foods(request):
    queryset = Food.objects.filter(
        available=True,
        restaurant__approved=True,
        restaurant__accepting_orders=True,
    ).select_related("restaurant", "category")
    category_id = request.GET.get("categoryId")
    if category_id:
        try:
            category_id = int(category_id)
        except ValueError:
            return _error("categoryId must be a number.")
        queryset = queryset.filter(category_id=category_id)
    restaurant_id = request.GET.get("restaurantId")
    if restaurant_id:
        try:
            restaurant_id = int(restaurant_id)
        except ValueError:
            return _error("restaurantId must be a number.")
        queryset = queryset.filter(restaurant_id=restaurant_id)
    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(restaurant__name__icontains=search)
        )
    data = [
        {
            "id": food.id,
            "name": food.name,
            "description": food.description,
            "image": food.image,
            "price": float(food.price),
            "restaurantId": food.restaurant_id,
            "restaurantName": food.restaurant.name,
            "categoryId": food.category_id,
        }
        for food in queryset
    ]
    return JsonResponse(data, safe=False)


@csrf_protect
@require_http_methods(["GET", "POST"])
def cart(request):
    role_error = _require_role(request, AccountProfile.Role.CUSTOMER)
    if role_error:
        return role_error
    if request.method == "GET":
        return JsonResponse(_serialize_cart(request))
    try:
        data = _json_body(request)
        food_id = int(data.get("foodId", data.get("productId")))
        quantity = int(data.get("quantity", 1))
    except (ValueError, TypeError):
        return _error("A valid foodId and quantity are required.")
    if not 1 <= quantity <= MAX_CART_QUANTITY:
        return _error(f"Quantity must be between 1 and {MAX_CART_QUANTITY}.")
    food = Food.objects.filter(
        id=food_id,
        available=True,
        restaurant__approved=True,
        restaurant__accepting_orders=True,
    ).first()
    if food is None:
        return _error("This food is not currently available.", 404)

    existing = request.session.get("cart", {})
    if not isinstance(existing, dict):
        existing = {}
    current_items = _cart_items(request)
    other_restaurants = {
        current_food.restaurant_id
        for current_food, _ in current_items
        if current_food.restaurant_id != food.restaurant_id
    }
    if other_restaurants:
        return _error("Please finish or clear the current restaurant's cart first.")
    new_quantity = int(existing.get(str(food.id), 0)) + quantity
    if new_quantity > MAX_CART_QUANTITY:
        return _error(f"Maximum quantity is {MAX_CART_QUANTITY}.")
    existing[str(food.id)] = new_quantity
    request.session["cart"] = existing
    return JsonResponse(_serialize_cart(request), status=201)


@csrf_protect
@require_http_methods(["PUT", "DELETE"])
def cart_item(request, food_id):
    role_error = _require_role(request, AccountProfile.Role.CUSTOMER)
    if role_error:
        return role_error
    cart_data = request.session.get("cart", {})
    if not isinstance(cart_data, dict):
        cart_data = {}
    if request.method == "DELETE":
        cart_data.pop(str(food_id), None)
    else:
        try:
            quantity = int(_json_body(request).get("quantity"))
        except (ValueError, TypeError):
            return _error("A valid quantity is required.")
        if not 1 <= quantity <= MAX_CART_QUANTITY:
            return _error(f"Quantity must be between 1 and {MAX_CART_QUANTITY}.")
        if str(food_id) not in cart_data:
            return _error("Cart item not found.", 404)
        cart_data[str(food_id)] = quantity
    request.session["cart"] = cart_data
    return JsonResponse(_serialize_cart(request))


def _quote_for_cart(request, order_type):
    items = _cart_items(request)
    if not items:
        raise ValidationError("Your cart is empty or contains unavailable food.")
    item_total, restaurant = _cart_summary(items)
    if restaurant is None:
        raise ValidationError("A cart can contain food from only one restaurant.")
    return items, restaurant, quote_order(restaurant, item_total, order_type)


@csrf_protect
@require_POST
def checkout_quote(request):
    role_error = _require_role(request, AccountProfile.Role.CUSTOMER)
    if role_error:
        return role_error
    try:
        order_type = _json_body(request).get("orderType", "")
        _, _, quote = _quote_for_cart(request, order_type)
    except ValueError as error:
        return _error(str(error))
    except ValidationError as error:
        return _error("; ".join(error.messages))
    except PricingSettings.DoesNotExist:
        return _error("Marketplace pricing is not configured.", 503)
    return JsonResponse({key: float(value) if isinstance(value, Decimal) else value
                         for key, value in quote.items()})


@csrf_protect
@require_POST
def create_order(request):
    role_error = _require_role(request, AccountProfile.Role.CUSTOMER)
    if role_error:
        return role_error
    try:
        data = _json_body(request)
        order_type = data.get("orderType", "")
        items, restaurant, quote = _quote_for_cart(request, order_type)
    except ValueError as error:
        return _error(str(error))
    except ValidationError as error:
        return _error("; ".join(error.messages))
    except PricingSettings.DoesNotExist:
        return _error("Pricing could not be loaded. Please try again.", 503)

    delivery_address = str(data.get("deliveryAddress", "")).strip()
    profile = _account_profile(request)
    customer_name = request.user.get_full_name().strip() or request.user.email
    customer_phone = profile.phone
    customer_email = request.user.email
    if not customer_phone:
        return _error("Add a phone number to your account before ordering.")
    if order_type == Order.OrderType.DELIVERY and not delivery_address:
        return _error("A delivery address is required for delivery orders.")
    if len(delivery_address) > 2000:
        return _error("Delivery address is too long.")
    confirmation_code = f"{secrets.randbelow(10000):04d}"

    with transaction.atomic():
        order = Order.objects.create(
            customer=request.user,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            delivery_address=delivery_address,
            restaurant=restaurant,
            order_type=order_type,
            item_total=quote["itemTotal"],
            commission_percentage=quote["commissionPercentage"],
            commission_amount=quote["commissionAmount"],
            delivery_fee=quote["deliveryFee"],
            platform_fee=quote["platformFee"],
            customer_total=quote["customerTotal"],
            restaurant_payout=quote["restaurantPayout"],
            confirmation_code=confirmation_code,
            status=Order.Status.PLACED,
        )
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    food=food,
                    food_name=food.name,
                    unit_price=food.price,
                    quantity=quantity,
                    line_total=money(food.price * quantity),
                )
                for food, quantity in items
            ]
        )

    request.session["current_order_id"] = str(order.id)
    request.session["cart"] = {}
    return JsonResponse(
        {
            "orderId": str(order.id),
            "customerName": customer_name,
            "customerEmail": customer_email,
            "customerPhone": customer_phone,
            "confirmationCode": confirmation_code,
            "status": order.status,
            "quote": {key: float(value) if isinstance(value, Decimal) else value
                      for key, value in quote.items()},
        },
        status=201,
    )


@require_GET
def order_detail(request, order_id):
    role_error = _require_role(request, AccountProfile.Role.CUSTOMER)
    if role_error:
        return role_error
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    order = (
        Order.objects.select_related("restaurant")
        .prefetch_related("items")
        .get(id=order.id)
    )
    data = {
        "id": str(order.id),
        "status": order.status,
        "statusText": {
            Order.Status.PLACED: "Order sent to restaurant",
            Order.Status.PAYMENT_PENDING: "Waiting for payment",
            Order.Status.PAID: "Order confirmed",
            Order.Status.ACCEPTED: "Restaurant accepted your order",
            Order.Status.PREPARING: "Your food is being prepared",
            Order.Status.READY_FOR_PICKUP: "Ready for pickup",
            Order.Status.ASSIGNED: "Delivery partner assigned",
            Order.Status.PICKED_UP: "Picked up",
            Order.Status.OUT_FOR_DELIVERY: "Your food is on the way!",
            Order.Status.COMPLETED: "Order delivered",
            Order.Status.CANCELLED: "Order cancelled",
            Order.Status.PAYMENT_FAILED: "Payment failed",
        }[order.status],
        "orderType": order.order_type,
        "deliveryAddress": order.delivery_address,
        "itemTotal": float(order.item_total),
        "commission": float(order.commission_amount),
        "deliveryFee": float(order.delivery_fee),
        "platformFee": float(order.platform_fee),
        "discount": 0,
        "restaurantPayout": float(order.restaurant_payout),
        "total": float(order.customer_total),
        "confirmationCode": order.confirmation_code,
        "orderTypeText": "Pickup (customer is on the way)" if order.order_type == "pickup" else "Home delivery",
        "paymentMethod": "Pay at restaurant" if order.order_type == "pickup" else "Pay on delivery",
        "estimatedArrival": "Pickup" if order.order_type == "pickup" else "To be confirmed",
        "timeline": _order_timeline(order.status),
        "restaurant": {
            "id": order.restaurant_id,
            "name": order.restaurant.name,
            "details": order.restaurant.address,
            "image": _restaurant_logo_url(order.restaurant),
        },
        "items": [
            {
                "name": item.food_name,
                "price": float(item.unit_price),
                "quantity": item.quantity,
                "image": item.food.image,
            }
            for item in order.items.all()
        ],
    }
    return JsonResponse(data)


def _restaurant_logo_url(restaurant):
    return restaurant.logo.url if restaurant.logo else ""


def _restaurant_for_request(request):
    role_error = _require_role(request, AccountProfile.Role.RESTAURANT)
    if role_error:
        return None, role_error
    try:
        restaurant = request.user.restaurant
        if not restaurant.approved:
            return None, _error("Restaurant is waiting for administrator approval.", 403)
        return restaurant, None
    except Restaurant.DoesNotExist:
        return None, _error("Restaurant profile is not configured.", 404)


def _restaurant_order_data(order):
    display_status = {
        Order.Status.PLACED: "pending",
        Order.Status.ACCEPTED: "confirmed",
        Order.Status.PREPARING: "preparing",
        Order.Status.READY_FOR_PICKUP: "ready",
        Order.Status.ASSIGNED: "assigned",
        Order.Status.PICKED_UP: "picked_up",
        Order.Status.OUT_FOR_DELIVERY: "on_the_way",
        Order.Status.COMPLETED: "completed",
        Order.Status.CANCELLED: "cancelled",
        Order.Status.PAYMENT_PENDING: "pending",
        Order.Status.PAID: "confirmed",
        Order.Status.PAYMENT_FAILED: "cancelled",
    }[order.status]
    return {
        "id": str(order.id),
        "orderNumber": str(order.id).split("-")[0].upper(),
        "date": timezone.localtime(order.created_at).strftime("%d %b %Y, %I:%M %p"),
        "status": display_status,
        "orderType": order.order_type,
        "orderTypeText": "Pickup (customer is on the way)" if order.order_type == "pickup" else "Delivery",
        "customerName": order.customer_name,
        "customerPhone": order.customer_phone,
        "address": order.delivery_address or "Customer will collect at restaurant",
        "paymentMethod": "Pay at restaurant" if order.order_type == "pickup" else "Pay on delivery",
        "total": float(order.customer_total),
        "items": [
            {
                "name": item.food_name,
                "quantity": item.quantity,
                "price": float(item.line_total),
            }
            for item in order.items.all()
        ],
    }


@csrf_protect
@require_http_methods(["GET", "PUT"])
def restaurant_profile(request):
    restaurant, error = _restaurant_for_request(request)
    if error:
        return error
    if request.method == "PUT":
        try:
            data = _json_body(request)
        except ValueError as body_error:
            return _error(str(body_error))
        name = str(data.get("restaurantName", "")).strip()
        owner_name = str(data.get("ownerName", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        phone = str(data.get("phone", "")).strip()
        address = str(data.get("address", "")).strip()
        nearby_landmark = str(data.get("nearbyLandmark", "")).strip()
        market = str(data.get("market", "")).strip()
        city = str(data.get("city", "")).strip()
        pincode = str(data.get("pincode", "")).strip()
        if not name or not owner_name or not phone or not address or not city or not pincode:
            return _error(
                "Restaurant name, owner, phone, address, city, and PIN code are required."
            )
        if len(name) > 160 or len(phone) > 30 or len(address) > 2000:
            return _error("Restaurant profile fields are too long.")
        if len(city) > 100 or len(nearby_landmark) > 160 or len(market) > 160:
            return _error("Restaurant location details are too long.")
        if len(pincode) != 6 or not pincode.isdigit():
            return _error("Enter a valid 6-digit restaurant PIN code.")
        try:
            validate_email(email)
        except ValidationError:
            return _error("Enter a valid account email address.")
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exclude(
            pk=request.user.pk
        ).exists():
            return _error("This email address is already in use.", 409)
        restaurant.name = name
        restaurant.owner_name = owner_name
        restaurant.email = email
        restaurant.phone = phone
        restaurant.address = address
        restaurant.nearby_landmark = nearby_landmark
        restaurant.market = market
        restaurant.city = city
        restaurant.pincode = pincode
        request.user.email = email
        request.user.username = email
        request.user.first_name = owner_name
        with transaction.atomic():
            request.user.save(update_fields=["email", "username", "first_name"])
            restaurant.save()
    return JsonResponse(
        {
            "id": restaurant.id,
            "name": restaurant.name,
            "restaurantName": restaurant.name,
            "ownerName": restaurant.owner_name,
            "email": restaurant.email,
            "phone": restaurant.phone,
            "address": restaurant.address,
            "nearbyLandmark": restaurant.nearby_landmark,
            "market": restaurant.market,
            "logo": _restaurant_logo_url(restaurant),
            "approved": restaurant.approved,
            "acceptOrders": restaurant.accepting_orders,
            "city": restaurant.city,
            "pincode": restaurant.pincode,
        }
    )


@csrf_protect
@require_http_methods(["PUT", "POST"])
def restaurant_profile_logo(request):
    restaurant, error = _restaurant_for_request(request)
    if error:
        return error
    uploaded = request.FILES.get("logo")
    if uploaded is None:
        return _error("Choose an image file.")
    if uploaded.size <= 0 or uploaded.size > 3 * 1024 * 1024:
        return _error("Logo image must be smaller than 3 MB.")
    extension = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
    signature = uploaded.read(12)
    uploaded.seek(0)
    signatures = {
        "png": signature.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": signature.startswith(b"\xff\xd8\xff"),
        "jpeg": signature.startswith(b"\xff\xd8\xff"),
        "gif": signature[:6] in {b"GIF87a", b"GIF89a"},
        "webp": signature.startswith(b"RIFF") and signature[8:12] == b"WEBP",
    }
    valid_signature = signatures.get(extension, False)
    if not valid_signature:
        return _error("Logo must be a valid PNG, JPEG, GIF, or WebP image.")
    restaurant.logo = uploaded
    restaurant.save(update_fields=["logo"])
    return JsonResponse({"logo": _restaurant_logo_url(restaurant)})


@csrf_protect
@require_http_methods(["GET", "PUT"])
def restaurant_settings(request):
    restaurant, error = _restaurant_for_request(request)
    if error:
        return error
    if request.method == "GET":
        return JsonResponse(
            {
                "acceptOrders": restaurant.accepting_orders,
                "orderNotifications": restaurant.order_notifications,
                "orderSound": restaurant.order_sound,
                "email": request.user.email,
            }
        )
    try:
        data = _json_body(request)
    except ValueError as body_error:
        return _error(str(body_error))
    email = str(data.get("email", request.user.email)).strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return _error("Enter a valid account email address.")
    if get_user_model().objects.filter(email__iexact=email).exclude(
        pk=request.user.pk
    ).exists():
        return _error("This email address is already in use.", 409)
    new_password = str(data.get("newPassword", ""))
    if new_password:
        current_password = str(data.get("currentPassword", ""))
        if not request.user.check_password(current_password):
            return _error("Current password is incorrect.", 403)
        try:
            validate_password(new_password, user=request.user)
        except ValidationError as validation_error:
            return _error(" ".join(validation_error.messages))
        request.user.set_password(new_password)
    request.user.email = email
    request.user.username = email
    restaurant.email = email
    for key in ("acceptOrders", "orderNotifications", "orderSound"):
        if key in data and not isinstance(data[key], bool):
            return _error(f"{key} must be true or false.")
    restaurant.accepting_orders = data.get("acceptOrders", True)
    restaurant.order_notifications = data.get("orderNotifications", True)
    restaurant.order_sound = data.get("orderSound", True)
    with transaction.atomic():
        request.user.save()
        restaurant.save(
            update_fields=[
                "email",
                "accepting_orders",
                "order_notifications",
                "order_sound",
            ]
        )
    if new_password:
        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, request.user)
    return JsonResponse({"message": "Restaurant settings updated."})
@require_GET
def restaurant_dashboard(request):
    restaurant, error = _restaurant_for_request(request)
    if error:
        return error
    orders = Order.objects.filter(restaurant=restaurant)
    today = timezone.localdate()
    return JsonResponse(
        {
            "totalProducts": restaurant.foods.count(),
            "totalOrders": orders.count(),
            "pendingOrders": orders.filter(status=Order.Status.PLACED).count(),
            "completedOrders": orders.filter(status=Order.Status.COMPLETED).count(),
            "todaysEarning": float(
                sum(
                    orders.filter(
                        status=Order.Status.COMPLETED,
                        created_at__date=today,
                    ).values_list("restaurant_payout", flat=True),
                    Decimal("0"),
                )
            ),
            "notificationCount": orders.filter(status=Order.Status.PLACED).count(),
        }
    )


def _product_payload(food):
    return {
        "id": food.id,
        "name": food.name,
        "category": food.category.name if food.category else "",
        "categoryId": food.category_id,
        "description": food.description,
        "image": food.image,
        "price": float(food.price),
        "available": food.available,
    }


@csrf_protect
@require_http_methods(["GET", "POST"])
def restaurant_products(request):
    restaurant, error = _restaurant_for_request(request)
    if error:
        return error
    if request.method == "GET":
        products = restaurant.foods.select_related("category").order_by("name")
        return JsonResponse([_product_payload(food) for food in products], safe=False)
    data = request.POST
    name = data.get("productName", "").strip()
    category_name = data.get("productCategory", "").strip()
    description = data.get("productDescription", "").strip()
    image = data.get("productImage", "").strip()
    try:
        price = Decimal(data.get("productPrice", ""))
    except (InvalidOperation, TypeError):
        return _error("Enter a valid product price.")
    if not name or len(name) > 160 or not category_name or len(description) > 2000:
        return _error("Enter a product name, category, and a description under 2000 characters.")
    if not price.is_finite() or price <= 0:
        return _error("Product price must be greater than zero.")
    if image:
        try:
            URLValidator(schemes=["http", "https"])(image)
        except ValidationError:
            return _error("Product image must be a valid HTTP or HTTPS URL.")
    with transaction.atomic():
        category = Category.objects.filter(name__iexact=category_name).first()
        if category is None:
            category = Category.objects.create(name=category_name)
        food = Food(
            restaurant=restaurant,
            category=category,
            name=name,
            description=description,
            image=image,
            price=price,
        )
        try:
            food.full_clean()
        except ValidationError as validation_error:
            return _error("; ".join(validation_error.messages))
        food.save()
    return JsonResponse(_product_payload(food), status=201)


def restaurant_orders(request):
    restaurant, error = _restaurant_for_request(request)
    if error:
        return error
    orders = (
        Order.objects.filter(restaurant=restaurant)
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return JsonResponse(
        {"orders": [_restaurant_order_data(order) for order in orders]}
    )


@csrf_protect
@require_http_methods(["PUT", "POST"])
def restaurant_update_order(request, order_id):
    restaurant, error = _restaurant_for_request(request)
    if error:
        return error
    order = get_object_or_404(Order, id=order_id, restaurant=restaurant)
    try:
        requested_status = str(_json_body(request).get("status", "")).lower()
    except ValueError as body_error:
        return _error(str(body_error))
    transitions = {
        "confirmed": (Order.Status.PLACED, Order.Status.ACCEPTED),
        "accepted": (Order.Status.PLACED, Order.Status.ACCEPTED),
        "preparing": (Order.Status.ACCEPTED, Order.Status.PREPARING),
        "ready": (Order.Status.PREPARING, Order.Status.READY_FOR_PICKUP),
        "cancelled": (Order.Status.PLACED, Order.Status.CANCELLED),
    }
    transition = transitions.get(requested_status)
    if transition is None:
        return _error("Unsupported restaurant order action.")
    allowed_current, new_status = transition
    if order.status != allowed_current:
        return _error("This order can no longer be changed to that status.", 409)
    order.status = new_status
    order.save(update_fields=["status"])
    return JsonResponse(
        {
            "message": f"Order status changed to {order.get_status_display()}.",
            "order": _restaurant_order_data(order),
        }
    )


@csrf_protect
@require_POST
def restaurant_confirm_pickup(request, order_id):
    restaurant, error = _restaurant_for_request(request)
    if error:
        return error
    order = get_object_or_404(Order, id=order_id, restaurant=restaurant)
    if order.order_type != Order.OrderType.PICKUP:
        return _error("Only pickup orders are confirmed by the restaurant.")
    if order.status != Order.Status.READY_FOR_PICKUP:
        return _error("Order must be ready before pickup can be confirmed.", 409)
    try:
        code = str(_json_body(request).get("confirmationCode", "")).strip()
    except ValueError as body_error:
        return _error(str(body_error))
    if len(code) != 4 or not code.isdigit():
        return _error("Enter the customer's 4-digit confirmation code.")
    return _confirm_order_with_code(
        order, code, "Pickup", {Order.Status.READY_FOR_PICKUP}
    )


def _delivery_partner_profile(request):
    role_error = _require_role(request, AccountProfile.Role.DELIVERY_PARTNER)
    if role_error:
        return None, role_error
    return _account_profile(request), None


@require_GET
def delivery_profile(request):
    profile, error = _delivery_partner_profile(request)
    if error:
        return error
    return JsonResponse(
        {
            "name": request.user.get_full_name() or request.user.email,
            "email": request.user.email,
            "phone": profile.phone,
            "approved": profile.approved,
        }
    )


@require_GET
def delivery_dashboard(request):
    profile, error = _delivery_partner_profile(request)
    if error:
        return error
    orders = Order.objects.filter(delivery_partner=profile)
    today = timezone.localdate()
    completed_today = orders.filter(
        status=Order.Status.COMPLETED, created_at__date=today
    ).count()
    recent_completed = (
        orders.filter(status=Order.Status.COMPLETED)
        .select_related("restaurant")
        .prefetch_related("items")
        .order_by("-created_at")[:20]
    )
    return JsonResponse(
        {
            "todayDeliveries": completed_today,
            "completedDeliveries": orders.filter(status=Order.Status.COMPLETED).count(),
            "earningsTracked": False,
            "recentCompleted": [
                _delivery_order_data(order) for order in recent_completed
            ],
        }
    )


def _delivery_order_data(order):
    return {
        "id": str(order.id),
        "orderNumber": str(order.id).split("-")[0].upper(),
        "date": timezone.localtime(order.created_at).strftime("%d %b %Y, %I:%M %p"),
        "statusCode": order.status,
        "status": order.get_status_display(),
        "orderType": order.order_type,
        "restaurantPayout": float(order.restaurant_payout),
        "restaurant": {
            "name": order.restaurant.name,
            "address": order.restaurant.address,
        },
        "customer": {
            "name": order.customer_name,
            "phone": order.customer_phone,
            "address": order.delivery_address,
        },
        "items": [
            {
                "name": item.food_name,
                "quantity": item.quantity,
                "total": float(item.line_total),
            }
            for item in order.items.all()
        ],
    }


@require_GET
def delivery_available_orders(request):
    _profile, error = _delivery_partner_profile(request)
    if error:
        return error
    orders = Order.objects.filter(
        order_type=Order.OrderType.DELIVERY,
        status=Order.Status.READY_FOR_PICKUP,
        delivery_partner__isnull=True,
    ).select_related("restaurant").prefetch_related("items")
    return JsonResponse(
        {"orders": [_delivery_order_data(order) for order in orders]}
    )


@require_GET
def delivery_current_order(request):
    profile, error = _delivery_partner_profile(request)
    if error:
        return error
    orders = list(
        Order.objects.filter(
            delivery_partner=profile,
            status__in=[
                Order.Status.ASSIGNED,
                Order.Status.PICKED_UP,
                Order.Status.OUT_FOR_DELIVERY,
            ],
        )
        .select_related("restaurant")
        .prefetch_related("items")
        .order_by("-created_at")
    )
    delivery_orders = [_delivery_order_data(order) for order in orders]
    return JsonResponse(
        {
            "orders": delivery_orders,
            "order": delivery_orders[0] if delivery_orders else None,
        }
    )


@csrf_protect
@require_http_methods(["PUT", "POST"])
def delivery_accept_order(request, order_id):
    profile, error = _delivery_partner_profile(request)
    if error:
        return error
    with transaction.atomic():
        AccountProfile.objects.select_for_update().get(pk=profile.pk)
        order = get_object_or_404(Order.objects.select_for_update(), id=order_id)
        if order.order_type != Order.OrderType.DELIVERY:
            return _error("Pickup orders do not need a delivery partner.", 400)
        if (
            order.status != Order.Status.READY_FOR_PICKUP
            or order.delivery_partner_id is not None
        ):
            return _error("This delivery is no longer available.", 409)
        order.delivery_partner = profile
        order.status = Order.Status.ASSIGNED
        order.save(update_fields=["delivery_partner", "status"])
    return JsonResponse(
        {"message": "Delivery assigned to you.", "order": _delivery_order_data(order)}
    )


@csrf_protect
@require_http_methods(["PUT", "POST"])
def delivery_update_status(request, order_id):
    profile, error = _delivery_partner_profile(request)
    if error:
        return error
    order = get_object_or_404(Order, id=order_id, delivery_partner=profile)
    try:
        requested_status = str(_json_body(request).get("status", "")).upper()
    except ValueError as body_error:
        return _error(str(body_error))
    if requested_status == "PICKED_UP" and order.status == Order.Status.ASSIGNED:
        order.status = Order.Status.PICKED_UP
    elif requested_status == "ON_THE_WAY" and order.status == Order.Status.PICKED_UP:
        order.status = Order.Status.OUT_FOR_DELIVERY
    else:
        return _error("Invalid delivery status transition.", 409)
    order.save(update_fields=["status"])
    return JsonResponse({"message": "Delivery status updated.", "status": order.status})


@csrf_protect
@require_http_methods(["PUT", "POST"])
def delivery_complete_order(request, order_id):
    profile, error = _delivery_partner_profile(request)
    if error:
        return error
    order = get_object_or_404(Order, id=order_id, delivery_partner=profile)
    if order.status not in {Order.Status.PICKED_UP, Order.Status.OUT_FOR_DELIVERY}:
        return _error("Pick up the order before confirming delivery.", 409)
    try:
        code = str(_json_body(request).get("confirmationCode", "")).strip()
    except ValueError as body_error:
        return _error(str(body_error))
    if len(code) != 4 or not code.isdigit():
        return _error("Enter the customer's 4-digit confirmation code.")
    return _confirm_order_with_code(
        order,
        code,
        "Delivery",
        {Order.Status.PICKED_UP, Order.Status.OUT_FOR_DELIVERY},
    )


def _confirm_order_with_code(order, code, completion_label, allowed_statuses):
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(id=order.id)
        if locked_order.status not in allowed_statuses:
            return _error("Order is not ready for confirmation.", 409)
        if locked_order.confirmation_attempts >= 5:
            return _error("Too many incorrect codes. Ask the customer to contact support.", 429)
        if not locked_order.confirmation_code or not secrets.compare_digest(
            code, locked_order.confirmation_code
        ):
            Order.objects.filter(id=locked_order.id).update(
                confirmation_attempts=F("confirmation_attempts") + 1
            )
            return _error("Confirmation code is incorrect.", 400)
        locked_order.status = Order.Status.COMPLETED
        locked_order.save(update_fields=["status"])
    return JsonResponse(
        {
            "message": f"{completion_label} confirmed.",
            "status": Order.Status.COMPLETED,
        }
    )


def _order_timeline(status):
    cancelled = status == Order.Status.CANCELLED
    placed = status in {
        Order.Status.PAID,
        Order.Status.PLACED,
        Order.Status.ACCEPTED,
        Order.Status.PREPARING,
        Order.Status.READY_FOR_PICKUP,
        Order.Status.ASSIGNED,
        Order.Status.PICKED_UP,
        Order.Status.OUT_FOR_DELIVERY,
        Order.Status.COMPLETED,
    }
    preparing_done = status in {
        Order.Status.READY_FOR_PICKUP,
        Order.Status.ASSIGNED,
        Order.Status.PICKED_UP,
        Order.Status.OUT_FOR_DELIVERY,
        Order.Status.COMPLETED,
    }
    out_for_delivery = status in {
        Order.Status.ASSIGNED,
        Order.Status.PICKED_UP,
        Order.Status.OUT_FOR_DELIVERY,
    }
    delivered = status == Order.Status.COMPLETED
    return [
        {
            "status": (
                "Order cancelled"
                if cancelled
                else ("Order placed" if placed else "Payment pending")
            ),
            "completed": placed or cancelled,
            "active": status in {Order.Status.PAYMENT_PENDING, Order.Status.PLACED},
        },
        {
            "status": "Preparing",
            "completed": preparing_done,
            "active": status in {Order.Status.ACCEPTED, Order.Status.PREPARING},
        },
        {
            "status": "On the way",
            "completed": delivered,
            "active": out_for_delivery,
        },
        {
            "status": "Delivered",
            "completed": delivered,
            "active": False,
        },
    ]


@require_GET
def current_order(request):
    role_error = _require_role(request, AccountProfile.Role.CUSTOMER)
    if role_error:
        return role_error
    order = Order.objects.filter(customer=request.user).first()
    if order is None:
        return _error("No current order.", 404)
    return order_detail(request, order.id)


@require_GET
def customer_order_history(request):
    role_error = _require_role(request, AccountProfile.Role.CUSTOMER)
    if role_error:
        return role_error
    orders = (
        Order.objects.filter(customer=request.user)
        .select_related("restaurant")
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return JsonResponse(
        {
            "orders": [
                {
                    "id": str(order.id),
                    "orderNumber": str(order.id).split("-")[0].upper(),
                    "createdAt": timezone.localtime(order.created_at).strftime(
                        "%d %b %Y, %I:%M %p"
                    ),
                    "status": order.get_status_display(),
                    "restaurantName": order.restaurant.name,
                    "orderType": order.get_order_type_display(),
                    "total": float(order.customer_total),
                    "items": [
                        {"name": item.food_name, "quantity": item.quantity}
                        for item in order.items.all()
                    ],
                }
                for order in orders
            ]
        }
    )


@csrf_protect
@require_http_methods(["POST", "PUT"])
def cancel_order(request, order_id):
    role_error = _require_role(request, AccountProfile.Role.CUSTOMER)
    if role_error:
        return role_error
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    if order.status != Order.Status.PLACED:
        return _error("Only new orders can be cancelled here.", 409)
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status"])
    return JsonResponse({"message": "Order cancelled.", "status": order.status})
