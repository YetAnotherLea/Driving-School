"""Peuple la base avec les comptes et les rendez-vous de démonstration.

Source unique des données publiques du site vitrine : les identifiants affichés
sur la page de connexion sortent d'ici. La commande est idempotente — la rejouer
remet mots de passe, rôles et permissions dans l'état attendu sans créer de
doublon.

    python manage.py seed_demo            # crée ou remet en état
    python manage.py seed_demo --reset    # supprime d'abord les comptes de démo

``--reset`` ne touche qu'aux comptes listés ci-dessous : le superuser et tout
compte créé à la main survivent, ce qui le distingue d'un ``flush``.
"""

from django.contrib.auth.models import Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from polls.models import HeuresFormation, RendezVous, UserProfile

# Consultation du back-office Django, accordée au seul compte « admin » : les
# correcteurs parcourent l'administration sans pouvoir rien modifier. Sans
# permission sur auth.User, la section « Utilisateurs » ne leur apparaît même pas.
LECTURE_SEULE = ("view_userprofile", "view_rendezvous", "view_heuresformation")

# Les quatre premiers comptes sont affichés sur la page de connexion ; les deux
# derniers existent pour que les listes ne soient pas triviales et pour rendre
# visible le cloisonnement entre deux moniteurs.
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

# (apprenant, moniteur, jours par rapport à aujourd'hui, heure, statut).
# Les dates sont relatives : un planning figé serait vide au bout de quelques mois.
RENDEZ_VOUS = [
    ("Jane_Apprenant", "John_Moniteur", -5, 11, "OK"),
    ("Alice_Apprenant", "Paul_Moniteur", -2, 9, "OK"),
    ("Jane_Apprenant", "John_Moniteur", 1, 10, "OK"),
    ("Alice_Apprenant", "Paul_Moniteur", 2, 9, "WAIT"),
    ("Jane_Apprenant", "Paul_Moniteur", 4, 16, "DEL"),
    ("Alice_Apprenant", "John_Moniteur", 7, 14, "WAIT"),
]


def horaire(jours, heure):
    """Date à J+`jours`, à l'heure pile, dans le fuseau du site."""
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

        profils = {spec["username"]: self.compte(spec) for spec in COMPTES}
        self.planifier(profils)

        self.dire(
            self.style.SUCCESS(
                f"{len(profils)} comptes et {len(RENDEZ_VOUS)} rendez-vous de "
                "démonstration prêts."
            )
        )

    def dire(self, message):
        """N'écrit qu'au-dessus de --verbosity 0, que la suite de tests utilise."""
        if self.bavard:
            self.stdout.write(message)

    def supprimer(self):
        noms = [spec["username"] for spec in COMPTES]
        profils = UserProfile.objects.filter(user__username__in=noms)
        # RendezVous.apprenant et .moniteur sont en on_delete=RESTRICT : les
        # rendez-vous doivent partir avant les profils qu'ils référencent.
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

        # La création du User déclenche create_user_profile, qui pose
        # « apprenant » par défaut : on ajuste le rôle juste après.
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
        """Résout les permissions par codename, en échouant si l'une manque.

        C'est l'intérêt d'une commande plutôt qu'une fixture JSON : un codename
        obsolète arrête le déploiement au lieu de créer silencieusement un compte
        sans droits.
        """
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

    def planifier(self, profils):
        concernes = list(profils.values())
        # On repart des mêmes rendez-vous à chaque exécution, pour que le
        # planning reste relatif à la date du jour.
        RendezVous.objects.filter(
            Q(apprenant__in=concernes) | Q(moniteur__in=concernes)
        ).delete()
        for apprenant, moniteur, jours, heure, statut in RENDEZ_VOUS:
            RendezVous.objects.create(
                date=horaire(jours, heure),
                apprenant=profils[apprenant],
                moniteur=profils[moniteur],
                status=statut,
            )
