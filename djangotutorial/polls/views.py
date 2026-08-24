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
from polls.models import HeuresFormation, QuizQuestion, RendezVous, UserProfile

TOUS_LES_ROLES = ("apprenant", "moniteur", "secretaire", "admin")
GESTIONNAIRES = ("secretaire", "admin")
GESTION_RDV = ("moniteur", "secretaire", "admin")


# ── Quiz (accessible sans compte) ──

class QuizView(TemplateView):
    template_name = "polls/quiz.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Trimitem întrebările amestecate pentru a varia experiența
        questions = list(QuizQuestion.objects.prefetch_related("choices").all())
        import random
        random.shuffle(questions)
        context["questions"] = questions
        return context


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
        if role == "moniteur":
            return qs.filter(role="apprenant", rdv_apprenant__moniteur=self.profile).distinct()
        # Un apprenant ne consulte que sa propre fiche.
        return qs.filter(pk=self.profile.pk)


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
            "apprenant__user", "moniteur__user"
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


class RendezVousCreateView(RoleRequiredMixin, CreateView):
    model = RendezVous
    form_class = RendezVousForm
    template_name = "polls/rendezvous_form.html"
    success_url = reverse_lazy("rdv-list")
    allowed_roles = GESTION_RDV

    def form_valid(self, form):
        if self.profile.role == "moniteur":
            # Un moniteur ne planifie que pour lui-même.
            form.instance.moniteur = self.profile
        return super().form_valid(form)


class RendezVousUpdateView(RendezVousProprieteMixin, RoleRequiredMixin, UpdateView):
    model = RendezVous
    form_class = RendezVousForm
    template_name = "polls/rendezvous_form.html"
    success_url = reverse_lazy("rdv-list")
    allowed_roles = GESTION_RDV

    def form_valid(self, form):
        if self.profile.role == "moniteur":
            form.instance.moniteur = self.profile
        return super().form_valid(form)


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
