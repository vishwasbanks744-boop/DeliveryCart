from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.urls import include, path, re_path
from django.views.static import serve

from orders import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("orders.urls")),
    path("api/config/public", views.public_client_config, name="public-client-config"),
    path("login/", RedirectView.as_view(url="/login.html", permanent=False)),
    path("", views.homepage, name="homepage"),
    path("category/<slug:slug>", views.frontend_page, {"page": "category"}, name="category-page"),
    path("<str:page>.html", views.frontend_page, name="frontend-page"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>restaurant-logos/[^/]+)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        )
    ]
