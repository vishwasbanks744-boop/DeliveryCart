from django.contrib import admin

from .models import (
    AccountProfile,
    Category,
    Food,
    Order,
    OrderItem,
    PricingSettings,
    Restaurant,
)


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "approved", "created_at")
    list_filter = ("role", "approved")
    search_fields = ("user__email", "user__first_name", "phone")
    readonly_fields = ("user", "role", "phone", "created_at")


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "registration_number",
        "approved",
        "certificate_issued_at",
        "accepting_orders",
        "commission_percentage",
        "max_commission_percentage",
    )
    list_filter = ("approved", "accepting_orders")
    search_fields = (
        "name",
        "email",
        "phone",
        "nearby_landmark",
        "market",
        "city",
        "pincode",
    )
    fieldsets = (
        (
            "Restaurant",
            {
                "fields": (
                    "owner",
                    "name",
                    "owner_name",
                    "email",
                    "registration_number",
                    "certificate_issued_at",
                    "phone",
                    "address",
                    "nearby_landmark",
                    "market",
                    "city",
                    "pincode",
                    "logo",
                )
            },
        ),
        (
            "Approval and commission",
            {
                "fields": (
                    "approved",
                    "accepting_orders",
                    "commission_percentage",
                    "max_commission_percentage",
                )
            },
        ),
    )
    readonly_fields = ("registration_number", "certificate_issued_at")


@admin.register(PricingSettings)
class PricingSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "delivery_fee",
        "pickup_platform_fee",
        "delivery_platform_fee",
        "minimum_commission",
        "updated_at",
    )
    fields = ("delivery_fee", "pickup_platform_fee", "delivery_platform_fee")

    def has_add_permission(self, request):
        return not PricingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "category", "price", "available")
    list_filter = ("available", "restaurant", "category")
    search_fields = ("name", "restaurant__name")


admin.site.register(Category)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("food", "food_name", "unit_price", "quantity", "line_total")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurant",
        "order_type",
        "status",
        "customer_total",
        "restaurant_payout",
        "created_at",
    )
    list_filter = ("status", "order_type", "restaurant")
    search_fields = ("id", "customer_name", "customer_phone")
    readonly_fields = (
        "customer",
        "customer_name",
        "customer_email",
        "customer_phone",
        "delivery_address",
        "restaurant",
        "order_type",
        "status",
        "item_total",
        "commission_percentage",
        "commission_amount",
        "delivery_fee",
        "platform_fee",
        "customer_total",
        "restaurant_payout",
        "created_at",
        "paid_at",
    )
    inlines = (OrderItemInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
