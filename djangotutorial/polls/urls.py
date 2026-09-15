from django.urls import path

from polls.views import (
    AccueilView,
    CompteCreateView,
    CompteDeleteView,
    CompteDetailView,
    CompteListView,
    CompteUpdateView,
    HeuresFormationCreateView,
    HeuresFormationDeleteView,
    HeuresFormationDetailView,
    HeuresFormationListView,
    HeuresFormationUpdateView,
    RendezVousCreateView,
    RendezVousDeleteView,
    RendezVousDetailView,
    RendezVousListView,
    RendezVousUpdateView,
)

urlpatterns = [
    path("", AccueilView.as_view(), name="accueil"),

    # Comptes : la clé de l'URL est celle du UserProfile.
    path("utilisateur/", CompteListView.as_view(), name="compte-list"),
    path("utilisateur/nouveau/", CompteCreateView.as_view(), name="compte-create"),
    path("utilisateur/<int:pk>/", CompteDetailView.as_view(), name="compte-detail"),
    path("utilisateur/<int:pk>/modifier/", CompteUpdateView.as_view(), name="compte-update"),
    path("utilisateur/<int:pk>/supprimer/", CompteDeleteView.as_view(), name="compte-delete"),

    # Rendez-vous
    path("rendezvous/", RendezVousListView.as_view(), name="rdv-list"),
    path("rendezvous/nouveau/", RendezVousCreateView.as_view(), name="rdv-create"),
    path("rendezvous/<int:pk>/", RendezVousDetailView.as_view(), name="rdv-detail"),
    path("rendezvous/<int:pk>/modifier/", RendezVousUpdateView.as_view(), name="rdv-update"),
    path("rendezvous/<int:pk>/supprimer/", RendezVousDeleteView.as_view(), name="rdv-delete"),

    # Heures de formation
    path("heures/", HeuresFormationListView.as_view(), name="heures-list"),
    path("heures/nouveau/", HeuresFormationCreateView.as_view(), name="heures-create"),
    path("heures/<int:pk>/", HeuresFormationDetailView.as_view(), name="heures-detail"),
    path("heures/<int:pk>/modifier/", HeuresFormationUpdateView.as_view(), name="heures-update"),
    path("heures/<int:pk>/supprimer/", HeuresFormationDeleteView.as_view(), name="heures-delete"),
]
