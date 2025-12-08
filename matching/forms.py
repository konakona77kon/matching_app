from django import forms
from .models import UserProfile, BoardPost  # ← BoardPost 追加
from .models import ContactMessage

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "nickname",
            "age_range",
            "area",
            "prefecture",
            "gender",
            "income",
            "job",
            "purpose",
            "bio",
            "avatar",
        ]


class BoardPostForm(forms.ModelForm):
    class Meta:
        model = BoardPost
        fields = ["title", "body", "image", "is_call_invite"]
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "タイトルを入力",
            }),
            "body": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "どんな人と話したいか、条件などを自由に書いてください。",
            }),
        }



class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile

        # UserProfile モデルに実際に存在する＆編集したいフィールドを全部列挙
        fields = [
            "nickname",
            "age_range",   # ← 年齢（1歳刻み）用
            "area",        # ← 「新宿・渋谷あたり」みたいなざっくりエリア
            "prefecture",  # ← 都道府県（セレクト）
            "gender",
            "purpose",     # ← 利用目的（友達/恋人など）
            "job",
            "income",
            "bio",
            "avatar",
        ]

        labels = {
            "nickname": "ニックネーム",
            "age_range": "年齢",
            "area": "居住エリア",
            "prefecture": "居住地（都道府県）",
            "gender": "性別",
            "purpose": "利用目的",
            "job": "職業",
            "income": "年収（万円）",
            "bio": "自己紹介（ひとこと）",
            "avatar": "プロフィール画像",
        }

        # この widgets はテンプレートで {{ form.xxx }} を使う場合に効く設定
        # 今は HTML を手書きしているので **必須ではない** けど、バリデーションには影響しません
        widgets = {
            "gender": forms.RadioSelect(),  # ラジオボタンにしたいとき用（今は使ってないなら消してもOK）
        }

class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "お名前（任意）"}),
            "email": forms.EmailInput(attrs={"placeholder": "返信してほしいメールアドレス"}),
            "subject": forms.TextInput(attrs={"placeholder": "件名"}),
            "message": forms.Textarea(attrs={"rows": 6, "placeholder": "お問い合わせ内容を入力してください"}),
        }