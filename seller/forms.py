from django import forms
from .models import Seller
from kishan.models import Tool, Category, Tag


class SellerForm(forms.ModelForm):
    class Meta:
        model = Seller
        fields = [
            "full_name",
            "email",
            "phone",
            "shop_name",
            "business_type",
            "location_name",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "shop_name": forms.TextInput(attrs={"class": "form-control"}),
            "business_type": forms.Select(attrs={"class": "form-select"}),
            "location_name": forms.TextInput(attrs={"class": "form-control"}),
        }


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
