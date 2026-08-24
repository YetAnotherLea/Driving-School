from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


#Liste des choix
ROLES_CHOICES = [
    ("apprenant", "Apprenant"),
    ("moniteur", "Moniteur"),
    ("secretaire", "Secrétaire"),
    ("admin", "Admin"),
]

LESSON_STATUS = {
    "WAIT": "En attente",
    "OK": "Confirmé",
    "DEL": "Annulé",
}


# Create your models here.   
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES_CHOICES, default="apprenant")

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    # --- Helpers de rôle (utilisables en vue et en template) ---

    @property
    def is_apprenant(self):
        return self.role == "apprenant"

    @property
    def is_moniteur(self):
        return self.role == "moniteur"

    @property
    def is_secretaire(self):
        return self.role == "secretaire"

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def peut_gerer_comptes(self):
        """Secrétaires et admins gèrent les comptes."""
        return self.role in ("secretaire", "admin")

    @property
    def peut_gerer_rdv(self):
        """Moniteurs, secrétaires et admins créent et modifient des rendez-vous."""
        return self.role in ("moniteur", "secretaire", "admin")

    @property
    def peut_gerer_heures(self):
        return self.role in ("secretaire", "admin")

    @property
    def roles_gerables(self):
        """Rôles que ce profil a le droit de créer, modifier ou supprimer.

        L'admin gère en plus les comptes secrétaire, conformément au sujet.
        """
        if self.role == "admin":
            return ["apprenant", "moniteur", "secretaire"]
        if self.role == "secretaire":
            return ["apprenant", "moniteur"]
        return []


class HeuresFormation(models.Model):
    apprenant = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    solde = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Heures de formations"
        verbose_name_plural = "Heures de formations"

    def __str__(self):
        return f"{self.apprenant.user.username} : {self.solde} ore"
  

class RendezVous(models.Model):
    date = models.DateTimeField()
    apprenant = models.ForeignKey(UserProfile, on_delete=models.RESTRICT, related_name="rdv_apprenant")
    moniteur = models.ForeignKey(UserProfile, on_delete=models.RESTRICT, related_name="rdv_moniteur")
    status = models.CharField(max_length=4, choices=LESSON_STATUS)

    class Meta:
        verbose_name = "Rendez-vous"
        verbose_name_plural = "Rendez-vous"

    def __str__(self):
        return str(self.date)

class Lecon(models.Model):
    rdv = models.OneToOneField(RendezVous, on_delete=models.CASCADE)
    duree = models.IntegerField()

    class Meta:
        verbose_name = "Leçon"
        verbose_name_plural = "Leçons"

    def __str__(self):
        return str(self.duree)

# Signals pentru automatizare
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Dacă e superuser, îi dăm rol de admin
        role = "admin" if instance.is_superuser else "apprenant"
        UserProfile.objects.create(user=instance, role=role)

@receiver(post_save, sender=UserProfile)
def sync_heures_formation(sender, instance, created, **kwargs):
    """Garde le solde d'heures aligné sur le rôle.

    Se déclenche à chaque save et non seulement à la création : un profil qui
    passe de moniteur à apprenant obtient son solde, et l'inverse ne laisse pas
    de HeuresFormation orpheline.
    """
    if instance.role == "apprenant":
        HeuresFormation.objects.get_or_create(apprenant=instance, defaults={"solde": 0})
    else:
        HeuresFormation.objects.filter(apprenant=instance).delete()


# --- AI QUIZ MODELS ---

class QuizQuestion(models.Model):
    DIFFICULTY_CHOICES = [
        ("EASY", "Facile"),
        ("MEDIUM", "Moyen"),
        ("HARD", "Difficile"),
    ]
    text = models.TextField(verbose_name="Întrebare")
    image = models.ImageField(upload_to="quiz_images/", null=True, blank=True)
    explanation = models.TextField(verbose_name="Explicație AI")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default="MEDIUM")
    
    class Meta:
        verbose_name = "Întrebare Quiz"
        verbose_name_plural = "Întrebări Quiz"

    def __str__(self):
        return self.text[:50]

class QuizChoice(models.Model):
    question = models.ForeignKey(QuizQuestion, related_name="choices", on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.question.text[:20]} - {self.text}"
  