from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from accounts.models import Profile
import re

class AdminLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "placeholder": "Username",
                "class": "form-input",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "class": "form-input",
            }
        )
    )


class SellerRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    confirm_password = forms.CharField(
        widget=forms.PasswordInput, label="Confirm Password"
    )
    phone = forms.CharField(max_length=15, label="Phone Number")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email"]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        phone = cleaned_data.get("phone")

        if password != confirm_password:
            raise ValidationError("Passwords do not match.")

        phone_digits = re.sub(r"\D", "", phone or "")
        if len(phone_digits) != 10:
            self.add_error("phone", "Phone number must be exactly 10 digits.")
        elif not phone_digits.isdigit():
            self.add_error("phone", "Phone number must contain digits only.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            profile = user.profile
            profile.phone = self.cleaned_data["phone"]
            profile.is_seller = True
            profile.is_farmer = False
            profile.save()
        return user


class FarmerRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    confirm_password = forms.CharField(
        widget=forms.PasswordInput, label="Confirm Password"
    )
    phone = forms.CharField(max_length=15, label="Phone Number")

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "username",
            "email",
        ]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        phone = cleaned_data.get("phone")

        if password != confirm_password:
            raise ValidationError("Passwords do not match.")

        phone_digits = re.sub(r"\D", "", phone or "")
        if len(phone_digits) != 10:
            self.add_error("phone", "Phone number must be exactly 10 digits.")
        elif not phone_digits.isdigit():
            self.add_error("phone", "Phone number must contain digits only.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            profile = user.profile
            profile.phone = self.cleaned_data["phone"]
            profile.is_farmer = True
            profile.is_seller = False
            profile.save()
        return user


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "placeholder": "Username",
                "class": "form-input",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "class": "form-input",
            }
        )
    )
