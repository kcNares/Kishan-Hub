import datetime
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .forms import (
    LoginForm,
    SellerRegistrationForm,
    FarmerRegistrationForm,
    AdminLoginForm,
)
from .models import Profile
from django.views.generic import TemplateView
from seller.models import Seller
from django.urls import reverse_lazy
from django.contrib.auth.models import User
from kishan.models import Booking, Tool


class AdminRootRedirectView(View):
    def get(self, request, *args, **kwargs):
        return redirect("admin_login")


class AdminLoginView(View):
    template_name = "assets/accounts/admin_login.html"
    form_class = AdminLoginForm

    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect("admin-dashboard")
        elif request.user.is_authenticated and not request.user.is_staff:
            logout(request)
            messages.error(request, "You are not authorized as admin.")
            return redirect("admin_login")
        return render(request, self.template_name, {"form": self.form_class()})

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)
            if user and user.is_staff:
                login(request, user)
                return redirect("admin-dashboard")
            messages.error(request, "Invalid credentials or not authorized as admin.")
        return render(request, self.template_name, {"form": form})

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "assets/accounts/admin_dashboard/admin_dashboard.html"

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        return redirect("admin_login")

    def get(self, request):
        return render(request, self.template_name)


class AdminLogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("admin_login")

# seller register
class SellerRegisterView(View):
    def get(self, request):
        form = SellerRegistrationForm()
        return render(
            request, "assets/accounts/seller_registration.html", {"form": form}
        )

    def post(self, request):
        form = SellerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.get_or_create_profile(user).is_seller = True
            messages.success(request, "Seller registered successfully!.")
            return redirect("seller-login")
        return render(
            request, "assets/accounts/seller_registration.html", {"form": form}
        )


class FarmerRegisterView(View):
    def get(self, request):
        form = FarmerRegistrationForm()
        return render(
            request, "assets/accounts/farmer_registration.html", {"form": form}
        )

    def post(self, request):
        form = FarmerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.get_or_create_profile(user).is_farmer = True
            messages.success(request, "Farmer registered successfully.")
            return redirect("farmer-login")
        return render(
            request, "assets/accounts/farmer_registration.html", {"form": form}
        )


class SellerLoginView(View):
    def get(self, request):
        form = LoginForm()
        return render(
            request,
            "assets/accounts/login.html",
            {
                "form": form,
                "form_action": request.path,
                "role": "seller",
            },
        )

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)
            if user:
                profile = Profile.get_or_create_profile(user)
                if profile.is_seller:
                    login(request, user)
                    return redirect("seller-dashboard")
                messages.error(request, "You are not registered as a seller.")
            else:
                messages.error(request, "Invalid username or password.")
        return render(
            request,
            "assets/accounts/login.html",
            {
                "form": form,
                "form_action": request.path,
                "role": "seller",
            },
        )


class FarmerLoginView(View):
    def get(self, request):
        form = LoginForm()
        return render(
            request,
            "assets/accounts/login.html",
            {
                "form": form,
                "form_action": request.path,
                "role": "farmer",
            },
        )

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)
            if user:
                profile = Profile.get_or_create_profile(user)
                if profile.is_farmer:
                    login(request, user)
                    return redirect("home")
                messages.error(request, "You are not registered as a farmer.")
            else:
                messages.error(request, "Invalid username or password.")
        return render(
            request,
            "assets/accounts/login.html",
            {
                "form": form,
                "form_action": request.path,
                "role": "farmer",
            },
        )


class SellerDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        seller = getattr(request.user, "seller", None)

        approval_confirmed = False

        if seller and seller.is_approved:
            if not seller.approval_notification_seen_by_seller:
                approval_confirmed = True
            else:
                viewed_at = seller.approval_notification_viewed_at_by_seller
                if viewed_at:
                    now = timezone.now()
                    diff = now - viewed_at
                    if diff.total_seconds() <= 3600:
                        approval_confirmed = True

        total_tools = 0
        recent_bookings = Booking.objects.none()

        if seller:
            total_tools = Tool.objects.filter(owner=seller).count()

            # Get recent bookings for tools owned by this seller
            # Order by latest start_date or created_at (adjust as needed)
            recent_bookings = (
                Booking.objects.filter(tool__owner=seller)
                .select_related("tool", "farmer__user")
                .order_by("-start_date")[:5]  # last 5 bookings
            )

        context = {
            "seller": seller,
            "approval_confirmed": approval_confirmed,
            "total_tools": total_tools,
            "recent_bookings": recent_bookings,
        }

        return render(request, "assets/seller/seller_dashboard.html", context)

    def post(self, request):
        seller = getattr(request.user, "seller", None)

        if "confirm_approval" in request.POST and seller:
            seller.approval_notification_seen_by_seller = True
            seller.approval_notification_viewed_at_by_seller = timezone.now()
            seller.save()

        return redirect("seller-dashboard")


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("home")


class RegisteredShopsView(View):
    template_name = (
        "assets/accounts/admin_dashboard/sidebar/registered_approval_shop.html"
    )

    def get(self, request):
        pending_shops = Seller.objects.filter(is_approved=False)
        approved_shops = Seller.objects.filter(is_approved=True)
        return render(
            request,
            self.template_name,
            {"pending_shops": pending_shops, "approved_shops": approved_shops},
        )

    def post(self, request):
        shop_id = request.POST.get("shop_id")
        action = request.POST.get("action")

        try:
            seller = Seller.objects.get(id=shop_id)
            if action == "approve" and not seller.is_approved:
                seller.is_approved = True
                seller.approval_notification_seen_by_seller = False
                seller.approval_notification_viewed_at_by_seller = None
                seller.save()
            elif action == "delete":
                seller.delete()
        except Seller.DoesNotExist:
            pass

        return redirect("registered-shops")


class RegisteredSellersView(View):
    template_name = "assets/accounts/admin_dashboard/sidebar/registered_sellers.html"

    def get(self, request):
        sellers = User.objects.filter(profile__is_seller=True, last_login__isnull=False)
        return render(
            request,
            self.template_name,
            {
                "sellers": sellers,
            },
        )

    def post(self, request):
        seller_id = request.POST.get("seller_id")
        action = request.POST.get("action")

        if action == "delete" and seller_id:
            seller_user = get_object_or_404(User, id=seller_id)
            seller_user.delete()
            messages.success(request, "Seller deleted successfully.")

        return redirect(reverse_lazy("registered-sellers"))


class RegisteredFarmersView(View):
    template_name = "assets/accounts/admin_dashboard/sidebar/registered_farmers.html"

    def get(self, request):
        farmers = User.objects.filter(profile__is_farmer=True, last_login__isnull=False)
        return render(
            request,
            self.template_name,
            {
                "farmers": farmers,
            },
        )

    def post(self, request):
        farmer_id = request.POST.get("farmer_id")
        action = request.POST.get("action")

        if action == "delete" and farmer_id:
            farmer_user = get_object_or_404(User, id=farmer_id)
            farmer_user.delete()
            messages.success(request, "Farmer deleted successfully.")

        return redirect(reverse_lazy("registered-farmers"))
