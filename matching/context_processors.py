# matching/context_processors.py

from django.db.models import Q

from .models import UserProfile, ChatRoom, Message, Like


def notification_context(request):
    """
    どのテンプレートからでも使える通知フラグを返すコンテキストプロセッサ。
    base.html で使っている:
      - has_new_messages : 新着メッセージがあるか
      - has_new_likes    : 新着の「いいね」があるか
      - has_new_matches  : 新しく成立したマッチがあるか
    をここで用意する。
    """

    # 未ログインなら全部 False
    if not request.user.is_authenticated:
        return {
            "has_new_messages": False,
            "has_new_likes": False,
            "has_new_matches": False,
        }

    # 自分の UserProfile がなければ何も出さない
    try:
        me = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return {
            "has_new_messages": False,
            "has_new_likes": False,
            "has_new_matches": False,
        }

    # ==========================================================
    # 🔔 新着メッセージ判定
    # ==========================================================
    # 自分が参加しているチャットルーム
    rooms = ChatRoom.objects.filter(Q(user1=me) | Q(user2=me))

    if me.last_checked_messages:
        # 最後に見た時刻以降に、相手が送ったメッセージがあれば新着あり
        has_new_messages = Message.objects.filter(
            room__in=rooms,
            created_at__gt=me.last_checked_messages,
        ).exclude(sender=me).exists()
    else:
        # ★ 初回：とにかく「相手からのメッセージ」が1件でもあれば新着扱い
        has_new_messages = Message.objects.filter(
            room__in=rooms,
        ).exclude(sender=me).exists()

    # ==========================================================
    # 💗 新着いいね判定
    # ==========================================================
    # 自分が「いいね」した相手（いいね返し済みの相手を除くために使う）
    liked_ids = Like.objects.filter(
        from_user=me
    ).values_list("to_user_id", flat=True)

    if me.last_checked_likes:
        has_new_likes = Like.objects.filter(
            to_user=me,
            created_at__gt=me.last_checked_likes,
        ).exclude(from_user_id__in=liked_ids).exists()
    else:
        # ★ 初回：自分宛て & まだ自分からいいね返ししてない ＝ 新着扱い
        has_new_likes = Like.objects.filter(
            to_user=me,
        ).exclude(from_user_id__in=liked_ids).exists()

    # ==========================================================
    # ❤️‍🔥 新着マッチ判定（相互いいね）
    # ==========================================================
    # 自分→相手
    liked_ids_set = set(
        Like.objects.filter(from_user=me).values_list("to_user_id", flat=True)
    )
    # 相手→自分
    liked_me_ids_set = set(
        Like.objects.filter(to_user=me).values_list("from_user_id", flat=True)
    )

    mutual_ids = liked_ids_set & liked_me_ids_set

    if me.last_checked_matches:
        # 最後に「マッチ一覧」を確認してから成立した相互いいねがあるか
        has_new_matches = Like.objects.filter(
            from_user_id__in=mutual_ids,
            to_user=me,
            created_at__gt=me.last_checked_matches,
        ).exists()
    else:
        # ★ 初回：相互いいねが1組でもあれば「新着マッチあり」とみなす
        has_new_matches = Like.objects.filter(
            from_user_id__in=mutual_ids,
            to_user=me,
        ).exists()

    return {
        "has_new_messages": has_new_messages,
        "has_new_likes": has_new_likes,
        "has_new_matches": has_new_matches,
    }
