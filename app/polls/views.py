from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q, RestrictedError
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from polls.forms import (
    CompteCreateForm,
    CompteUpdateForm,
    HeuresFormationEditForm,
    HeuresFormationForm,
    RendezVousForm,
)
from polls.mixins import ProfileMixin, RoleRequiredMixin
from polls.models import HeuresFormation, Lecon, RendezVous, UserProfile

TOUS_LES_ROLES = ("apprenant", "moniteur", "secretaire", "admin")
GESTIONNAIRES = ("secretaire", "admin")
GESTION_RDV = ("moniteur", "secretaire", "admin")


# ── Accueil ──

class AccueilView(RoleRequiredMixin, TemplateView):
    template_name = "polls/home.html"
    allowed_roles = TOUS_LES_ROLES

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profil = self.profile
        now = timezone.now()
        if profil.role in GESTIONNAIRES:
            qs = RendezVous.objects.filter(date__gte=now)
        elif profil.role == "moniteur":
            qs = RendezVous.objects.filter(moniteur=profil, date__gte=now)
        else:
            qs = RendezVous.objects.filter(apprenant=profil, date__gte=now)
        ctx["prochains_rdv"] = qs.order_by("date")[:5]
        ctx["rdv_count"] = RendezVous.objects.count()
        ctx["user_count"] = UserProfile.objects.count()
        ctx["heures_count"] = HeuresFormation.objects.count()
        return ctx


# ── Comptes (User + UserProfile) ──

class CompteAccesMixin:
    """Vérifie que le gestionnaire a le droit d'agir sur le compte ciblé.

    L'URL porte la clé du UserProfile, mais les vues d'écriture manipulent le
    User : supprimer le seul profil laisserait un User orphelin, exactement le
    cas qui faisait planter les vues auparavant.
    """

    def get_profil_cible(self):
        profil = get_object_or_404(UserProfile, pk=self.kwargs["pk"])
        if profil.role not in self.profile.roles_gerables:
            raise PermissionDenied(
                "Vous n'avez pas le droit de gérer un compte de ce rôle."
            )
        return profil

    def get_object(self, queryset=None):
        return self.get_profil_cible().user


class GestionnaireFormMixin:
    """Transmet le profil connecté au formulaire pour borner les rôles proposés."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["gestionnaire"] = self.profile
        return kwargs


class CompteListView(RoleRequiredMixin, ListView):
    model = UserProfile
    allowed_roles = ("moniteur",) + GESTIONNAIRES

    def get_queryset(self):
        qs = UserProfile.objects.select_related("user").order_by("user__username")
        if self.profile.role == "moniteur":
            # Un moniteur ne voit que ses propres élèves.
            return qs.filter(role="apprenant", rdv_apprenant__moniteur=self.profile).distinct()
        return qs


class CompteDetailView(RoleRequiredMixin, DetailView):
    model = UserProfile
    allowed_roles = TOUS_LES_ROLES

    def get_queryset(self):
        qs = UserProfile.objects.select_related("user")
        role = self.profile.role
        if role in GESTIONNAIRES:
            return qs
        # Chacun voit sa fiche et celles des personnes avec qui il a rendez-vous.
        if role == "moniteur":
            lies = Q(role="apprenant", rdv_apprenant__moniteur=self.profile)
        else:
            lies = Q(role="moniteur", rdv_moniteur__apprenant=self.profile)
        return qs.filter(Q(pk=self.profile.pk) | lies).distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Sur une fiche, on ne liste que les rendez-vous que le visiteur a le droit de voir.
        rdvs = RendezVous.objects.select_related("apprenant__user", "moniteur__user").order_by("date")
        role = self.profile.role
        if role == "moniteur":
            rdvs = rdvs.filter(moniteur=self.profile)
        elif role == "apprenant":
            rdvs = rdvs.filter(apprenant=self.profile)
        ctx["rdv_apprenant"] = rdvs.filter(apprenant=self.object)
        ctx["rdv_moniteur"] = rdvs.filter(moniteur=self.object)
        return ctx


class CompteCreateView(GestionnaireFormMixin, RoleRequiredMixin, CreateView):
    model = User
    form_class = CompteCreateForm
    template_name = "polls/userprofile_form.html"
    success_url = reverse_lazy("compte-list")
    allowed_roles = GESTIONNAIRES

    def form_valid(self, form):
        response = super().form_valid(form)
        # Le signal create_user_profile a déjà créé le profil : on ajuste son
        # rôle plutôt que d'en créer un second (le OneToOne lèverait).
        profil = self.object.userprofile
        profil.role = form.cleaned_data["role"]
        profil.save()
        return response


class CompteUpdateView(CompteAccesMixin, GestionnaireFormMixin, RoleRequiredMixin, UpdateView):
    model = User
    form_class = CompteUpdateForm
    template_name = "polls/userprofile_form.html"
    success_url = reverse_lazy("compte-list")
    allowed_roles = GESTIONNAIRES

    def form_valid(self, form):
        response = super().form_valid(form)
        profil = self.object.userprofile
        profil.role = form.cleaned_data["role"]
        profil.save()
        return response


class CompteDeleteView(CompteAccesMixin, RoleRequiredMixin, DeleteView):
    model = User
    template_name = "polls/userprofile_confirm_delete.html"
    success_url = reverse_lazy("compte-list")
    allowed_roles = GESTIONNAIRES

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profil = UserProfile.objects.filter(user=self.object).first()
        ctx["profil_cible"] = profil
        ctx["nb_rdv"] = RendezVous.objects.filter(
            Q(apprenant=profil) | Q(moniteur=profil)
        ).count()
        return ctx

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except RestrictedError:
            # RendezVous.apprenant / .moniteur sont en on_delete=RESTRICT :
            # on explique au lieu de renvoyer une 500.
            ctx = self.get_context_data(object=self.object)
            ctx["erreur_suppression"] = (
                "Ce compte est rattaché à des rendez-vous. "
                "Supprimez-les d'abord pour pouvoir supprimer le compte."
            )
            return self.render_to_response(ctx)


# ── Rendez-vous ──

class RendezVousProprieteMixin:
    """Un moniteur n'agit que sur les rendez-vous qui lui sont attribués."""

    def get_object(self, queryset=None):
        rdv = super().get_object(queryset)
        if self.profile.role == "moniteur" and rdv.moniteur_id != self.profile.pk:
            raise PermissionDenied("Ce rendez-vous ne vous est pas attribué.")
        return rdv


class RendezVousListView(RoleRequiredMixin, ListView):
    model = RendezVous
    allowed_roles = TOUS_LES_ROLES

    def get_queryset(self):
        qs = RendezVous.objects.select_related(
            "apprenant__user", "moniteur__user", "lecon"
        ).order_by("date")
        role = self.profile.role
        if role in GESTIONNAIRES:
            return qs
        if role == "moniteur":
            return qs.filter(moniteur=self.profile)
        return qs.filter(apprenant=self.profile)


class RendezVousDetailView(RoleRequiredMixin, DetailView):
    model = RendezVous
    allowed_roles = TOUS_LES_ROLES

    def get_queryset(self):
        qs = RendezVous.objects.select_related("apprenant__user", "moniteur__user")
        role = self.profile.role
        if role in GESTIONNAIRES:
            return qs
        if role == "moniteur":
            return qs.filter(moniteur=self.profile)
        return qs.filter(apprenant=self.profile)


class RendezVousFormMixin:
    """Enregistre le rendez-vous puis aligne la leçon (et donc le solde) dessus."""

    def form_valid(self, form):
        if self.profile.role == "moniteur":
            # Un moniteur ne planifie que pour lui-même.
            form.instance.moniteur = self.profile
        if form.instance.pk and "apprenant" in form.changed_data:
            # Les heures repartent à l'ancien apprenant avant d'être prises au nouveau.
            Lecon.objects.filter(rdv=form.instance).delete()
        response = super().form_valid(form)
        self.object.synchroniser_lecon(form.cleaned_data["duree"])
        return response


class RendezVousCreateView(RendezVousFormMixin, RoleRequiredMixin, CreateView):
    model = RendezVous
    form_class = RendezVousForm
    template_name = "polls/rendezvous_form.html"
    success_url = reverse_lazy("rdv-list")
    allowed_roles = GESTION_RDV


class RendezVousUpdateView(RendezVousFormMixin, RendezVousProprieteMixin, RoleRequiredMixin, UpdateView):
    model = RendezVous
    form_class = RendezVousForm
    template_name = "polls/rendezvous_form.html"
    success_url = reverse_lazy("rdv-list")
    allowed_roles = GESTION_RDV


class RendezVousDeleteView(RendezVousProprieteMixin, RoleRequiredMixin, DeleteView):
    model = RendezVous
    template_name = "polls/rendezvous_confirm_delete.html"
    success_url = reverse_lazy("rdv-list")
    allowed_roles = GESTION_RDV


# ── Heures de formation ──

class HeuresFormationListView(RoleRequiredMixin, ListView):
    model = HeuresFormation
    allowed_roles = GESTIONNAIRES

    def get_queryset(self):
        return HeuresFormation.objects.select_related("apprenant__user")


class HeuresFormationDetailView(RoleRequiredMixin, DetailView):
    model = HeuresFormation
    allowed_roles = ("apprenant",) + GESTIONNAIRES

    def get_queryset(self):
        qs = HeuresFormation.objects.select_related("apprenant__user")
        if self.profile.role == "apprenant":
            return qs.filter(apprenant=self.profile)
        return qs


class HeuresFormationCreateView(RoleRequiredMixin, FormView):
    """Créditer des heures à un apprenant."""

    template_name = "polls/heures_form.html"
    form_class = HeuresFormationForm
    success_url = reverse_lazy("heures-list")
    allowed_roles = GESTIONNAIRES

    def form_valid(self, form):
        apprenant = form.cleaned_data["apprenant"]
        heures, _ = HeuresFormation.objects.get_or_create(
            apprenant=apprenant, defaults={"solde": 0}
        )
        heures.solde += form.cleaned_data["heures"]
        heures.save()
        return super().form_valid(form)


class HeuresFormationUpdateView(RoleRequiredMixin, UpdateView):
    model = HeuresFormation
    form_class = HeuresFormationEditForm
    template_name = "polls/heuresformation_form.html"
    success_url = reverse_lazy("heures-list")
    allowed_roles = GESTIONNAIRES


class HeuresFormationDeleteView(RoleRequiredMixin, DeleteView):
    model = HeuresFormation
    template_name = "polls/heuresformation_confirm_delete.html"
    success_url = reverse_lazy("heures-list")
    allowed_roles = GESTIONNAIRES
