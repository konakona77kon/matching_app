from django.urls import path
from . import views
from django.conf import settings


urlpatterns = [
    # プロフィール関連
    path("my/edit/", views.edit_my_profile, name="edit_my_profile"),
    path("matches/", views.match_list, name="match_list"),
    path("likes/inbox/", views.like_inbox, name="like_inbox"),
    path("me/", views.my_profile, name="my_profile"),

    # プロフィール一覧
    path("list/", views.profile_list, name="profile_list"),

    # プロフィール新規作成フォーム
    path("new/", views.profile_form, name="profile_form"),
    path("done/", views.profile_done, name="profile_done"),

    # プロフィール詳細
    path("detail/<int:pk>/", views.profile_detail, name="profile_detail"),

    # いいね送信
    path("detail/<int:pk>/like/", views.send_like, name="send_like"),

    # チャット開始（相互いいねチェック）
    path("detail/<int:pk>/chat/", views.start_chat, name="start_chat"),

    # チャットルーム
    path("chat/<int:room_id>/", views.chat_room, name="chat_room"),
    path("chats/", views.chat_list, name="chat_list"),

    # 通話リクエスト関連
    path(
        "chat/<int:room_id>/call/request/<str:mode>/",
        views.send_call_request,
        name="send_call_request",
    ),
    path(
        "chat/call/accept/<int:request_id>/",
        views.accept_call_request,
        name="accept_call_request",
    ),
    path(
        "chat/call/reject/<int:request_id>/",
        views.reject_call_request,
        name="reject_call_request",
    ),

    # ブロック
    path("block/<int:pk>/", views.block_user, name="block_user"),
    path("unblock/<int:pk>/", views.unblock_user, name="unblock_user"),

    # 掲示板
    path("board/", views.board_list, name="board_list"),
    path("board/new/", views.board_create, name="board_create"),
    path("board/<int:pk>/", views.board_detail, name="board_detail"),
]