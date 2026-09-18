"""Tests des droits CRUD par rôle.

Le sujet définit quatre rôles aux permissions distinctes : ces tests vérifient
que chaque rôle accède exactement à ce qui lui revient, et rien de plus.
"""

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from polls.models import HeuresFormation, Lecon, RendezVous, UserProfile


def creer_compte(username, role):
    """Le signal post_save crée le profil : on ne fait qu'ajuster son rôle."""
    user = User.objects.create_user(username, password="motdepasse123")
    profil = user.userprofile
    profil.role = role
    profil.save()
    return profil


class BaseRolesTest(TestCase):
    def setUp(self):
        self.apprenant = creer_compte("eleve", "apprenant")
        self.moniteur = creer_compte("moniteur", "moniteur")
        self.autre_moniteur = creer_compte("moniteur2", "moniteur")
        self.secretaire = creer_compte("secretaire", "secretaire")
        self.admin = creer_compte("patron", "admin")

        HeuresFormation.objects.filter(apprenant=self.apprenant).update(solde=10)
        self.rdv = RendezVous.objects.create(
            date=timezone.now() + timezone.timedelta(days=1),
            apprenant=self.apprenant,
            moniteur=self.moniteur,
            status="OK",
        )

    def connecte(self, profil):
        self.client.force_login(profil.user)


class AccesParRoleTest(BaseRolesTest):
    """Chaque rôle atteint ses pages et se voit refuser les autres."""

    def test_apprenant_voit_son_planning_pas_les_comptes(self):
        self.connecte(self.apprenant)
        self.assertEqual(self.client.get(reverse("rdv-list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("compte-list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("heures-list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("rdv-create")).status_code, 403)

    def test_chacun_consulte_sa_fiche_et_celles_de_ses_rendez_vous(self):
        self.connecte(self.apprenant)
        self.assertEqual(self.client.get(reverse("compte-detail", args=[self.apprenant.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("compte-detail", args=[self.moniteur.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("compte-detail", args=[self.autre_moniteur.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("compte-detail", args=[self.secretaire.pk])).status_code, 404)
        self.connecte(self.moniteur)
        self.assertEqual(self.client.get(reverse("compte-detail", args=[self.moniteur.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("compte-detail", args=[self.apprenant.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("compte-detail", args=[self.autre_moniteur.pk])).status_code, 404)

    def test_moniteur_gere_les_rdv_pas_les_comptes(self):
        self.connecte(self.moniteur)
        self.assertEqual(self.client.get(reverse("rdv-create")).status_code, 200)
        # Il consulte ses élèves, mais ne crée pas de compte.
        self.assertEqual(self.client.get(reverse("compte-list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("compte-create")).status_code, 403)

    def test_secretaire_et_admin_ont_les_pages_de_gestion(self):
        for profil in (self.secretaire, self.admin):
            self.connecte(profil)
            for nom in ("compte-list", "compte-create", "rdv-list", "rdv-create",
                        "heures-list", "heures-create"):
                self.assertEqual(
                    self.client.get(reverse(nom)).status_code, 200,
                    msg=f"{profil.role} devrait accéder à {nom}",
                )

    def test_anonyme_est_redirige_vers_la_connexion(self):
        reponse = self.client.get(reverse("rdv-list"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/login/", reponse["Location"])


class PerimetreDesDonneesTest(BaseRolesTest):
    """Les listes sont filtrées : on ne voit que son propre périmètre."""

    def test_apprenant_ne_voit_que_ses_rdv(self):
        autre = creer_compte("eleve2", "apprenant")
        RendezVous.objects.create(
            date=timezone.now() + timezone.timedelta(days=2),
            apprenant=autre, moniteur=self.moniteur, status="OK",
        )
        self.connecte(self.apprenant)
        rdvs = self.client.get(reverse("rdv-list")).context["object_list"]
        self.assertEqual([r.pk for r in rdvs], [self.rdv.pk])

    def test_moniteur_ne_voit_que_ses_eleves(self):
        creer_compte("eleve_sans_rdv", "apprenant")
        self.connecte(self.moniteur)
        comptes = self.client.get(reverse("compte-list")).context["object_list"]
        self.assertEqual([p.pk for p in comptes], [self.apprenant.pk])


class GestionDesComptesTest(BaseRolesTest):
    """Création, modification et suppression des comptes."""

    def donnees_compte(self, username, role, avec_mdp=True):
        donnees = {
            "username": username,
            "first_name": "Prenom",
            "last_name": "Nom",
            "email": f"{username}@exemple.fr",
            "role": role,
        }
        if avec_mdp:
            donnees["password"] = "motdepasse123"
        return donnees

    def test_secretaire_cree_un_apprenant_avec_son_solde(self):
        self.connecte(self.secretaire)
        reponse = self.client.post(
            reverse("compte-create"), self.donnees_compte("nouvel_eleve", "apprenant")
        )
        self.assertEqual(reponse.status_code, 302)
        profil = UserProfile.objects.get(user__username="nouvel_eleve")
        self.assertEqual(profil.role, "apprenant")
        # Un seul profil, malgré le signal de création automatique.
        self.assertEqual(UserProfile.objects.filter(user=profil.user).count(), 1)
        self.assertTrue(HeuresFormation.objects.filter(apprenant=profil).exists())

    def test_secretaire_ne_peut_pas_creer_de_secretaire(self):
        self.connecte(self.secretaire)
        reponse = self.client.post(
            reverse("compte-create"), self.donnees_compte("taupe", "secretaire")
        )
        # Le rôle n'est pas proposé : le formulaire est rejeté.
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(User.objects.filter(username="taupe").exists())

    def test_admin_peut_creer_une_secretaire(self):
        self.connecte(self.admin)
        reponse = self.client.post(
            reverse("compte-create"), self.donnees_compte("nouvelle_secretaire", "secretaire")
        )
        self.assertEqual(reponse.status_code, 302)
        profil = UserProfile.objects.get(user__username="nouvelle_secretaire")
        self.assertEqual(profil.role, "secretaire")

    def test_secretaire_ne_peut_pas_modifier_une_secretaire(self):
        autre = creer_compte("collegue", "secretaire")
        self.connecte(self.secretaire)
        self.assertEqual(
            self.client.get(reverse("compte-update", args=[autre.pk])).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("compte-delete", args=[autre.pk])).status_code, 403
        )

    def test_changer_de_role_synchronise_le_solde_dheures(self):
        self.connecte(self.admin)
        sans_rdv = creer_compte("mutant", "apprenant")
        self.assertTrue(HeuresFormation.objects.filter(apprenant=sans_rdv).exists())

        reponse = self.client.post(
            reverse("compte-update", args=[sans_rdv.pk]),
            self.donnees_compte("mutant", "moniteur", avec_mdp=False),
        )
        self.assertEqual(reponse.status_code, 302)
        sans_rdv.refresh_from_db()
        self.assertEqual(sans_rdv.role, "moniteur")
        # Plus de solde orphelin une fois le rôle changé.
        self.assertFalse(HeuresFormation.objects.filter(apprenant=sans_rdv).exists())

    def test_suppression_dun_compte_sans_rdv(self):
        cible = creer_compte("a_supprimer", "apprenant")
        self.connecte(self.secretaire)
        reponse = self.client.post(reverse("compte-delete", args=[cible.pk]))
        self.assertEqual(reponse.status_code, 302)
        self.assertFalse(User.objects.filter(username="a_supprimer").exists())
        self.assertFalse(UserProfile.objects.filter(pk=cible.pk).exists())

    def test_suppression_dun_compte_avec_rdv_est_expliquee(self):
        """RendezVous est en on_delete=RESTRICT : message clair, pas de 500."""
        self.connecte(self.secretaire)
        reponse = self.client.post(reverse("compte-delete", args=[self.apprenant.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("erreur_suppression", reponse.context)
        self.assertTrue(User.objects.filter(pk=self.apprenant.user.pk).exists())


class GestionDesRendezVousTest(BaseRolesTest):
    def donnees_rdv(self, moniteur):
        return {
            "date": "31/12/2026 14:30",
            "apprenant": self.apprenant.pk,
            "moniteur": moniteur.pk,
            "status": "OK",
            "duree": 1,
        }

    def test_secretaire_cree_modifie_supprime(self):
        self.connecte(self.secretaire)
        self.assertEqual(
            self.client.post(reverse("rdv-create"), self.donnees_rdv(self.moniteur)).status_code,
            302,
        )
        self.assertEqual(RendezVous.objects.count(), 2)

        self.client.post(
            reverse("rdv-update", args=[self.rdv.pk]), self.donnees_rdv(self.autre_moniteur)
        )
        self.rdv.refresh_from_db()
        self.assertEqual(self.rdv.moniteur, self.autre_moniteur)

        self.client.post(reverse("rdv-delete", args=[self.rdv.pk]))
        self.assertFalse(RendezVous.objects.filter(pk=self.rdv.pk).exists())

    def test_moniteur_ne_touche_pas_au_rdv_dun_collegue(self):
        self.connecte(self.autre_moniteur)
        self.assertEqual(
            self.client.get(reverse("rdv-update", args=[self.rdv.pk])).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("rdv-delete", args=[self.rdv.pk])).status_code, 403
        )

    def test_moniteur_reste_assigne_a_ses_propres_rdv(self):
        """Même en désignant un collègue, le moniteur reste titulaire."""
        self.connecte(self.moniteur)
        self.client.post(reverse("rdv-create"), self.donnees_rdv(self.autre_moniteur))
        cree = RendezVous.objects.exclude(pk=self.rdv.pk).get()
        self.assertEqual(cree.moniteur, self.moniteur)

    def test_apprenant_ne_peut_pas_creer_de_rdv(self):
        self.connecte(self.apprenant)
        self.assertEqual(
            self.client.post(reverse("rdv-create"), self.donnees_rdv(self.moniteur)).status_code,
            403,
        )


class HeuresFormationTest(BaseRolesTest):
    def test_secretaire_credite_des_heures(self):
        self.connecte(self.secretaire)
        reponse = self.client.post(
            reverse("heures-create"), {"apprenant": self.apprenant.pk, "heures": 5}
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(HeuresFormation.objects.get(apprenant=self.apprenant).solde, 15)

    def test_apprenant_consulte_son_solde_pas_celui_des_autres(self):
        autre = creer_compte("eleve3", "apprenant")
        self.connecte(self.apprenant)
        mien = HeuresFormation.objects.get(apprenant=self.apprenant)
        sien = HeuresFormation.objects.get(apprenant=autre)
        self.assertEqual(self.client.get(reverse("heures-detail", args=[mien.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("heures-detail", args=[sien.pk])).status_code, 404)


class SeedDemoTest(TestCase):
    """Les mots de passe de démo sont publics : leurs droits doivent rester minimes."""

    def setUp(self):
        call_command("seed_demo", verbosity=0)

    def test_aucun_superuser_cree(self):
        self.assertFalse(User.objects.filter(is_superuser=True).exists())

    def test_aucun_compte_de_demo_natteint_le_back_office(self):
        self.assertFalse(User.objects.filter(is_staff=True).exists())
        self.assertFalse(User.objects.filter(user_permissions__isnull=False).exists())

    def test_les_quatre_roles_sont_representes(self):
        roles = set(UserProfile.objects.values_list("role", flat=True))
        self.assertEqual(roles, {"apprenant", "moniteur", "secretaire", "admin"})

    def test_relancer_la_commande_ne_duplique_rien(self):
        call_command("seed_demo", verbosity=0)
        self.assertEqual(User.objects.count(), 6)
        self.assertEqual(RendezVous.objects.count(), 6)

    def test_reset_efface_les_creations_des_visiteurs_pas_la_demo(self):
        User.objects.create_superuser("patron", password="motdepasse123")
        visiteur = creer_compte("visiteur", "apprenant")
        jane_avant = User.objects.get(username="Jane_Apprenant").pk
        call_command("seed_demo", "--reset", verbosity=0)
        self.assertFalse(User.objects.filter(username="visiteur").exists())
        self.assertTrue(User.objects.filter(username="patron").exists())
        self.assertEqual(User.objects.get(username="Jane_Apprenant").pk, jane_avant)
        self.assertEqual(User.objects.count(), 7)

    def test_le_planning_reste_relatif_a_la_date_du_jour(self):
        self.assertTrue(RendezVous.objects.filter(date__gte=timezone.now()).exists())
        self.assertTrue(RendezVous.objects.filter(date__lt=timezone.now()).exists())


class BackOfficeTest(TestCase):
    def test_les_comptes_de_demo_sont_renvoyes_vers_la_connexion_admin(self):
        call_command("seed_demo", verbosity=0)
        for username, password in (("Claire_Admin", "admin123"), ("Bob_Secretaire", "secretaire123")):
            self.client.login(username=username, password=password)
            reponse = self.client.get("/admin/")
            self.assertEqual(reponse.status_code, 302)
            self.assertIn("/admin/login/", reponse["Location"])
            self.client.logout()


class ComptesDemoTest(TestCase):
    """Les comptes de démo sont publics : ils doivent rester intacts."""

    def setUp(self):
        call_command("seed_demo", verbosity=0)
        self.client.login(username="Claire_Admin", password="admin123")
        self.jane = UserProfile.objects.get(user__username="Jane_Apprenant")

    def test_un_compte_de_demo_ne_se_modifie_ni_ne_se_supprime(self):
        self.assertEqual(self.client.get(reverse("compte-update", args=[self.jane.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("compte-delete", args=[self.jane.pk])).status_code, 403)
        self.assertTrue(User.objects.filter(username="Jane_Apprenant").exists())

    def test_un_compte_cree_par_un_visiteur_reste_modifiable(self):
        visiteur = creer_compte("visiteur", "apprenant")
        self.assertEqual(self.client.get(reverse("compte-update", args=[visiteur.pk])).status_code, 200)

    def test_la_liste_ne_propose_pas_de_modifier_la_demo(self):
        html = self.client.get(reverse("compte-list")).content.decode()
        self.assertNotIn(reverse("compte-update", args=[self.jane.pk]), html)


class RolesGerablesTest(BaseRolesTest):
    """Seul l'admin peut créer des comptes secrétaire."""

    def test_admin_propose_les_trois_roles(self):
        self.connecte(self.admin)
        reponse = self.client.get(reverse("compte-create"))
        choix = [valeur for valeur, _ in reponse.context["form"].fields["role"].choices]
        self.assertEqual(choix, ["apprenant", "moniteur", "secretaire"])

    def test_secretaire_ne_propose_pas_le_role_secretaire(self):
        self.connecte(self.secretaire)
        reponse = self.client.get(reverse("compte-create"))
        choix = [valeur for valeur, _ in reponse.context["form"].fields["role"].choices]
        self.assertEqual(choix, ["apprenant", "moniteur"])


class LeconTest(BaseRolesTest):
    """Un rendez-vous confirmé réserve ses heures ; annulé ou supprimé, il les rend."""

    def setUp(self):
        super().setUp()
        self.heures = HeuresFormation.objects.get(apprenant=self.apprenant)
        self.heures.solde = 10
        self.heures.save()
        self.connecte(self.secretaire)

    def solde(self):
        self.heures.refresh_from_db()
        return self.heures.solde

    def donnees(self, statut, duree, apprenant=None):
        return {
            "date": "01/06/2030 10:00",
            "apprenant": (apprenant or self.apprenant).pk,
            "moniteur": self.moniteur.pk,
            "status": statut,
            "duree": duree,
        }

    def test_confirmer_reserve_les_heures(self):
        self.client.post(reverse("rdv-create"), self.donnees("OK", 2))
        self.assertEqual(self.solde(), 8)
        self.assertEqual(Lecon.objects.count(), 1)

    def test_en_attente_ne_reserve_rien(self):
        self.client.post(reverse("rdv-create"), self.donnees("WAIT", 2))
        self.assertEqual(self.solde(), 10)
        self.assertFalse(Lecon.objects.exists())

    def test_annuler_rend_les_heures(self):
        self.client.post(reverse("rdv-create"), self.donnees("OK", 2))
        rdv = RendezVous.objects.latest("pk")
        self.client.post(reverse("rdv-update", args=[rdv.pk]), self.donnees("DEL", 2))
        self.assertEqual(self.solde(), 10)
        self.assertFalse(Lecon.objects.filter(rdv=rdv).exists())

    def test_changer_la_duree_ajuste_le_solde(self):
        self.client.post(reverse("rdv-create"), self.donnees("OK", 2))
        rdv = RendezVous.objects.latest("pk")
        self.client.post(reverse("rdv-update", args=[rdv.pk]), self.donnees("OK", 3))
        self.assertEqual(self.solde(), 7)

    def test_supprimer_le_rdv_rend_les_heures(self):
        self.client.post(reverse("rdv-create"), self.donnees("OK", 2))
        rdv = RendezVous.objects.latest("pk")
        self.client.post(reverse("rdv-delete", args=[rdv.pk]))
        self.assertEqual(self.solde(), 10)

    def test_solde_insuffisant_refuse_la_confirmation(self):
        reponse = self.client.post(reverse("rdv-create"), self.donnees("OK", 4))
        self.heures.solde = 3
        self.heures.save()
        reponse = self.client.post(reverse("rdv-create"), self.donnees("OK", 4))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Solde insuffisant", reponse.context["form"].errors["duree"][0])
        self.assertEqual(self.solde(), 3)

    def test_modifier_sans_changer_la_duree_ne_redebite_pas(self):
        self.client.post(reverse("rdv-create"), self.donnees("OK", 2))
        rdv = RendezVous.objects.latest("pk")
        # Solde à 0 : les 2 h déjà réservées par ce rdv restent utilisables.
        self.heures.solde = 0
        self.heures.save()
        reponse = self.client.post(reverse("rdv-update", args=[rdv.pk]), self.donnees("OK", 2))
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(self.solde(), 0)

    def test_changer_d_apprenant_deplace_la_reservation(self):
        autre = creer_compte("eleve2", "apprenant")
        HeuresFormation.objects.filter(apprenant=autre).update(solde=5)
        self.client.post(reverse("rdv-create"), self.donnees("OK", 2))
        rdv = RendezVous.objects.latest("pk")
        self.client.post(reverse("rdv-update", args=[rdv.pk]), self.donnees("OK", 2, apprenant=autre))
        self.assertEqual(self.solde(), 10)
        self.assertEqual(HeuresFormation.objects.get(apprenant=autre).solde, 3)

    def test_le_formulaire_reprend_la_duree_existante(self):
        self.client.post(reverse("rdv-create"), self.donnees("OK", 3))
        rdv = RendezVous.objects.latest("pk")
        reponse = self.client.get(reverse("rdv-update", args=[rdv.pk]))
        self.assertEqual(reponse.context["form"].fields["duree"].initial, 3)


class NonIndexationTest(TestCase):
    def test_robots_txt_interdit_tout(self):
        reponse = self.client.get("/robots.txt")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Disallow: /", reponse.content.decode())

    def test_toutes_les_reponses_portent_x_robots_tag(self):
        for url in ("/", "/login/", "/intranet/", "/admin/login/", "/nexistepas/"):
            self.assertEqual(self.client.get(url)["X-Robots-Tag"], "noindex, nofollow", url)
