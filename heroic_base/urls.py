"""
URL configuration for heroic_base project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.urls import path, re_path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from heroic_api.views import LoginRedirectView, LogoutRedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('mozilla_django_oidc.urls')),
    path('login-redirect/', LoginRedirectView.as_view(), name='login-redirect'),
    path('logout-redirect/', LogoutRedirectView.as_view(), name='logout-redirect'),
    re_path(r'^api/', include(('heroic_api.urls', 'api'), namespace='api')),  # Include heroic_api routes
    # drf-spectacular OpenAPI docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
