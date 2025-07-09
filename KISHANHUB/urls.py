"""
URL configuration for KISHANHUB project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("djadmin/", admin.site.urls),  # Keep for Django's default admin (optional)
    path("accounts/", include("accounts.urls")),  # All role-based auth lives here
    path("admin/", include("accounts.urls")),  # Allow /admin/ → custom admin system
    path(
        "tools/", include("kishan.urls")
    ),  # Include kishan app URLs under 'tools/' path
    path("seller/", include("seller.urls")),
    path("", include("kishan.urls")),
    path("kishan/", include("kishan.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
