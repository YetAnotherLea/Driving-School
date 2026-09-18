"""Comptes et rendez-vous de démonstration (ceux affichés sur la page de connexion).

    python manage.py seed_demo            # crée ou remet en état, sans doublon
    python manage.py seed_demo --reset    # supprime aussi tout ce qui n'est pas de la démo

--reset garde les comptes de démo (mêmes identifiants, sessions intactes) et le
superuser ; les comptes et rendez-vous créés par les visiteurs disparaissent.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from polls.demo import COMPTES, RENDEZ_VOUS
from polls.models import HeuresFormation, RendezVous, UserProfile


def horaire(jours, heure):
    debut = timezone.localtime(timezone.now()).replace(
        hour=heure, minute=0, second=0, microsecond=0
    )
    return debut + timezone.timedelta(days=jours)


class Command(BaseCommand):
    help = "Crée ou remet en état les comptes et rendez-vous de démonstration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime les comptes et rendez-vous créés en dehors de la démo.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.bavard = options["verbosity"] > 0

        if options["reset"]:
            self.supprimer()

        # Rendez-vous d'abord : leurs leçons recréditent les soldes en partant.
        self.deplanifier()
        profils = {spec["username"]: self.compte(spec) for spec in COMPTES}
        self.planifier(profils)

        self.dire(
            self.style.SUCCESS(
                f"{len(profils)} comptes et {len(RENDEZ_VOUS)} rendez-vous de "
                "démonstration prêts."
            )
        )

    def dire(self, message):
        if self.bavard:
            self.stdout.write(message)

    def supprimer(self):
        noms = [spec["username"] for spec in COMPTES]
        # on_delete=RESTRICT : les rendez-vous partent avant les profils.
        RendezVous.objects.all().delete()
        supprimes, _ = User.objects.exclude(username__in=noms).exclude(is_superuser=True).delete()
        self.dire(f"{supprimes} objet(s) hors démonstration supprimé(s).")

    def compte(self, spec):
        user, _ = User.objects.get_or_create(username=spec["username"])
        user.first_name = spec["first_name"]
        user.last_name = spec["last_name"]
        user.email = spec["email"]
        user.is_staff = False
        user.is_superuser = False
        user.set_password(spec["password"])
        user.save()

        # Le signal a créé le profil en apprenant, on ajuste le rôle.
        profil, _ = UserProfile.objects.get_or_create(user=user)
        profil.role = spec["role"]
        profil.save()  # sync_heures_formation crée ou retire le solde d'heures

        user.user_permissions.clear()

        if "solde" in spec:
            HeuresFormation.objects.filter(apprenant=profil).update(
                solde=spec["solde"]
            )
        return profil

    def deplanifier(self):
        # Recréés à chaque passage pour rester relatifs à la date du jour.
        noms = [spec["username"] for spec in COMPTES]
        RendezVous.objects.filter(
            Q(apprenant__user__username__in=noms) | Q(moniteur__user__username__in=noms)
        ).delete()

    def planifier(self, profils):
        for apprenant, moniteur, jours, heure, statut, duree in RENDEZ_VOUS:
            rdv = RendezVous.objects.create(
                date=horaire(jours, heure),
                apprenant=profils[apprenant],
                moniteur=profils[moniteur],
                status=statut,
            )
            rdv.synchroniser_lecon(duree)
