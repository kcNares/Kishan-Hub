from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "is_seller", "is_farmer", "role_display")
    list_filter = ("is_seller", "is_farmer")
    search_fields = ("user__username", "user__email", "phone")

    def role_display(self, obj):
        return obj.role()

    role_display.short_description = "Role"
