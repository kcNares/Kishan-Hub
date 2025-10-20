from django.urls import path
from kishan import views
from .views import EsewaFailureView, EsewaSuccessView, RentalCODSuccessView, RentalEsewaSuccessView

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("alltools/", views.AllToolsView.as_view(), name="all-tools"),
    path("about/", views.AboutView.as_view(), name="about"),
    path("search/", views.ToolSearchResultsView.as_view(), name="tool-search-results"),
    path(
        "autocomplete/", views.ToolAutocompleteView.as_view(), name="tool-autocomplete"
    ),
    path("tool/<int:pk>/", views.ToolDetailView.as_view(), name="tool-detail"),
    path(
        "tool/<int:pk>/review/",
        views.ToolReviewCreateView.as_view(),
        name="tool-review-create",
    ),
    path(
        "review/delete/<int:pk>/",
        views.DeleteReviewView.as_view(),
        name="delete-review",
    ),
    path("booking/create/", views.BookingCreateView.as_view(), name="booking-create"),
    path(
        "check-tool-availability/",
        views.ToolAvailabilityCheckView.as_view(),
        name="check_tool_availability",
    ),
    path(
        "notifications/read/<int:notif_id>/",
        views.MarkNotificationReadView.as_view(),
        name="mark-notification-read",
    ),
    path(
        "notification/<int:pk>/",
        views.NotificationRedirectView.as_view(),
        name="notification-redirect",
    ),
    path("kishan/rent/<int:tool_id>/", views.RentToolView.as_view(), name="rent-tool"),
    path(
        "rental/cod-success/<int:pk>/",
        RentalCODSuccessView.as_view(),
        name="rental-cod-success",
    ),
    path(
        "rentals/esewa/success/<int:pk>/",
        RentalEsewaSuccessView.as_view(),
        name="rental-esewa-success",
    ),
    path("esewa/success/", EsewaSuccessView.as_view(), name="esewa-success"),
    path("esewa/failure/", EsewaFailureView.as_view(), name="esewa-failure"),
]
