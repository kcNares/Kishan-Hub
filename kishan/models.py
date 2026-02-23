from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from seller.models import Seller
from django.contrib.auth.models import User
from django.db.models import Avg


class TimeStampModel(models.Model):
    created_at = models.DateTimeField(
        default=timezone.now
    )  # default only for existing rows
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampModel):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    def __str__(self):
        return f"{self.parent.name + ' > ' if self.parent else ''}{self.name}"

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
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
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

    @property
    def is_rented_now(self):
        """
        Returns True if the tool is currently blocked by an active rental window.
        We consider rentals with status 'rented' (COD) or 'paid' (eSewa success).
        """
        now = timezone.now()
        return self.rentals.filter(
            is_active=True,
            status__in=["rented", "paid"],
            start_date__lte=now,
            end_date__gte=now,
        ).exists()


class SearchQuery(models.Model):
    query = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.query


class ToolReview(TimeStampModel):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="reviews")
    farmer = models.ForeignKey(
        "accounts.Profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_farmer": True},
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, null=True)
    reply = models.TextField(blank=True, null=True)
    is_flagged = models.BooleanField(default=False)
    is_sentiment_mismatch = models.BooleanField(default=False)

    class Meta:
        unique_together = ("tool", "farmer")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review for {self.tool.name} by {self.farmer.user.username}"


class Booking(TimeStampModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
    ]

    tool = models.ForeignKey(
        "kishan.Tool", on_delete=models.CASCADE, related_name="bookings"
    )
    farmer = models.ForeignKey(
        "accounts.Profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_farmer": True},
        related_name="bookings",
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    delivery_address = models.TextField(blank=True, null=True)
    reminder_sent = models.BooleanField(default=False)
    delivery_needed = models.CharField(
        max_length=3,
        choices=[("no", "No"), ("yes", "Yes")],
        default="no",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("End date must be after start date.")

        from kishan.utils import is_tool_available

        if not is_tool_available(self.tool, self.start_date, self.end_date):
            raise ValidationError("This tool is not available for the selected dates.")

    def __str__(self):
        return f"Booking for {self.tool.name} by {self.farmer.user.username} ({self.status})"


# class Rental(TimeStampModel):
#     PAYMENT_METHOD_CHOICES = [
#         ("esewa", "eSewa"),
#         ("cash", "Cash on Delivery"),
#     ]

#     STATUS_CHOICES = [
#         ("pending", "Pending"),
#         ("paid", "Paid"),
#         ("rented", "Rented"),  # for COD confirmation
#     ]

#     tool = models.ForeignKey(
#         "kishan.Tool", on_delete=models.CASCADE, related_name="rentals"
#     )
#     farmer = models.ForeignKey(
#         "accounts.Profile",
#         on_delete=models.CASCADE,
#         limit_choices_to={"is_farmer": True},
#         related_name="rentals",
#     )

#     # Normal rental
#     start_date = models.DateTimeField()
#     end_date = models.DateTimeField()

#     # Extension (new end date proposal)
#     extend_date = models.DateTimeField(blank=True, null=True)

#     # Pricing & delivery
#     total_price = models.DecimalField(max_digits=12, decimal_places=2)
#     delivery_needed = models.CharField(
#         max_length=3, choices=[("no", "No"), ("yes", "Yes")], default="no"
#     )
#     delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
#     delivery_address = models.TextField(blank=True, null=True)

#     # Payment
#     payment_method = models.CharField(
#         max_length=10, choices=PAYMENT_METHOD_CHOICES, default="esewa"
#     )
#     paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
#     status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
#     is_active = models.BooleanField(default=True)

#     def clean(self):
#         # Ensure valid dates
#         if self.end_date <= self.start_date:
#             raise ValidationError("End date must be after start date.")

#         # If extend_date is provided, validate it
#         if self.extend_date and self.extend_date <= self.end_date:
#             raise ValidationError("Extend date must be after the current End Date.")

#         from kishan.utils import is_tool_available

#         # Validate tool availability for the final rental period
#         final_end = self.extend_date if self.extend_date else self.end_date
#         if not is_tool_available(
#             self.tool, self.start_date, final_end, exclude_rental_id=self.pk
#         ):
#             raise ValidationError("Tool is not available for the selected period.")

#     def apply_extension(self):
#         """
#         Apply the extend_date to end_date when extension is confirmed.
#         """
#         if self.extend_date and self.extend_date > self.end_date:
#             self.end_date = self.extend_date
#             self.extend_date = None  # clear after applying
#             self.save()
#             return True
#         return False

#     def __str__(self):
#         return f"{self.tool.name} rented by {self.farmer.user.username} ({self.status})"


class Rental(TimeStampModel):
    PAYMENT_METHOD_CHOICES = [
        ("esewa", "eSewa"),
        ("cash", "Cash on Delivery"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("rented", "Rented"),
        ("cancelled", "Cancelled"),
    ]

    tool = models.ForeignKey(
        "kishan.Tool", on_delete=models.CASCADE, related_name="rentals"
    )
    farmer = models.ForeignKey(
        "accounts.Profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_farmer": True},
        related_name="rentals",
    )

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    extend_date = models.DateTimeField(blank=True, null=True)

    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_needed = models.CharField(
        max_length=3, choices=[("no", "No"), ("yes", "Yes")], default="no"
    )
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    delivery_address = models.TextField(blank=True, null=True)

    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_METHOD_CHOICES, default="esewa"
    )
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    is_active = models.BooleanField(default=True)

    esewa_transaction_uuid = models.CharField(
        max_length=100, blank=True, null=True, unique=True
    )
    esewa_ref_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    esewa_status = models.CharField(
        max_length=20,
        choices=[
            ("initiated", "Initiated"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        default="initiated",
    )
    esewa_response_message = models.TextField(blank=True, null=True)

    def clean(self):
        # ---- Guard against None values ----
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError("End date must be after start date.")

        if self.extend_date:
            # If end_date exists, compare normally
            if self.end_date and self.extend_date <= self.end_date:
                raise ValidationError("Extend date must be after the current End Date.")

        # Check availability only if dates exist
        if self.start_date and (self.end_date or self.extend_date):
            from kishan.utils import is_tool_available

            final_end = self.extend_date if self.extend_date else self.end_date

            if not is_tool_available(
                self.tool, self.start_date, final_end, exclude_rental_id=self.pk
            ):
                raise ValidationError("Tool is not available for the selected period.")

    def apply_extension(self):
        if self.extend_date and self.end_date and self.extend_date > self.end_date:
            self.end_date = self.extend_date
            self.extend_date = None
            self.save()
            return True
        return False

    def save(self, *args, **kwargs):
        """
        Optional: skip validation when creating programmatically
        by passing skip_validation=True in kwargs.
        """
        skip = kwargs.pop("skip_validation", False)
        if not skip:
            self.clean()
        super(Rental, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.tool.name} rented by {self.farmer.user.username} ({self.status})"


class Notification(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True, null=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    booking = models.ForeignKey(
        "kishan.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"


class ContactMessage(models.Model):
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    subject = models.CharField(max_length=120)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.subject}"
