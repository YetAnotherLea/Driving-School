from django import forms
from django.contrib.auth.models import User

from polls.models import (
    HeuresFormation,
    RendezVous,
    ROLES_CHOICES,
    UserProfile,
)


class RendezVousForm(forms.ModelForm):
    # Format jour/mois/année : correctif du bug de saisie de date.
    date = forms.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M", "%d/%m/%Y"],
        help_text="Format : JJ/MM/AAAA HH:MM",
    )

    class Meta:
        model = RendezVous
        fields = ["date", "apprenant", "moniteur", "status"]
        labels = {"status": "Statut"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["apprenant"].queryset = UserProfile.objects.filter(role="apprenant")
        self.fields["moniteur"].queryset = UserProfile.objects.filter(role="moniteur")


class HeuresFormationForm(forms.Form):
    """Créditer des heures à un apprenant (action, pas édition d'objet)."""

    apprenant = forms.ModelChoiceField(
        queryset=UserProfile.objects.filter(role="apprenant")
    )
    heures = forms.IntegerField(min_value=1, max_value=10)


class HeuresFormationEditForm(forms.ModelForm):
    """Correction directe d'un solde par une secrétaire ou un admin."""

    class Meta:
        model = HeuresFormation
        fields = ["solde"]
        labels = {"solde": "Solde d'heures"}


class CompteForm(forms.ModelForm):
    """Base des formulaires de compte : champs User + rôle du profil associé.

    Les choix de rôle sont limités à ce que le gestionnaire connecté a le droit
    d'attribuer (voir UserProfile.roles_gerables).
    """

    role = forms.ChoiceField(choices=ROLES_CHOICES, label="Rôle")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]
        labels = {
            "username": "Identifiant",
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Adresse e-mail",
        }

    def __init__(self, *args, gestionnaire=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.gestionnaire = gestionnaire
        autorises = gestionnaire.roles_gerables if gestionnaire else []
        self.fields["role"].choices = [
            (valeur, libelle) for valeur, libelle in ROLES_CHOICES if valeur in autorises
        ]
        if self.instance.pk:
            profil = UserProfile.objects.filter(user=self.instance).first()
            if profil:
                self.fields["role"].initial = profil.role


class CompteCreateForm(CompteForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Mot de passe",
        min_length=8,
    )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class CompteUpdateForm(CompteForm):
    """Édition d'un compte : mêmes champs, sans le mot de passe."""
