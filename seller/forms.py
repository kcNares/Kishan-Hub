from django import forms
from .models import Seller
from kishan.models import Tool, Category, Tag


class SellerForm(forms.ModelForm):
    latitude = forms.FloatField(widget=forms.HiddenInput(), required=False)
    longitude = forms.FloatField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Seller
        fields = [
            "full_name",
            "email",
            "phone",
            "shop_name",
            "business_type",
            "location_name",
            "latitude",
            "longitude",
            "shopLogo",
            "description",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. John Doe"}
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. johndoe@example.com",
                }
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. +977-9801234567"}
            ),
            "shop_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. ABC Electronics"}
            ),
            "business_type": forms.Select(attrs={"class": "form-select"}),
            "location_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Select location from map",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Write a short description...",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get("latitude")
        longitude = cleaned_data.get("longitude")
        location_name = cleaned_data.get("location_name")

        if location_name and (latitude is None or longitude is None):
            raise forms.ValidationError("Please select a valid location on the map.")

        return cleaned_data

    def save(self, user=None, commit=True):
        seller = super().save(commit=False)
        if user:
            seller.user = user
            seller.full_name = user.get_full_name() or seller.full_name
            seller.email = user.email
            if hasattr(user, "profile") and user.profile.phone:
                seller.phone = user.profile.phone
        if commit:
            seller.save()
        return seller


class ToolForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Category",
    )

    class Meta:
        model = Tool
        exclude = ["owner"]
        fields = [
            "name",
            "description",
            "image",
            "daily_rent_price",
            "delivery_charge",
            "status",
            "category",
            "tags",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "daily_rent_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "delivery_charge": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "tags": forms.SelectMultiple(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].label_from_instance = lambda obj: (
            f"{obj.parent.name + ' > ' if obj.parent else ''}{obj.name}"
        )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "parent"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "parent": forms.Select(attrs={"class": "form-control"}),
        }


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["name"]
