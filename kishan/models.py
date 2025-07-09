from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from seller.models import Seller
from django.utils import timezone


class TimeStampModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampModel):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Tag(TimeStampModel):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Tool(TimeStampModel):
    STATUS_CHOICES = [
        ("available", "Available"),
        ("unavailable", "Unavailable"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to="tool_images/%Y/%m/%d", blank=False)
    daily_rent_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="available"
    )
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    reviews_count = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="tools"
    )
    tags = models.ManyToManyField(Tag, blank=True)
    owner = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name="tools")

    def __str__(self):
        return self.name


class SearchQuery(models.Model):
    query = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.query


class Rental(TimeStampModel):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="rentals")
    farmer = models.ForeignKey(
        "accounts.Profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_farmer": True},
        related_name="rentals",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tool.name} rented by {self.farmer.user.username}"


class ToolReview(models.Model):
    tool = models.ForeignKey("Tool", on_delete=models.CASCADE, related_name="reviews")
    farmer = models.ForeignKey(
        "accounts.Profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_farmer": True},
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, null=True)

    # Fields used by your algorithms:
    is_flagged = models.BooleanField(default=False)  # ← for fake review detection
    is_sentiment_mismatch = models.BooleanField(
        default=False
    )  # ← for sentiment mismatch

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("tool", "farmer")  # Only one review per farmer per tool
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review for {self.tool.name} by {self.farmer.user.username}"
