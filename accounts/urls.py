from django.urls import path
from .views import (
    AdminDashboardView,
    AdminDeleteMessageView,
    AdminLogoutView,
    AdminMessagesView,
    AdminReplyMessageView,
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
    SellerRegisterView,
    ShopDocumentsView)

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
        "shops/<int:shop_id>/documents/",
        ShopDocumentsView.as_view(),
        name="shop_documents_view",
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
    path("admin/messages/", AdminMessagesView.as_view(), name="admin-messages"),
    path(
        "admin/messages/reply/<int:pk>/",
        AdminReplyMessageView.as_view(),
        name="admin_reply_message",
    ),
    path(
        "admin/messages/delete/<int:pk>/",
        AdminDeleteMessageView.as_view(),
        name="admin_delete_message",
    ),
]
