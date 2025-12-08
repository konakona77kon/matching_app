# matching/utils.py
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image

# 画像のリサイズ
def resize_image_if_needed(uploaded_file, max_size=(1280, 1280)):
    file_size_mb = uploaded_file.size / (1024 * 1024)
    max_mb = getattr(settings, "MAX_IMAGE_SIZE_MB", 5)

    if file_size_mb <= max_mb:
        return uploaded_file

    image = Image.open(uploaded_file)
    image = image.convert("RGB")
    image.thumbnail(max_size, Image.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    buffer.seek(0)
    return ContentFile(buffer.read(), name=uploaded_file.name)


# 動画サイズチェック
def validate_video_size(uploaded_file):
    max_mb = getattr(settings, "MAX_VIDEO_SIZE_MB", 30)
    file_mb = uploaded_file.size / 1024 / 1024
    return file_mb <= max_mb


# Content-Type / 拡張子チェック
def is_safe_file(uploaded_file):
    allowed_content_types = getattr(settings, "ALLOWED_CONTENT_TYPES", [])
    allowed_extensions = getattr(settings, "ALLOWED_EXTENSIONS", [])

    if uploaded_file.content_type not in allowed_content_types:
        return False

    name = uploaded_file.name.lower()
    if not any(name.endswith(ext) for ext in allowed_extensions):
        return False

    return True


# ファイル種別の簡易判定
def detect_file_type(uploaded_file):
    ct = uploaded_file.content_type

    if ct.startswith("image/"):
        return "image"
    elif ct.startswith("video/"):
        return "video"
    return "other"
