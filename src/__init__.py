# -*- coding: utf-8 -*-
"""
Package initializer pour créer le namespace local 'src'.

EXPLICATION :
============
En Python, avoir un fichier __init__.py dans un répertoire signifie que 
ce répertoire est un "package" (paquet/module).

POURQUOI C'EST IMPORTANT :
1. Permet d'importer des modules depuis ce répertoire
   Exemple : 'from src.inference import predict_proba' fonctionne grâce à ce fichier
   
2. Évite les conflits de noms
   Il existe peut-être un package 'src' installé avec pip
   Ce fichier s'assure qu'on utilise notre propre 'src' local, pas celui du système

3. Organise le code
   Sans __init__.py, Python ne reconnaît pas ce dossier comme un package
   et on ne peut pas importer de modules depuis ce dossier

FICHIERS DU PACKAGE SRC :
- __init__.py (ce fichier) = initialise le package
- api.py = service API FastAPI pour les prédictions
- database.py = gestion de PostgreSQL (logs, archivage, etc.)
- preprocessing.py = normalisation des données (scaling)
- feature_engineering.py = création de nouvelles variables
- inference.py = chargement du modèle et prédictions
- monitoring.py = détection de dérive (data drift)
- monitoring_pg.py = monitoring avec base de données PostgreSQL
- metrics.py = calcul des métriques d'évaluation
- data_loader.py = chargement et fusion des fichiers de données

ARCHITECTURE :
===============
data (entrée) → preprocessing → feature_engineering → model → predictions (sortie)
                                                      ↓
                                                   logging
                                                   Database
                                                   Monitoring
"""

# Ce package initializer peut rester vide, mais le fichier doit exister
# pour que Python reconnaisse ce répertoire comme un package

