from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve as static_serve
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend_dist"


def spa_index(request):
    """返回前端单页应用入口（前端路由由 Vue Router 接管）。"""
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return HttpResponse(index.read_text(encoding="utf-8"), content_type="text/html")
    return HttpResponse(
        "前端尚未构建：请先在 client/ 下执行 npm install && npm run build",
        status=503,
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("revrec.urls")),
    re_path(r"^assets/(?P<path>.*)$", static_serve, {"document_root": FRONTEND_DIST / "assets"}),
    re_path(r"^(?!api/|admin/|assets/).*$", spa_index),
]
