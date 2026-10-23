import uuid
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def generate_registration_number():
    return f"HC-{timezone.localdate():%Y}-{secrets.token_hex(8).upper()}"


class AccountProfile(models.Model):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        RESTAURANT = "restaurant", "Restaurant"
        DELIVERY_PARTNER = "delivery_partner", "Delivery partner"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_profile"
    )
    firebase_uid = models.CharField(
        max_length=128, unique=True, null=True, blank=True, editable=False
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=30, blank=True)
    # Latest GPS fix from the delivery partner's device; never set by a customer.
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.role == self.Role.RESTAURANT and self.approved:
            restaurant = Restaurant.objects.filter(
                owner_id=self.user_id,
                approved=True,
                certificate_issued_at__isnull=True,
            ).first()
            if restaurant:
                restaurant.certificate_issued_at = timezone.now()
                restaurant.save(update_fields=["certificate_issued_at"])

    def __str__(self):
        return f"{self.user.email} ({self.get_role_display()})"


class Restaurant(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restaurant",
    )
    name = models.CharField(max_length=160)
    owner_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField(unique=True)
    registration_number = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        editable=False,
        default=generate_registration_number,
    )
    certificate_issued_at = models.DateTimeField(
        null=True, blank=True, editable=False
    )
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    logo = models.FileField(upload_to="restaurant-logos/", blank=True)
    nearby_landmark = models.CharField(max_length=160, blank=True)
    market = models.CharField(max_length=160, blank=True)
    city = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=12, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-90")),
            MaxValueValidator(Decimal("90")),
        ],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-180")),
            MaxValueValidator(Decimal("180")),
        ],
    )
    approved = models.BooleanField(default=False)
    accepting_orders = models.BooleanField(default=True)
    order_notifications = models.BooleanField(default=True)
    order_sound = models.BooleanField(default=True)
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Commission percentage currently charged to this restaurant.",
    )
    max_commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Admin-approved maximum percentage for this restaurant.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.approved and self.certificate_issued_at is None and self.owner_id:
            profile_approved = AccountProfile.objects.filter(
                user_id=self.owner_id,
                role=AccountProfile.Role.RESTAURANT,
                approved=True,
            ).exists()
            if profile_approved:
                self.certificate_issued_at = timezone.now()
                update_fields = kwargs.get("update_fields")
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {
                        "certificate_issued_at"
                    }
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.commission_percentage > self.max_commission_percentage:
            errors["commission_percentage"] = (
                "Commission cannot exceed the approved maximum."
            )
        if (self.latitude is None) != (self.longitude is None):
            errors["longitude"] = "Latitude and longitude must both be provided."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Food(models.Model):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="foods"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="foods"
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    image = models.URLField(blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.restaurant.name})"


class PricingSettings(models.Model):
    delivery_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Customer delivery charge. Update this value whenever your delivery rate changes.",
    )
    delivery_platform_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Customer platform fee charged on delivery orders.",
    )
    pickup_platform_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Customer platform fee charged on pickup orders.",
    )
    minimum_commission = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("1.00"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    def __str__(self):
        return "Marketplace pricing"

    @classmethod
    def current(cls):
        settings_row, _ = cls.objects.get_or_create(pk=1)
        return settings_row


class Order(models.Model):
    class OrderType(models.TextChoices):
        PICKUP = "pickup", "Pickup"
        DELIVERY = "delivery", "Delivery"

    class Status(models.TextChoices):
        PLACED = "placed", "New order"
        PAYMENT_PENDING = "payment_pending", "Payment pending"
        PAID = "paid", "Paid"
        ACCEPTED = "accepted", "Accepted"
        PREPARING = "preparing", "Preparing"
        READY_FOR_PICKUP = "ready_for_pickup", "Ready for pickup"
        ASSIGNED = "assigned", "Delivery partner assigned"
        PICKED_UP = "picked_up", "Picked up"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        PAYMENT_FAILED = "payment_failed", "Payment failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="food_orders",
    )
    customer_name = models.CharField(max_length=160)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=30)
    delivery_address = models.TextField(blank=True)
    delivery_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-90")),
            MaxValueValidator(Decimal("90")),
        ],
    )
    delivery_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-180")),
            MaxValueValidator(Decimal("180")),
        ],
    )
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.PROTECT, related_name="orders"
    )
    delivery_partner = models.ForeignKey(
        AccountProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
        limit_choices_to={"role": AccountProfile.Role.DELIVERY_PARTNER},
    )
    order_type = models.CharField(max_length=10, choices=OrderType.choices)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PLACED
    )
    item_total = models.DecimalField(max_digits=10, decimal_places=2)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    platform_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    customer_total = models.DecimalField(max_digits=10, decimal_places=2)
    restaurant_payout = models.DecimalField(max_digits=10, decimal_places=2)
    gateway_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    gateway_payment_status = models.CharField(max_length=24, default="not_required")
    cashfree_order_id = models.CharField(max_length=45, blank=True, null=True, unique=True)
    cashfree_payment_session_id = models.TextField(blank=True)
    cashfree_payment_id = models.CharField(max_length=80, blank=True)
    confirmation_code = models.CharField(max_length=4, null=True, blank=True)
    confirmation_attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if (self.delivery_latitude is None) != (
            self.delivery_longitude is None
        ):
            raise ValidationError(
                {
                    "delivery_longitude": (
                        "Delivery latitude and longitude must both be provided."
                    )
                }
            )

    def __str__(self):
        return f"{self.id} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.PROTECT)
    food_name = models.CharField(max_length=160)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.food_name}"
