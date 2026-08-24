# Intranet Auto-École — Driving School Portal

Plateforme intranet moderne pour la gestion d'une auto-école, intégrant une expérience d'apprentissage assistée par IA.

## ✨ Nouvelles Fonctionnalités (Version Stefan)

- **AI Road Test** : Module interactif de 15 questions basé sur le Code de la Route français.
- **Explications IA** : Chaque réponse est accompagnée d'une explication pédagogique détaillée générée par l'IA.
- **Analyse de Performance** : Système de score intelligent avec 4 paliers de progression (Excellent, Bien, Moyen, Insuffisant).
- **Interface Premium** : Design "Glassmorphism" moderne avec banners interactifs et feedback instantané.
- **Automatisation** : Création automatique des profils utilisateurs et soldes d'heures via Django Signals.
- **Localisation** : Interface 100% en français professionnel.

## 🛠️ Prérequis
- Python 3.12+
- pip

## 🚀 Installation

### 1. Cloner le projet
```bash
git clone <url-du-repo>
cd W-DEV-300-MAR-3-1-devresp-1/djangotutorial
```

### 2. Environnement virtuel
```bash
python3 -m venv venv
source venv/bin/activate
pip install django
```

### 3. Migration & Données
```bash
python3 manage.py migrate
python3 manage.py loaddata sample
```

### 4. Lancer le serveur
```bash
python3 manage.py runserver
```

## 🎯 Accès
- **Page d'accueil** : [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Module AI Test** : [http://127.0.0.1:8000/polls/quiz/](http://127.0.0.1:8000/polls/quiz/)
- **Administration** : [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)