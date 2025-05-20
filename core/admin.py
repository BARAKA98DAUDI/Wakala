from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import CustomUser, Network, Wallet, Transaction, Refill


# ────────────────────────────────────────────────────────────────────
#  Custom‑user administration
# ────────────────────────────────────────────────────────────────────
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display  = ("username", "email", "role", "is_staff", "is_active")
    list_filter   = ("role", "is_staff", "is_active")
    search_fields = ("username", "email")
    ordering      = ("username",)

    # show “role” in the add / change forms
    fieldsets = UserAdmin.fieldsets + (
        (None, {"fields": ("role",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {"fields": ("role",)}),
    )


# ────────────────────────────────────────────────────────────────────
#  Network administration with logo preview
# ────────────────────────────────────────────────────────────────────
@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display  = ("name", "logo_thumb")
    search_fields = ("name",)

    readonly_fields = ("logo_thumb",)        # show preview inside the form

    def logo_thumb(self, obj):
        """Returns an <img> tag for the logo or a dash if none."""
        if obj.logo:
            return format_html(
                '<img src="{}" style="height:45px; border-radius:4px;">',
                obj.logo.url,
            )
        return "—"

    logo_thumb.short_description = "Logo"    # column / field title


# ────────────────────────────────────────────────────────────────────
#  Other models (no customisation needed right now)
# ────────────────────────────────────────────────────────────────────
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Wallet)
admin.site.register(Transaction)
admin.site.register(Refill)
