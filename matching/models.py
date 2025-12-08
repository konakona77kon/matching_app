from django.db import models
from django.conf import settings
from django.utils import timezone
# matching/models.py
from django.contrib.auth import get_user_model

User = get_user_model()
class CallRequest(models.Model):
    MODE_CHOICES = (
        ("audio", "音声"),
        ("video", "ビデオ"),
    )

    room = models.ForeignKey("ChatRoom", on_delete=models.CASCADE)
    caller = models.ForeignKey("UserProfile", related_name="outgoing_calls", on_delete=models.CASCADE)
    callee = models.ForeignKey("UserProfile", related_name="incoming_calls", on_delete=models.CASCADE)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(null=True, blank=True)  # None=保留, True=受けた, False=拒否
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.caller} -> {self.callee} ({self.mode})"


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ("M", "男性"),
        ("F", "女性"),
        ("O", "その他"),
    ]

    PREF_CHOICES = [
        ("北海道", "北海道"),
        ("青森県", "青森県"),
        ("岩手県", "岩手県"),
        ("宮城県", "宮城県"),
        ("秋田県", "秋田県"),
        ("山形県", "山形県"),
        ("福島県", "福島県"),
        ("茨城県", "茨城県"),
        ("栃木県", "栃木県"),
        ("群馬県", "群馬県"),
        ("埼玉県", "埼玉県"),
        ("千葉県", "千葉県"),
        ("東京都", "東京都"),
        ("神奈川県", "神奈川県"),
        ("新潟県", "新潟県"),
        ("富山県", "富山県"),
        ("石川県", "石川県"),
        ("福井県", "福井県"),
        ("山梨県", "山梨県"),
        ("長野県", "長野県"),
        ("岐阜県", "岐阜県"),
        ("静岡県", "静岡県"),
        ("愛知県", "愛知県"),
        ("三重県", "三重県"),
        ("滋賀県", "滋賀県"),
        ("京都府", "京都府"),
        ("大阪府", "大阪府"),
        ("兵庫県", "兵庫県"),
        ("奈良県", "奈良県"),
        ("和歌山県", "和歌山県"),
        ("鳥取県", "鳥取県"),
        ("島根県", "島根県"),
        ("岡山県", "岡山県"),
        ("広島県", "広島県"),
        ("山口県", "山口県"),
        ("徳島県", "徳島県"),
        ("香川県", "香川県"),
        ("愛媛県", "愛媛県"),
        ("高知県", "高知県"),
        ("福岡県", "福岡県"),
        ("佐賀県", "佐賀県"),
        ("長崎県", "長崎県"),
        ("熊本県", "熊本県"),
        ("大分県", "大分県"),
        ("宮崎県", "宮崎県"),
        ("鹿児島県", "鹿児島県"),
        ("沖縄県", "沖縄県"),
    ]

    PURPOSE_CHOICES = [
        ("friend", "友達作り"),
        ("love", "恋人探し"),
        ("both", "友達も恋人も両方"),
        ("hobby", "趣味友達"),
        ("talk", "暇つぶし・話し相手"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        null=True,
        blank=True,
    )
    nickname = models.CharField(max_length=50)
    age_range = models.CharField(max_length=20, blank=True)
    area = models.CharField(max_length=50, blank=True)
    purpose = models.CharField(
        "利用目的",
        max_length=20,
        choices=PURPOSE_CHOICES,
        blank=True,
    )
    job = models.CharField(max_length=50, blank=True)        # 職業
    income = models.IntegerField(blank=True, null=True)      # 年収（数字で保存）
    prefecture = models.CharField(
        max_length=10,
        choices=PREF_CHOICES,
        blank=True,
        verbose_name="居住地",
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        null=True,
        verbose_name="性別",
    )
    bio = models.TextField(blank=True)  # ひとこと自己紹介

    # メインのプロフィール画像
    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True,
    )

    # 通知用の「最後に見た時刻」
    last_checked_messages = models.DateTimeField(null=True, blank=True)
    last_checked_likes = models.DateTimeField(null=True, blank=True)
    last_checked_matches = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        # user が None の可能性も一応考慮
        if self.nickname:
            return self.nickname
        if self.user:
            return self.user.username
        return "UserProfile"


class ProfilePhoto(models.Model):
    """
    プロフィールのサブ写真（複数枚）を管理するモデル。
    avatar が「メイン」、こちらは「追加ギャラリー」想定。
    """
    profile = models.ForeignKey(
        UserProfile,
        related_name="photos",
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to="profile_photos/")
    order = models.PositiveIntegerField(default=0)  # 並び順
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-uploaded_at"]

    def __str__(self):
        return f"Photo of {self.profile} (id={self.id})"


class Like(models.Model):
    from_user = models.ForeignKey(
        UserProfile,
        related_name="likes_sent",
        on_delete=models.CASCADE,
    )
    to_user = models.ForeignKey(
        UserProfile,
        related_name="likes_received",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("from_user", "to_user")

    def __str__(self):
        return f"{self.from_user} → {self.to_user}"


class ChatRoom(models.Model):
    user1 = models.ForeignKey(
        UserProfile,
        related_name="chatrooms_as_user1",
        on_delete=models.CASCADE,
    )
    user2 = models.ForeignKey(
        UserProfile,
        related_name="chatrooms_as_user2",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user1", "user2"],
                name="unique_chatroom_pair",
            )
        ]

    def __str__(self):
        return f"Room {self.pk}: {self.user1} & {self.user2}"



class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    sender = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    text = models.TextField(blank=True)

    image = models.ImageField(upload_to="chat_images/", blank=True, null=True)
    video = models.FileField(upload_to="chat_videos/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.created_at:%H:%M}] {self.sender}: {self.text[:20]}"


class ChatReadState(models.Model):
    """
    ユーザーごと・チャットルームごとの「最後に読んだ時刻」を持つモデル。
    """
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    last_read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "room")

    def __str__(self):
        return f"{self.user} @ {self.room} : {self.last_read_at}"

class Block(models.Model):
    blocker = models.ForeignKey(
        UserProfile, related_name="blocks_sent", on_delete=models.CASCADE
    )
    blocked = models.ForeignKey(
        UserProfile, related_name="blocks_received", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("blocker", "blocked")

    def __str__(self):
        return f"{self.blocker} blocks {self.blocked}"

class SearchCondition(models.Model):
    """
    ユーザーごとの「最後に使った検索条件」を保存しておくモデル。
    まずは 1人1レコードを自動更新する使い方にしておく。
    """
    owner = models.ForeignKey(
        UserProfile,
        related_name="search_conditions",
        on_delete=models.CASCADE,
    )

    # 並び順
    order = models.CharField(max_length=20, default="recommended")  # recommended / new / random

    # フィルタ条件
    age_filter = models.CharField(max_length=10, default="any")     # any / near
    prefecture = models.CharField(max_length=10, blank=True)        # 完全一致
    gender = models.CharField(max_length=1, blank=True, null=True)  # M / F / O
    income_min = models.IntegerField(null=True, blank=True)
    income_max = models.IntegerField(null=True, blank=True)
    purpose = models.CharField(max_length=100, blank=True)

    # いつ使われたか（自動更新）
    last_used_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SearchCondition({self.owner}, {self.order}, age={self.age_filter})"

class BoardPost(models.Model):
    """掲示板の投稿"""

    author = models.ForeignKey(
        "UserProfile",
        on_delete=models.CASCADE,
        related_name="board_posts",
    )
    title = models.CharField("タイトル", max_length=100)
    body = models.TextField("本文", blank=True)
    image = models.ImageField(
        "画像",
        upload_to="board_images/",
        blank=True,
        null=True,
    )
    is_call_invite = models.BooleanField(
        "通話相手を募集する",
        default=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} by {self.author.nickname}"

    

class ContactMessage(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="ユーザー",
    )
    name = models.CharField("お名前", max_length=50, blank=True)
    email = models.EmailField("メールアドレス", blank=True)
    subject = models.CharField("件名", max_length=100)
    message = models.TextField("お問い合わせ内容")
    created_at = models.DateTimeField("送信日時", auto_now_add=True)

    def __str__(self):
        # 管理画面での表示用
        if self.user:
            return f"{self.subject} ({self.user})"
        return f"{self.subject} ({self.email})"