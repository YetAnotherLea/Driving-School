# Driving School — intranet d'auto-école

Intranet de gestion pour une auto-école : comptes, planning des leçons et suivi des heures de
formation, avec quatre rôles aux droits distincts. Projet Django réalisé à Epitech, remis en état
et mis en ligne comme projet de portfolio.

**Démo : https://driving-school.leaballester.com**

## Fonctionnalités

- **Quatre rôles** — apprenant, moniteur, secrétaire, admin — chacun ne voit et ne fait que ce
  qui lui revient, vérifié côté serveur.
- **Comptes** : création, modification, suppression, avec des rôles attribuables limités selon
  qui agit (seul l'admin gère les comptes secrétaire).
- **Planning** : rendez-vous entre un apprenant et un moniteur, avec statut (en attente,
  confirmé, annulé). Un moniteur ne gère que ses propres créneaux.
- **Heures de formation** : solde par apprenant, crédité par le secrétariat. Un rendez-vous
  confirmé réserve sa durée sur le solde ; annulé ou supprimé, il la rend.
- Interface en français, tableau de bord par rôle, 41 tests.

## Comptes de démonstration

Les identifiants sont affichés sur la page de connexion. Chaque rôle a son compte :

| Rôle | Identifiant | Mot de passe | Ce qu'il permet de tester |
|---|---|---|---|
| Apprenant | `Jane_Apprenant` | `apprenant123` | son planning, son solde, sa fiche |
| Moniteur | `John_Moniteur` | `moniteur123` | ses élèves, création et suivi de ses rendez-vous |
| Secrétaire | `Bob_Secretaire` | `secretaire123` | comptes apprenant/moniteur, heures, tous les rendez-vous |
| Admin | `Claire_Admin` | `admin123` | tout, y compris les comptes secrétaire |

Les comptes de démonstration ne peuvent pas être modifiés ni supprimés ; tout ce que les
visiteurs créent est effacé chaque nuit.

## Stack

Python 3.12 · Django 6.1 · SQLite · gunicorn · nginx

## Installation locale

```bash
git clone git@github.com:YetAnotherLea/Driving-School.git
cd Driving-School
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # DJANGO_DEBUG=1 suffit en local

cd app
python manage.py migrate
python manage.py seed_demo      # comptes et rendez-vous de démonstration
python manage.py runserver
```

Puis http://127.0.0.1:8000/ — les comptes de démonstration sont sur la page de connexion.

```bash
python manage.py test           # 41 tests
python manage.py seed_demo --reset   # remet la démo à zéro
```

Variables d'environnement : voir [`.env.example`](.env.example).

## Déploiement

Le site tourne sur un VPS derrière nginx, servi par gunicorn, en HTTPS (Let's Encrypt).
La configuration de production est entièrement lue dans l'environnement — clé secrète,
hôtes autorisés, chemin de la base — et `manage.py check --deploy` ne remonte aucun
avertissement.

## Pistes d'amélioration

- Historique des leçons effectuées, distinct des rendez-vous confirmés
- Notifications par e-mail à la confirmation ou l'annulation d'un rendez-vous
- Export du planning d'un moniteur
