from django import forms
from django.contrib.auth.models import User

from polls.models import (
    HeuresFormation,
    Lecon,
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
    duree = forms.IntegerField(
        min_value=1,
        max_value=4,
        initial=1,
        label="Durée (heures)",
        help_text="Réservée sur le solde de l'apprenant une fois le rendez-vous confirmé.",
    )

    class Meta:
        model = RendezVous
        fields = ["date", "apprenant", "moniteur", "status", "duree"]
        labels = {"status": "Statut"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["apprenant"].queryset = UserProfile.objects.filter(role="apprenant")
        self.fields["moniteur"].queryset = UserProfile.objects.filter(role="moniteur")
        if self.instance.pk:
            lecon = Lecon.objects.filter(rdv=self.instance).first()
            if lecon:
                self.fields["duree"].initial = lecon.duree

    def clean(self):
        donnees = super().clean()
        apprenant, duree = donnees.get("apprenant"), donnees.get("duree")
        if donnees.get("status") != "OK" or not apprenant or not duree:
            return donnees
        heures = HeuresFormation.objects.filter(apprenant=apprenant).first()
        disponible = heures.solde if heures else 0
        # Les heures déjà réservées par ce même rendez-vous restent utilisables.
        if self.instance.pk and self.instance.apprenant_id == apprenant.pk:
            lecon = Lecon.objects.filter(rdv=self.instance).first()
            disponible += lecon.duree if lecon else 0
        if duree > disponible:
            self.add_error(
                "duree",
                f"Solde insuffisant : {disponible} heure{'s' if disponible > 1 else ''} disponible{'s' if disponible > 1 else ''}.",
            )
        return donnees


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
