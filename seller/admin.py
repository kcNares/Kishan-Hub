from django.contrib import admin
from .models import Seller


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "shop_name",
        "full_name",
        "email",
        "phone",
        "business_type",
        "location_name",
        "latitude",
        "longitude",
        "is_approved",
        "user_display",
    )
    list_filter = (
        "business_type",
        "is_approved",
    )
    search_fields = (
        "shop_name",
        "full_name",
        "email",
        "phone",
        "location_name",
    )
    readonly_fields = ("latitude", "longitude")

    def user_display(self, obj):
        return str(obj.user) if obj.user else "-"

    user_display.short_description = "User"
