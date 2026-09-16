from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist


class ProfileMixin:
    """Donne accès au UserProfile de l'utilisateur connecté sans jamais lever.

    Un User sans profil renvoie None au lieu de déclencher un
    RelatedObjectDoesNotExist, ce qui évite les erreurs 500 dans les vues.
    """

    @property
    def profile(self):
        if not hasattr(self, "_profile_cache"):
            self._profile_cache = None
            user = self.request.user
            if user.is_authenticated:
                try:
                    self._profile_cache = user.userprofile
                except ObjectDoesNotExist:
                    self._profile_cache = None
        return self._profile_cache

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profil"] = self.profile
        return context


class RoleRequiredMixin(ProfileMixin, LoginRequiredMixin, UserPassesTestMixin):
    """Restreint une vue aux rôles listés dans allowed_roles.

    LoginRequiredMixin passe avant UserPassesTestMixin : un visiteur anonyme est
    redirigé vers la page de connexion, un utilisateur connecté mais non autorisé
    reçoit un 403.
    """

    allowed_roles = ()

    def test_func(self):
        profile = self.profile
        return profile is not None and profile.role in self.allowed_roles
