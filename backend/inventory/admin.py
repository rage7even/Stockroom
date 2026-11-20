from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Staff


@admin.register(Staff)
class StaffAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Stockroom", {"fields": ("full_name", "role", "shop")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Stockroom", {"fields": ("full_name", "email", "role", "shop")}),
    )
    list_display = ["username", "full_name", "role", "is_active"]
