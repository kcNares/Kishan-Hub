from django.urls import path
from seller import views

urlpatterns = [
    path(
        "register/",
        views.SellerRegisterShopView.as_view(),
        name="register-shop",
    ),
    path("tools/", views.ToolListView.as_view(), name="tools-list"),
    path(
        "tools/delete/<int:pk>/",
        views.ToolDeleteView.as_view(),
        name="tool-delete",
    ),
    path("categories/", views.CategoryListView.as_view(), name="categories-list"),
    path(
        "categories/delete/<int:pk>/",
        views.CategoryDeleteView.as_view(),
        name="category-delete",
    ),
    path("tags/", views.TagListView.as_view(), name="tags-list"),
    path("tags/delete/<int:pk>/", views.TagDeleteView.as_view(), name="tag-delete"),
    path(
        "bookings/",
        views.SellerBookingListView.as_view(),
        name="booking-list",
    ),
    path(
        "bookings/<int:pk>/confirm/",
        views.BookingConfirmView.as_view(),
        name="booking-confirm",
    ),
    path(
        "bookings/<int:pk>/cancel/",
        views.BookingCancelView.as_view(),
        name="booking-cancel",
    ),
    path(
        "bookings/<int:pk>/delete/",
        views.BookingDeleteView.as_view(),
        name="booking-delete",
    ),
    path("payments/", views.SellerPaymentListView.as_view(), name="payments-list"),
    path(
        "payments/<int:pk>/mark-paid/",
        views.MarkPaymentPaidView.as_view(),
        name="mark-paid",
    ),
    path(
        "rentals/<int:pk>/delete/",
        views.DeleteRentalView.as_view(),
        name="delete-rental",
    ),
    path("reviews/", views.SellerReviewListView.as_view(), name="seller_reviews"),
    path(
        "reviews/<int:pk>/reply/",
        views.SellerReplyCreateView.as_view(),
        name="seller_reply_create",
    ),
    path(
        "reviews/<int:pk>/reply/update/",
        views.SellerReplyUpdateView.as_view(),
        name="seller_reply_update",
    ),
    path(
        "reviews/<int:pk>/reply/delete/",
        views.SellerReplyDeleteView.as_view(),
        name="seller_reply_delete",
    ),
    path(
        "reviews/<int:pk>/delete/",
        views.SellerReviewDeleteView.as_view(),
        name="seller_review_delete",
    ),
]
