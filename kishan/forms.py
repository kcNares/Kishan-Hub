from django import forms
from kishan.models import ToolReview
from django.forms import DateTimeInput
from kishan.utils import is_tool_available
from .models import Booking


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

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        tool = cleaned_data.get("tool")

        if start_date and end_date and tool:
            if end_date <= start_date:
                raise forms.ValidationError("End date must be after start date.")

            if not is_tool_available(tool, start_date, end_date):
                raise forms.ValidationError(
                    "Tool is not available for the selected dates."
                )

        return cleaned_data
