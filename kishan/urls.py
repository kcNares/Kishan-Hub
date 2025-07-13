from django.urls import path
from kishan import views

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
]
