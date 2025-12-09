# config/urls.py

from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.auth import views as auth_views
from matching import views as matching_views
from django.conf import settings
from django.views.static import serve
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    # ★トップページ（1個だけ）
    path("debug-users/", matching_views.debug_users, name="debug_users"),
    path("", matching_views.home, name="home"),

    path("admin/", admin.site.urls),

    # 認証
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="matching/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        matching_views.logout_view,   # ← ここを変更
        name="logout",
    ),
    path("accounts/signup/", matching_views.signup, name="signup"),
    path("accounts/", include("django.contrib.auth.urls")),

    # プロフィール・チャット
    path("profile/", include("matching.urls")),

    # その他ページ
    path("ladies_free/", matching_views.ladies_free, name="ladies_free"),
    path("terms/", matching_views.terms, name="terms"),
    path("privacy/", matching_views.privacy, name="privacy"),
    path("rules/", matching_views.rules, name="rules"),
    path("contact/", matching_views.contact, name="contact"),
    path("account/delete/", matching_views.delete_account, name="delete_account"),
]

handler404 = "matching.views.custom_404"
handler500 = "matching.views.custom_500"

# ★ media 配信（DEBUG 関係なし）
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
        name="media",
    ),
]

# ★ static は DEBUG=True のときのみ
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
