"""Comptes et rendez-vous de démonstration, ceux affichés sur la page de connexion."""

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


IDENTIFIANTS_DEMO = {compte["username"] for compte in COMPTES}
