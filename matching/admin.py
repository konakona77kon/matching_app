# matching/admin.py
from django.contrib import admin
from .models import ContactMessage

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "user", "name", "email", "created_at")
    list_filter = ("created_at",)
    search_fields = ("subject", "name", "email", "message")
