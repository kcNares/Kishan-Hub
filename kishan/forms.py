from django import forms
from kishan.models import ToolReview, ContactMessage
from django.forms import DateTimeInput, HiddenInput
from kishan.utils import is_tool_available
from .models import Booking, Rental
from django.utils import timezone
from django.core.exceptions import ValidationError


class ToolReviewForm(forms.ModelForm):
    class Meta:
        model = ToolReview
        fields = ["rating", "comment"]

    def clean_comment(self):
        comment = self.cleaned_data.get("comment", "")
        if len(comment.strip()) < 10:
            raise forms.ValidationError(
                "Your review is too short. Please provide more details."
            )
        return comment


class BookingForm(forms.ModelForm):
    DELIVERY_CHOICES = [
        ("no", "No"),
        ("yes", "Yes"),
    ]

    delivery_needed = forms.ChoiceField(
        choices=DELIVERY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_delivery_needed"}),
        label="Delivery Option",
    )

    delivery_address = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Enter delivery address...",
                "id": "id_delivery_address",
            }
        ),
        label="Delivery Address",
    )

    delivery_charge = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        initial=0.00,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "readonly": "readonly",
                "id": "id_delivery_charge",
            }
        ),
    )

    class Meta:
        model = Booking
        fields = [
            "start_date",
            "end_date",
            "tool",
            "total_price",
            "delivery_needed",
            "delivery_address",
            "delivery_charge",
        ]
        widgets = {
            "start_date": DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                    "id": "id_start_date",
                }
            ),
            "end_date": DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                    "id": "id_end_date",
                }
            ),
            "tool": forms.HiddenInput(),
            "total_price": forms.HiddenInput(attrs={"id": "id_total_price"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # If farmer is logged in, fill initial address
        if self.user and hasattr(self.user, "profile"):
            farmer_address = self.user.profile.location
            if farmer_address:
                self.fields["delivery_address"].initial = farmer_address

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        tool = cleaned_data.get("tool")

        if start_date and end_date and tool:
            now = timezone.now()
            if start_date < now:
                raise ValidationError("Start date must be in the future.")

            if end_date <= start_date:
                raise ValidationError("End date must be after start date.")

            if not is_tool_available(tool, start_date, end_date):
                raise ValidationError("Tool is not available for the selected dates.")

        return cleaned_data


class RentalForm(forms.ModelForm):
    # Optional extend date for existing rentals
    extend_date = forms.DateTimeField(
        required=False,
        widget=DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Optional: Extend rental beyond current end date",
    )

    class Meta:
        model = Rental
        fields = [
            "tool",
            "start_date",
            "end_date",
            "extend_date",
            "delivery_needed",
            "delivery_address",
            "total_price",
            "delivery_charge",
            "payment_method",
        ]
        widgets = {
            "start_date": DateTimeInput(attrs={"type": "datetime-local"}),
            "end_date": DateTimeInput(attrs={"type": "datetime-local"}),
            "delivery_address": forms.Textarea(attrs={"rows": 2}),
            "total_price": HiddenInput(),
            "delivery_charge": HiddenInput(),
            "payment_method": HiddenInput(),
            "tool": HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        extend_date = cleaned_data.get("extend_date")

        # Validate normal rental
        if start_date and end_date and end_date <= start_date:
            self.add_error("end_date", "End date must be after start date.")

        # Validate extension
        if extend_date:
            if not end_date:
                self.add_error("extend_date", "Cannot set extension without end date.")
            elif extend_date <= end_date:
                self.add_error(
                    "extend_date",
                    "Extension date must be after current end date and time.",
                )

        return cleaned_data


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["full_name", "email", "phone", "subject", "message"]

        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "subject": forms.Select(
                choices=[
                    ("General Inquiry", "General Inquiry"),
                    ("Tool Rental", "Tool Rental"),
                    ("Technical Support", "Technical Support"),
                    ("Partnership", "Partnership"),
                    ("Other", "Other"),
                ],
                attrs={"class": "form-select"},
            ),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }
