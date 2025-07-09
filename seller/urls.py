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
]
