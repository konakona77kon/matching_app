from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q, Case, When, IntegerField
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings

from datetime import datetime, timezone as dt_timezone
from collections import Counter
import random

from .forms import ContactForm, UserProfileForm, BoardPostForm
from .models import (
    UserProfile,
    Like,
    ChatRoom,
    Message,
    CallRequest,
    ChatReadState,
    ProfilePhoto,
    Block,
    SearchCondition,
    ContactMessage,
    BoardPost,
)
from .utils import (
    is_safe_file,
    resize_image_if_needed,
    validate_video_size,
    detect_file_type,
)
from django.contrib.auth import logout

def custom_404(request, exception):
    return render(request, "matching/404.html", status=404)


def custom_500(request):
    # ★ テンプレートパスを "matching/500.html" にする
    return render(request, "matching/500.html", status=500)
# 都道府県 → 地方グループ
REGION_GROUPS = {
    "北海道・東北": ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"],
    "関東": ["茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"],
    "中部": [
        "新潟県",
        "富山県",
        "石川県",
        "福井県",
        "山梨県",
        "長野県",
        "岐阜県",
        "静岡県",
        "愛知県",
    ],
    "近畿": ["三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"],
    "中国": ["鳥取県", "島根県", "岡山県", "広島県", "山口県"],
    "四国": ["徳島県", "香川県", "愛媛県", "高知県"],
    "九州・沖縄": [
        "福岡県",
        "佐賀県",
        "長崎県",
        "熊本県",
        "大分県",
        "宮崎県",
        "鹿児島県",
        "沖縄県",
    ],
}


def get_region_name(prefecture: str) -> str | None:
    """都道府県から地方名（REGION_GROUPS のキー）を返す"""
    if not prefecture:
        return None
    for region, prefs in REGION_GROUPS.items():
        if prefecture in prefs:
            return region
    return None


def is_blocked(me, other):
    # 自分がブロックしている or 相手にブロックされている
    return Block.objects.filter(
        Q(blocker=me, blocked=other) | Q(blocker=other, blocked=me)
    ).exists()


# ========== 通話関連 ==========


@login_required
def accept_call_request(request, request_id):
    call_req = get_object_or_404(
        CallRequest,
        id=request_id,
        callee__user=request.user,
        is_active=True,
        is_accepted__isnull=True,  # ★まだ未決のものだけ
    )
    call_req.is_accepted = True
    call_req.is_active = False
    call_req.save()

    url = reverse("call_room", args=[call_req.room.id])
    return redirect(f"{url}?mode={call_req.mode}")


@login_required
def reject_call_request(request, request_id):
    call_req = get_object_or_404(
        CallRequest,
        id=request_id,
        callee__user=request.user,
        is_active=True,
        is_accepted__isnull=True,  # ★まだ未決のものだけ
    )
    call_req.is_accepted = False
    call_req.is_active = False
    call_req.save()

    return redirect("chat_room", room_id=call_req.room.id)


@login_required
def send_call_request(request, room_id, mode):
    """チャット画面から通話ボタンを押した時に呼ばれる"""
    room = get_object_or_404(ChatRoom, id=room_id)
    me = get_object_or_404(UserProfile, user=request.user)

    # ルームの相手
    if room.user1_id == me.id:
        partner = room.user2
    else:
        partner = room.user1

    if request.method == "POST":
        # 既存のアクティブなリクエストを一旦無効化（連打対策）
        CallRequest.objects.filter(
            room=room,
            caller=me,
            callee=partner,
            is_active=True,
        ).update(is_active=False)

        CallRequest.objects.create(
            room=room,
            caller=me,
            callee=partner,
            mode=mode,
        )

        # 自分はそのまま通話ルームへ
        url = reverse("call_room", args=[room.id])
        return redirect(f"{url}?mode={mode}")

    # GET で直接叩かれたらチャットに戻す
    return redirect("chat_room", room_id=room.id)


@login_required
def call_room(request, room_id):
    me = get_current_profile(request)
    room = get_object_or_404(ChatRoom, pk=room_id)

    # 参加者チェック
    if me not in [room.user1, room.user2]:
        return redirect("profile_list")

    mode = request.GET.get("mode", "audio")
    return render(
        request,
        "matching/call.html",
        {
            "room": room,
            "me": me,
            "partner": room.user2 if room.user1 == me else room.user1,
            "mode": mode,
        },
    )


# ========== 通知系（いいね・マッチ一覧） ==========


# matching/views.py

@login_required
def like_inbox(request):
    """
    自分に届いている「いいね」の通知一覧。
    ・まだ相互いいねになっていない「片想いのいいね」
    ・最近新しく成立した「マッチ」
    の両方を表示する。
    """
    me = get_current_profile(request)

    # 自分が「いいね」した相手ID
    liked_ids = Like.objects.filter(
        from_user=me
    ).values_list("to_user_id", flat=True)

    # ① 片想いの「いいね」一覧
    incoming_likes = (
        Like.objects.filter(to_user=me)
        .exclude(from_user_id__in=liked_ids)
        .select_related("from_user")
        .order_by("-id")
    )

    # ② 新しく成立した「マッチ」一覧
    last_checked_matches = me.last_checked_matches or datetime(2000, 1, 1, tzinfo=dt_timezone.utc)

    recent_liked_me_ids = Like.objects.filter(
        to_user=me,
        created_at__gt=last_checked_matches,
    ).values_list("from_user_id", flat=True)

    new_match_ids = set(recent_liked_me_ids) & set(liked_ids)

    new_match_partners = UserProfile.objects.filter(id__in=new_match_ids)

    new_matches = []
    for partner in new_match_partners:
        room = ChatRoom.objects.filter(
            Q(user1=me, user2=partner) | Q(user1=partner, user2=me)
        ).first()

        new_matches.append({
            "partner": partner,
            "room": room,
        })

    # 通知確認時刻を更新
    now = timezone.now()
    me.last_checked_likes = now
    me.last_checked_matches = now
    me.save(update_fields=["last_checked_likes", "last_checked_matches"])

    context = {
        "me": me,
        "incoming_likes": incoming_likes,
        "new_matches": new_matches,
        "current_tab": "notice",
    }
    return render(request, "matching/like_inbox.html", context)


@login_required
def match_list(request):
    """相互いいねしている相手の一覧"""
    me = get_current_profile(request)

    # 自分が「いいね」した相手
    liked_ids = Like.objects.filter(from_user=me).values_list(
        "to_user_id", flat=True
    )

    # 相手から「いいね」されている人
    liked_me_ids = Like.objects.filter(to_user=me).values_list(
        "from_user_id", flat=True
    )

    # 相互いいねになっている相手ID
    mutual_ids = set(liked_ids) & set(liked_me_ids)

    partners = UserProfile.objects.filter(id__in=mutual_ids)

    # ★ 「マッチ一覧を見た」時刻を更新
    me.last_checked_matches = timezone.now()
    me.save(update_fields=["last_checked_matches"])

    context = {
        "me": me,
        "partners": partners,
    }
    return render(request, "matching/match_list.html", context)


# ========== プロフィール編集 ==========


@login_required
def edit_my_profile(request):
    me = get_current_profile(request)

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=me)
        if form.is_valid():
            form.save()

            # ★ 複数プロフィール写真の保存
            photo_files = request.FILES.getlist("photos")  # input name="photos" を想定
            for idx, f in enumerate(photo_files):
                ProfilePhoto.objects.create(
                    profile=me,
                    image=f,
                    order=idx,
                )

            return redirect("my_profile")
    else:
        form = UserProfileForm(instance=me)

    return render(
        request,
        "matching/my_profile_edit.html",
        {
            "form": form,
            "me": me,
            # 既存のサブ写真もテンプレートで使えるように渡しておく
            "photos": me.photos.all(),
            "current_tab": "me",
        },
    )



@login_required
def my_profile(request):
    """自分のプロフィール詳細（レイアウトは他人の詳細と同じ）"""
    me = get_current_profile(request)
    if not me:
        return redirect("signup")

    return render(
        request,
        "matching/detail.html",
        {
            "profile": me,
            "me": me,
            # ギャラリー表示用
            "photos": me.photos.all(),
            "current_tab": "me",
        },
    )


def home(request):
    """ログイン前の入口ページ"""
    return render(request, "matching/home.html")


# ========== 共通ヘルパー ==========


def get_current_profile(request):
    """
    ログイン中ユーザーに対応する UserProfile を返す。
    なければ作る（ニックネームはユーザー名）。
    """
    if not request.user.is_authenticated:
        return None

    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "nickname": request.user.username,
        },
    )
    return profile


# ========== 認証まわり ==========


def signup(request):
    """
    ユーザー新規登録 + UserProfile 作成 → そのままログイン
    /accounts/signup/ から来る想定
    """
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        # プロフィール用の値をフォームから取得
        nickname = request.POST.get("nickname", "").strip()
        age_range = request.POST.get("age_range", "").strip()
        area = request.POST.get("area", "").strip()
        purpose = request.POST.get("purpose", "").strip()
        job = request.POST.get("job", "").strip()
        prefecture = request.POST.get("prefecture", "").strip()
        gender = request.POST.get("gender") or None
        bio = request.POST.get("bio", "").strip()
        income_raw = request.POST.get("income", "").strip()
        avatar = request.FILES.get("avatar")

        income = None
        if income_raw:
            try:
                income = int(income_raw)
            except ValueError:
                income = None  # 数値変換できなければ無視（後で編集可）

        if form.is_valid():
            user = form.save()

            profile = UserProfile.objects.create(
                user=user,
                nickname=nickname or user.username,
                age_range=age_range,
                area=area,
                purpose=purpose,
                job=job,
                income=income,
                prefecture=prefecture,
                gender=gender,
                bio=bio,
            )
            if avatar:
                profile.avatar = avatar
                profile.save(update_fields=["avatar"])

            auth_login(request, user)
            return redirect("profile_detail", pk=profile.pk)
    else:
        form = UserCreationForm()

    return render(request, "matching/signup.html", {"form": form})


# ========== プロフィール一覧 / 詳細 ==========


@login_required
def profile_list(request):
    me = get_current_profile(request)

    # 自分以外
    qs = UserProfile.objects.exclude(user=request.user)

    # 性別が M/F のときだけ「異性のみ」フィルタ
    if me.gender in ("M", "F"):
        opposite = "F" if me.gender == "M" else "M"
        qs = qs.filter(gender=opposite)

    # いいね済み + ブロック関係のある相手は除外
    liked_ids = Like.objects.filter(
        from_user=me
    ).values_list("to_user_id", flat=True)

    blocked_by_me_ids = Block.objects.filter(
        blocker=me
    ).values_list("blocked_id", flat=True)

    blocked_me_ids = Block.objects.filter(
        blocked=me
    ).values_list("blocker_id", flat=True)

    hidden_ids = set(list(liked_ids) + list(blocked_by_me_ids) + list(blocked_me_ids))
    if hidden_ids:
        qs = qs.exclude(id__in=hidden_ids)

    # ▼ 絞り込みパラメータ取得 -------------------------
    pref = request.GET.get("pref", "").strip()
    gender = request.GET.get("gender", "").strip()
    purpose = request.GET.get("purpose", "").strip()
    min_income_raw = request.GET.get("min_income", "").strip()
    photo_only = request.GET.get("photo_only", "")
    age_filter = request.GET.get("age", "any").strip()
    current_order = request.GET.get("order", "recommended")

    # 都道府県フィルタ
    if pref:
        qs = qs.filter(prefecture=pref)

    # 性別フィルタ（上の「異性のみ」と両立させたいなら AND になる）
    if gender:
        qs = qs.filter(gender=gender)

    # ★ 利用目的フィルタ
    if purpose:
        qs = qs.filter(purpose=purpose)

    # 年収下限
    min_income = None
    if min_income_raw:
        try:
            min_income = int(min_income_raw)
            qs = qs.filter(income__gte=min_income)
        except ValueError:
            min_income = None

    # 写真ありのみ
    if photo_only == "1":
        qs = qs.exclude(avatar="").exclude(avatar__isnull=True)

    # 年齢フィルタ（自分と同じ age_range）
    if age_filter == "near" and me.age_range:
        qs = qs.filter(age_range=me.age_range)

    # 一旦 list 化して Python 側でスコアリング
    profiles = list(qs)

    # 地方ざっくり判定用
    def get_region(pref_name):
        table = {
            "北海道": "北海道",
            "青森県": "東北", "岩手県": "東北", "宮城県": "東北", "秋田県": "東北",
            "山形県": "東北", "福島県": "東北",
            "茨城県": "関東", "栃木県": "関東", "群馬県": "関東", "埼玉県": "関東",
            "千葉県": "関東", "東京都": "関東", "神奈川県": "関東",
            "新潟県": "中部", "富山県": "中部", "石川県": "中部", "福井県": "中部",
            "山梨県": "中部", "長野県": "中部", "岐阜県": "中部",
            "静岡県": "中部", "愛知県": "中部",
            "三重県": "近畿", "滋賀県": "近畿", "京都府": "近畿",
            "大阪府": "近畿", "兵庫県": "近畿", "奈良県": "近畿", "和歌山県": "近畿",
            "鳥取県": "中国", "島根県": "中国", "岡山県": "中国",
            "広島県": "中国", "山口県": "中国",
            "徳島県": "四国", "香川県": "四国", "愛媛県": "四国", "高知県": "四国",
            "福岡県": "九州", "佐賀県": "九州", "長崎県": "九州", "熊本県": "九州",
            "大分県": "九州", "宮崎県": "九州", "鹿児島県": "九州", "沖縄県": "九州",
        }
        return table.get(pref_name or "", "")

    # ▼ 並び順 -----------------------------------------
    if current_order == "new":
        profiles.sort(key=lambda p: p.id, reverse=True)
    elif current_order == "random":
        random.shuffle(profiles)
    else:
        # おすすめ：同県 > 同じ地方 > 年齢レンジ近い > 新しい
        my_region = get_region(me.prefecture)

        def score(p):
            s = 0
            if p.prefecture == me.prefecture:
                s += 20
            if my_region and get_region(p.prefecture) == my_region:
                s += 10
            if me.age_range and p.age_range and me.age_range == p.age_range:
                s += 3
            # ★ 利用目的が同じならちょっと加点
            if me.purpose and p.purpose and me.purpose == p.purpose:
                s += 2
            s += p.id / 1000.0  # 新しいほど少し上に
            return -s

        profiles.sort(key=score)

    # フィルタ用の選択肢

    context = {
        "me": me,
        "profiles": profiles,
        "current_order": current_order,
        "age_filter": age_filter,

        # フィルタ状態
        "pref": pref,
        "gender": gender,
        "purpose": purpose,
        "min_income": min_income_raw,
        "photo_only": photo_only,

        # 選択肢
        "pref_choices": UserProfile.PREF_CHOICES,
        "gender_choices": UserProfile.GENDER_CHOICES,
        "purpose_choices": UserProfile.PURPOSE_CHOICES,

    }

    context["current_tab"] = "search"

    return render(request, "matching/list.html", context)



@login_required
def profile_detail(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk)
    me = get_current_profile(request)

    iine_sent = False
    can_chat = False

    if me and me != profile:
        iine_sent = Like.objects.filter(
            from_user=me, to_user=profile
        ).exists()

        you_to_me = Like.objects.filter(
            from_user=profile, to_user=me
        ).exists()

        can_chat = iine_sent and you_to_me

    is_blocked_flag = is_blocked(me, profile) if me and me != profile else False
    blocked_by_me = Block.objects.filter(
        blocker=me, blocked=profile
    ).exists() if me and me != profile else False

    photos_qs = profile.photos.all()  # ★ここ

    context = {
        "profile": profile,
        "me": me,
        "iine_sent": iine_sent,
        "can_chat": can_chat,
        "is_blocked": is_blocked_flag,
        "blocked_by_me": blocked_by_me,
        "photos": photos_qs,
    }
    return render(request, "matching/detail.html", context)


def profile_form(request):
    """旧 form でプロフィールだけ作る機能（いまは使わなくてもOK）"""
    if request.method == "POST":
        nickname = request.POST.get("nickname")
        age_range = request.POST.get("age_range")
        area = request.POST.get("area")
        purpose = request.POST.get("purpose")

        if nickname and age_range and area and purpose:
            UserProfile.objects.create(
                nickname=nickname,
                age_range=age_range,
                area=area,
                purpose=purpose,
            )
            return redirect("profile_done")

    return render(request, "matching/form.html")


def profile_done(request):
    return render(request, "matching/done.html")


# ========== いいね ==========


@login_required
def send_like(request, pk):
    me = get_current_profile(request)
    target = get_object_or_404(UserProfile, pk=pk)

    if is_blocked(me, target):
        messages.error(request, "このユーザーにはアクションできません。")
        return redirect("profile_detail", pk=pk)

    like, created = Like.objects.get_or_create(
        from_user=me,
        to_user=target,
    )

    mutual_like = Like.objects.filter(
        from_user=target,
        to_user=me,
    ).exists()

    if mutual_like:
        existing = ChatRoom.objects.filter(
            Q(user1=me, user2=target) | Q(user1=target, user2=me)
        ).first()

        if not existing:
            ChatRoom.objects.create(user1=me, user2=target)

    messages.success(request, "いいねを送信しました。")
    return redirect("profile_detail", pk=pk)


# ========== チャット開始 / ルーム ==========


@login_required
def start_chat(request, pk):
    """「この人とチャットする」を押したとき"""
    me = get_current_profile(request)
    partner = get_object_or_404(UserProfile, pk=pk)

    if me == partner:
        return redirect("profile_detail", pk=pk)

    me_to_you = Like.objects.filter(from_user=me, to_user=partner).exists()
    you_to_me = Like.objects.filter(from_user=partner, to_user=me).exists()

    if not (me_to_you and you_to_me):
        return render(
            request,
            "matching/chat_locked.html",
            {"target": partner, "me": me},
        )

    u1, u2 = sorted([me, partner], key=lambda u: u.pk)
    room, created = ChatRoom.objects.get_or_create(user1=u1, user2=u2)

    return redirect("chat_room", room_id=room.id)


@login_required
def chat_room(request, room_id):
    # ① チャットルーム取得
    room = get_object_or_404(ChatRoom, id=room_id)

    # ② 自分のプロフィール
    me = get_current_profile(request)
    if me is None:
        return redirect("profile_form")

    # ③ このルームの参加者かチェック＆相手判定
    if room.user1_id == me.id:
        partner = room.user2
    elif room.user2_id == me.id:
        partner = room.user1
    else:
        # 自分と関係ない room_id を直打ちされたときは弾く
        messages.error(request, "このチャットルームには参加していません。")
        return redirect("chat_list")

    # ブロックチェック
    if is_blocked(me, partner):
        messages.error(
            request, "このユーザーとはチャットできません（ブロック中です）。"
        )
        return redirect("chat_list")

    # ④ メッセージ一覧
    messages_qs = Message.objects.filter(room=room).order_by("created_at")

    # ⑤ 着信（未処理の通話リクエスト）1件拾う
    incoming_call = (
        CallRequest.objects.filter(
            room=room,
            callee=me,
            is_active=True,
            is_accepted__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )

    # ⑥ メッセージ送信
    if request.method == "POST":
        text = request.POST.get("message", "").strip()
        uploaded_file = request.FILES.get("file")

        msg = Message(room=room, sender=me)

        # テキスト
        if text:
            msg.text = text

        # ファイル（画像 or 動画）
        if uploaded_file:
            # まず形式チェック（Content-Type + 拡張子）
            if not is_safe_file(uploaded_file):
                messages.error(
                    request,
                    "このファイル形式は送信できません。",
                )
                return redirect("chat_room", room_id=room.id)

            ftype = detect_file_type(uploaded_file)

            # 画像の場合：必要ならリサイズ
            if ftype == "image":
                safe_image = resize_image_if_needed(uploaded_file)
                msg.image = safe_image

            # 動画の場合：サイズチェックだけ（変換はしない）
            elif ftype == "video":
                if not validate_video_size(uploaded_file):
                    messages.error(
                        request,
                        f"動画ファイルが大きすぎます（最大 {settings.MAX_VIDEO_SIZE_MB}MB まで）。",
                    )
                    return redirect("chat_room", room_id=room.id)
                msg.video = uploaded_file

            # どちらでもない → 危険なので拒否
            else:
                messages.error(
                    request,
                    "送信できるのは画像（JPEG/PNG/GIF）と動画ファイルのみです。",
                )
                return redirect("chat_room", room_id=room.id)

        # 何かしら内容がある場合だけ保存
        if msg.text or msg.image or msg.video:
            msg.save()
        else:
            messages.info(request, "空のメッセージは送信されません。")

        return redirect("chat_room", room_id=room.id)

    # ⑦ 既読更新
    read_state, created = ChatReadState.objects.get_or_create(
        user=me,
        room=room,
        defaults={"last_read_at": timezone.now()},
    )
    read_state.last_read_at = timezone.now()
    read_state.save(update_fields=["last_read_at"])

    # ⑧ テンプレートへ
    context = {
        "room": room,
        "room_id": room.id,
        "me": me,
        "partner": partner,
        "messages": messages_qs,
        "incoming_call": incoming_call,
        "current_tab": "chat",
    }
    return render(request, "matching/chat_room.html", context)

@login_required
def chat_list(request):
    """自分が参加しているチャットルーム一覧 + 未読数"""
    me = get_current_profile(request)

    # 新しいルーム順に並べる（あとで先に見つけたものだけ採用する）
    rooms = ChatRoom.objects.filter(
        Q(user1=me) | Q(user2=me)
    ).order_by("-created_at")

    room_infos_dict = {}  # key: partner.id, value: room_info

    for room in rooms:
        # 相手プロフィールを先に決める
        partner = room.user2 if room.user1_id == me.id else room.user1

        # すでにこの相手とのルームを追加済みならスキップ
        if partner.id in room_infos_dict:
            continue

        # 最新メッセージ
        latest = (
            Message.objects.filter(room=room).order_by("-created_at").first()
        )

        # 既読状態を取得（なければ2000年を既読時刻として作成）
        read_state, _ = ChatReadState.objects.get_or_create(
            user=me,
            room=room,
            defaults={
                "last_read_at": datetime(2000, 1, 1, tzinfo=dt_timezone.utc),
            },
        )

        # 未読数カウント（自分以外のメッセージだけ）
        unread_count = 0
        if latest and latest.created_at > read_state.last_read_at:
            unread_count = (
                Message.objects.filter(
                    room=room,
                    created_at__gt=read_state.last_read_at,
                )
                .exclude(sender=me)
                .count()
            )

        room_infos_dict[partner.id] = {
            "room": room,
            "partner": partner,
            "latest_message": latest,
            "unread_count": unread_count,
        }

    # dict → list に変換（表示順は created_at 降順のまま）
    room_infos = list(room_infos_dict.values())

    context = {
        "me": me,
        "room_infos": room_infos,
        "rooms": rooms,          # もしテンプレでまだ使ってるなら残してOK
        "current_tab": "chat",
    }
    return render(request, "matching/chat_list.html", context)



@login_required
def block_user(request, pk):
    me = get_current_profile(request)
    target = get_object_or_404(UserProfile, pk=pk)

    if me != target:
        Block.objects.get_or_create(blocker=me, blocked=target)

    # チャットルームがあれば削除してもOK（任意）
    ChatRoom.objects.filter(
        Q(user1=me, user2=target) | Q(user1=target, user2=me)
    ).delete()

    messages.info(request, "ユーザーをブロックしました。")
    return redirect("profile_list")


@login_required
def unblock_user(request, pk):
    me = get_current_profile(request)
    target = get_object_or_404(UserProfile, pk=pk)

    Block.objects.filter(blocker=me, blocked=target).delete()

    messages.info(request, "ブロックを解除しました。")
    return redirect("profile_detail", pk=pk)

from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required

@login_required
def board_list(request):
    posts = BoardPost.objects.select_related("author").order_by("-created_at")

    # GETパラメータ
    call_only = request.GET.get("call_only", "")
    gender = request.GET.get("gender", "")  # 'M' / 'F' / '' を想定

    # 通話募集だけ
    if call_only == "1":
        posts = posts.filter(is_call_invite=True)

    # 性別フィルタ（UserProfile.gender は 'M' / 'F' / 'O'）
    if gender in ["M", "F"]:
        posts = posts.filter(author__gender=gender)

    paginator = Paginator(posts, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "call_only": call_only,
        "gender": gender,
        "current_tab": "board",
    }
    return render(request, "matching/board_list.html", context)

@login_required
def board_create(request):
    """掲示板投稿を新規作成"""
    me = get_current_profile(request)

    if request.method == "POST":
        form = BoardPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = me
            post.save()
            return redirect("board_detail", pk=post.pk)
    else:
        form = BoardPostForm()

    return render(
        request,
        "matching/board_form.html",
        {
            "me": me,
            "form": form,
            "current_tab": "board",
        },
    )


@login_required
def board_detail(request, pk):
    """掲示板投稿の詳細"""
    me = get_current_profile(request)
    post = get_object_or_404(BoardPost, pk=pk)

    # ここで、「この人とチャットする」「プロフィールを見る」などの導線だけ用意
    return render(
        request,
        "matching/board_detail.html",
        {
            "me": me,
            "post": post,
            "current_tab": "board",
        },
    )

def ladies_free(request):
    return render(request, "matching/ladies_free.html", {"current_tab": "me"})

def terms(request):
    return render(request, "matching/terms.html")

def privacy(request):
    return render(request, "matching/privacy.html")

def rules(request):
    return render(request, "matching/rules.html")




def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "")
        email = request.POST.get("email", "")
        subject = request.POST.get("subject", "")
        message = request.POST.get("message", "")

        # ★ ここで DB に保存
        ContactMessage.objects.create(
            name=name,
            email=email,
            subject=subject,
            message=message,
        )

        full_message = f"【名前】{name}\n【メール】{email}\n\n---\n{message}"

        send_mail(
            subject=f"[お問い合わせ] {subject}",
            message=full_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_EMAIL],
        )

        return render(request, "matching/contact_done.html")

    return render(request, "matching/contact.html")

@login_required
def delete_account(request):
    """ログイン中ユーザーのアカウントを完全削除するビュー"""
    if request.method == "POST":
        user = request.user
        # 先にログアウト
        auth_logout(request)
        # これで User に紐づく UserProfile や Like, ChatRoom などが
        # on_delete=CASCADE でまとめて削除される
        user.delete()

        messages.success(request, "アカウントを削除しました。ご利用ありがとうございました。")
        return redirect("home")  # ← トップページなど、好きなURL名に変えてOK

    # GET のときは確認画面を表示
    return render(request, "matching/delete_account_confirm.html")

def logout_view(request):
    """シンプルなログアウトビュー（GET/POST どちらでもOK）"""
    logout(request)
    return redirect("home")   # 好きな遷移先に変えてOK