from django.urls import path
from .views import (
    AdminDashboardView,
    AdminLogoutView,
    AdminRootRedirectView,
    AdminLoginView,
    FarmerLoginView,
    FarmerRegisterView,
    LogoutView,
    RegisteredFarmersView,
    RegisteredSellersView,
    RegisteredShopsView,
    SellerDashboardView,
    SellerLoginView,
    SellerRegisterView)

urlpatterns = [
    # Admin
    path("", AdminRootRedirectView.as_view(), name="admin_root_redirect"),
    path("admin/login/", AdminLoginView.as_view(), name="admin_login"),
    path("admin/dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("admin/logout/", AdminLogoutView.as_view(), name="admin-logout"),
    path(
        "admin/registered-shops/",
        RegisteredShopsView.as_view(),
        name="registered-shops",
    ),
    path(
        "registered-sellers/",
        RegisteredSellersView.as_view(),
        name="registered-sellers",
    ),
    path(
        "registered-farmers/",
        RegisteredFarmersView.as_view(),
        name="registered-farmers",
    ),
    # seller
    path("seller/register/", SellerRegisterView.as_view(), name="seller-register"),
    path("seller/login/", SellerLoginView.as_view(), name="seller-login"),
    path("seller/dashboard/", SellerDashboardView.as_view(), name="seller-dashboard"),
    path("seller/logout/", LogoutView.as_view(), name="seller-logout"),
    # farmer
    path("farmer/register/", FarmerRegisterView.as_view(), name="farmer-register"),
    path("farmer/login/", FarmerLoginView.as_view(), name="farmer-login"),
    path("farmer/logout/", LogoutView.as_view(), name="farmer-logout"),
]
