"""Comptes et rendez-vous de démonstration (ceux affichés sur la page de connexion).

    python manage.py seed_demo            # crée ou remet en état, sans doublon
    python manage.py seed_demo --reset    # supprime d'abord les comptes de démo

--reset ne touche pas au superuser ni aux comptes créés à la main.
"""

from django.contrib.auth.models import Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from polls.models import HeuresFormation, RendezVous, UserProfile

# Accès /admin/ en consultation seulement, pour le compte admin.
LECTURE_SEULE = ("view_userprofile", "view_rendezvous", "view_lecon", "view_heuresformation")

# Les quatre premiers sont affichés sur la page de connexion.
COMPTES = [
    {
        "username": "Jane_Apprenant",
        "password": "apprenant123",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "janedoe@apprenant.fr",
        "role": "apprenant",
        "solde": 12,
    },
    {
        "username": "John_Moniteur",
        "password": "moniteur123",
        "first_name": "John",
        "last_name": "Doe",
        "email": "johndoe@moniteur.fr",
        "role": "moniteur",
    },
    {
        "username": "Bob_Secretaire",
        "password": "secretaire123",
        "first_name": "Bob",
        "last_name": "Smith",
        "email": "bobsmith@secretaire.fr",
        "role": "secretaire",
    },
    {
        "username": "Claire_Admin",
        "password": "admin123",
        "first_name": "Claire",
        "last_name": "Lefèvre",
        "email": "claire@direction.fr",
        "role": "admin",
        "is_staff": True,
        "permissions": LECTURE_SEULE,
    },
    {
        "username": "Alice_Apprenant",
        "password": "apprenant123",
        "first_name": "Alice",
        "last_name": "Martin",
        "email": "alice@apprenant.fr",
        "role": "apprenant",
        "solde": 5,
    },
    {
        "username": "Paul_Moniteur",
        "password": "moniteur123",
        "first_name": "Paul",
        "last_name": "Dupont",
        "email": "paul@moniteur.fr",
        "role": "moniteur",
    },
]

# (apprenant, moniteur, J+n, heure, statut, durée) — relatif à aujourd'hui.
RENDEZ_VOUS = [
    ("Jane_Apprenant", "John_Moniteur", -5, 11, "OK", 2),
    ("Alice_Apprenant", "Paul_Moniteur", -2, 9, "OK", 1),
    ("Jane_Apprenant", "John_Moniteur", 1, 10, "OK", 1),
    ("Alice_Apprenant", "Paul_Moniteur", 2, 9, "WAIT", 2),
    ("Jane_Apprenant", "Paul_Moniteur", 4, 16, "DEL", 1),
    ("Alice_Apprenant", "John_Moniteur", 7, 14, "WAIT", 1),
]


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
            help="Supprime les comptes de démonstration avant de les recréer.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.bavard = options["verbosity"] > 0

        if options["reset"]:
            self.supprimer()

        # Les rendez-vous partent avant que les soldes soient posés : leurs
        # leçons rendent des heures en disparaissant.
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
        profils = UserProfile.objects.filter(user__username__in=noms)
        # on_delete=RESTRICT : les rendez-vous partent avant les profils.
        RendezVous.objects.filter(
            Q(apprenant__in=profils) | Q(moniteur__in=profils)
        ).delete()
        User.objects.filter(username__in=noms).delete()
        self.dire("Comptes de démonstration précédents supprimés.")

    def compte(self, spec):
        user, _ = User.objects.get_or_create(username=spec["username"])
        user.first_name = spec["first_name"]
        user.last_name = spec["last_name"]
        user.email = spec["email"]
        user.is_staff = spec.get("is_staff", False)
        user.is_superuser = False
        user.set_password(spec["password"])
        user.save()

        # Le signal a créé le profil en apprenant, on ajuste le rôle.
        profil, _ = UserProfile.objects.get_or_create(user=user)
        profil.role = spec["role"]
        profil.save()  # sync_heures_formation crée ou retire le solde d'heures

        user.user_permissions.set(self.permissions(spec.get("permissions", ())))

        if "solde" in spec:
            HeuresFormation.objects.filter(apprenant=profil).update(
                solde=spec["solde"]
            )
        return profil

    def permissions(self, codenames):
        if not codenames:
            return []
        trouvees = list(
            Permission.objects.filter(
                codename__in=codenames, content_type__app_label="polls"
            )
        )
        manquantes = set(codenames) - {perm.codename for perm in trouvees}
        if manquantes:
            raise CommandError(
                "Permissions introuvables : " + ", ".join(sorted(manquantes))
            )
        return trouvees

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
