from django.contrib import admin

from .models import HeuresFormation, Lecon, RendezVous, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "email")
    list_filter = ("role",)
    search_fields = ("user__username", "user__first_name", "user__last_name", "user__email")

    @admin.display(description="Adresse e-mail")
    def email(self, obj):
        return obj.user.email


@admin.register(HeuresFormation)
class HeuresFormationAdmin(admin.ModelAdmin):
    list_display = ("apprenant", "solde")
    search_fields = ("apprenant__user__username",)


@admin.register(RendezVous)
class RendezVousAdmin(admin.ModelAdmin):
    list_display = ("date", "apprenant", "moniteur", "status", "duree")
    list_filter = ("status", "moniteur")
    date_hierarchy = "date"
    search_fields = ("apprenant__user__username", "moniteur__user__username")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "apprenant__user", "moniteur__user", "lecon"
        )

    @admin.display(description="Durée")
    def duree(self, obj):
        lecon = getattr(obj, "lecon", None)
        return f"{lecon.duree} h" if lecon else "—"


@admin.register(Lecon)
class LeconAdmin(admin.ModelAdmin):
    list_display = ("rdv", "duree")
    search_fields = ("rdv__apprenant__user__username",)
