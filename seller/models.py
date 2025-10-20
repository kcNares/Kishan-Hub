from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


def shop_document_upload_path(instance, filename):
    return f"seller_documents/{instance.seller.user.id}/{filename}"


def shop_logo_upload_path(instance, filename):
    return f"seller_logos/{instance.user.id}/{filename}"


class Seller(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("cancelled", "Cancelled"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)

    shop_name = models.CharField(max_length=100)
    business_type = models.CharField(
        max_length=20,
        choices=[
            ("individual", "Individual"),
            ("partnership", "Partnership"),
            ("company", "Company"),
        ],
    )

    location_name = models.CharField(max_length=255)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    shopLogo = models.ImageField(
        upload_to=shop_logo_upload_path,
        blank=True,
        null=True,
    )

    description = models.TextField(blank=True, null=True)

    is_approved = models.BooleanField(default=False)
    approval_notification_seen_by_seller = models.BooleanField(default=False)
    approval_notification_viewed_at_by_seller = models.DateTimeField(
        null=True, blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    cancel_reason = models.TextField(blank=True, null=True)

    notified = models.BooleanField(default=False)
    notified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.shop_name} ({self.location_name})"


class SellerDocument(models.Model):
    seller = models.ForeignKey(
        Seller, on_delete=models.CASCADE, related_name="documents"
    )
    document = models.FileField(upload_to=shop_document_upload_path)

    def __str__(self):
        return f"Document for {self.seller.shop_name}"
