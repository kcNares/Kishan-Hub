from django.contrib import admin
from .models import (
    Category,
    Tag,
    Tool,
    SearchQuery,
    Rental,
    ToolReview,
)


# Inline for ToolReview inside Tool admin (optional but useful)
class ToolReviewInline(admin.TabularInline):
    model = ToolReview
    extra = 0
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "farmer",
        "rating",
        "comment",
        "is_flagged",
        "is_sentiment_mismatch",
        "created_at",
    )
    can_delete = True
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "owner",
        "daily_rent_price",
        "status",
        "rating",
        "reviews_count",
    )
    list_filter = ("status", "category", "tags")
    search_fields = ("name", "description", "owner__shop_name")
    autocomplete_fields = ("category", "tags", "owner")
    inlines = [ToolReviewInline]


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ("query", "timestamp")
    search_fields = ("query",)
    ordering = ("-timestamp",)


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = (
        "tool",
        "farmer",
        "start_date",
        "end_date",
        "total_price",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active", "start_date", "end_date")
    search_fields = ("tool__name", "farmer__user__username")
    autocomplete_fields = ("tool", "farmer")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ToolReview)
class ToolReviewAdmin(admin.ModelAdmin):
    list_display = (
        "tool",
        "farmer",
        "rating",
        "is_flagged",
        "is_sentiment_mismatch",
        "created_at",
    )
    list_filter = ("rating", "is_flagged", "is_sentiment_mismatch", "created_at")
    search_fields = ("tool__name", "farmer__user__username", "comment")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("tool", "farmer")

    # Prevent adding duplicate reviews manually (enforced by unique_together in model)
    def save_model(self, request, obj, form, change):
        if not change:
            exists = ToolReview.objects.filter(
                tool=obj.tool, farmer=obj.farmer
            ).exists()
            if exists:
                from django.core.exceptions import ValidationError

                raise ValidationError("This farmer has already reviewed this tool.")
        super().save_model(request, obj, form, change)
