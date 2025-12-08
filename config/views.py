from django.shortcuts import render, redirect, get_object_or_404
from matching.models import UserProfile
from matching.forms import UserProfileForm



def demo(request):
    # トップページ用：Sakura のカードが出るテンプレートを表示
    return render(request, "matching/demo.html")

    
    
def profile_form(request):
    """プロフィール登録フォーム（新規作成）"""
    if request.method == "POST":
        form = UserProfileForm(request.POST)
        if form.is_valid():
            form.save()
            # 登録後は一覧ページへ
            return redirect("profile_list")
    else:
        form = UserProfileForm()

    return render(request, "matching/form.html", {"form": form})


def profile_list(request):
    """登録済みプロフィールの一覧"""
    profiles = UserProfile.objects.all().order_by("-id")
    return render(request, "matching/list.html", {"profiles": profiles})


def profile_detail(request, pk):
    """プロフィール詳細"""
    profile = get_object_or_404(UserProfile, pk=pk)
    return render(request, "matching/detail.html", {"profile": profile})


