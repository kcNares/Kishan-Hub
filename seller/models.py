from django.db import models
from django.contrib.auth.models import User
from .utils import get_random_point_in_location


class Seller(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    shop_name = models.CharField(max_length=100)

    BUSINESS_TYPE_CHOICES = [
        ("individual", "Individual"),
        ("partnership", "Partnership"),
        ("company", "Company"),
    ]
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE_CHOICES)

    location_name = models.CharField(max_length=255)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    is_approved = models.BooleanField(default=False)

    # Notification fields
    approval_notification_seen_by_seller = models.BooleanField(default=False)
    approval_notification_viewed_at_by_seller = models.DateTimeField(
        null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if self.location_name and (self.latitude is None or self.longitude is None):
            lat, lon = get_random_point_in_location(self.location_name)
            if lat and lon:
                self.latitude = lat
                self.longitude = lon
            else:
                # Fallback to default coordinate (Kathmandu center)
                self.latitude = 27.7
                self.longitude = 85.3
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shop_name} ({self.location_name})"
