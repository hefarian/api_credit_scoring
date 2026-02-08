# Projet 06 - Scoring Credit : Pret a depenser

**Auteur :** Gregory CRESPIN  
**Date :** 30/01/2026  
**Version :** 1.0

---

## Description du projet

Ce projet consiste a developper un outil de **scoring credit** pour la societe financiere "Pret a depenser". L'objectif est de calculer la probabilite qu'un client rembourse son credit et de classifier les demandes en credit accorde ou refuse.

## Objectifs

1. **Construire et optimiser un modele de scoring** qui predit la probabilite de faillite d'un client
2. **Analyser l'importance des features** (globale et locale) pour la transparence du modele
3. **Mettre en oeuvre une approche MLOps** complete avec MLflow :
   - Tracking des experimentations
   - Interface web MLflow
   - Model registry
   - Model serving

## Structure du projet

```
PROJET06/
├── Dockerfile                   # Image Docker (Jupyter + dependances)
├── docker-compose.yml           # Orchestration (Jupyter, option MLflow)
├── .dockerignore                # Fichiers exclus du contexte Docker
├── DOCKER.md                    # Documentation lancement Docker
├── data/                        # Donnees brutes
├── notebooks/                   # Notebooks Jupyter
│   ├── 01_exploration.ipynb
│   ├── 02_preparation.ipynb
│   ├── 03_entrainement2.ipynb
│   └── 04_optimisation.ipynb
├── src/                         # Modules Python reutilisables
│   ├── data_loader.py           # Module pour charger et fusionner les donnees du projet Scoring Credit.
│   ├── preprocessing.py         # Module pour le preprocessing (normalisation) des donnees.
│   ├── feature_engineering.py   # Module pour le feature engineering (creation de nouvelles variables).
│   └── metrics.py               # Module pour les metriques d'evaluation des modeles.
├── utils/                       # Utilitaires
│   ├── business_cost.py         # Module pour calculer le cout metier personnalise.
│   └── feature_importance.py    # Module pour analyser l'importance des features (globale et locale).
├── models/                      # Modeles sauvegardes
├── mlruns/                      # Runs MLflow (genere automatiquement)
└── requirements.txt
```

## Installation

### Option 1 : Docker (recommandé)
```bash
docker-compose up --build
```
Puis ouvrir http://localhost:8888 (token : `greg2026`).

Pour lancer aussi MLflow UI : `docker-compose --profile mlflow up --build`

Voir [DOCKER.md](DOCKER.md) pour plus de details.

### Option 2 : Installation locale
1. Creer un environnement virtuel :
```bash
python -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate
```

2. Installer les dependances :
```bash
pip install -r requirements.txt
```

3. Lancer Jupyter :
```bash
jupyter notebook
```

## Donnees

Les donnees sont disponibles dans le dossier `data/` :
- `application_train.csv` / `application_test.csv` : Donnees principales
- `bureau.csv` / `bureau_balance.csv` : Donnees d'autres institutions
- `previous_application.csv` : Demandes precedentes
- `POS_CASH_balance.csv` : Historique POS/CASH
- `credit_card_balance.csv` : Historique cartes de credit
- `installments_payments.csv` : Historique de remboursements

## Fonctionnalites cles

### Gestion du desequilibre des classes
- Utilisation de `class_weight` ou SMOTE
- Metriques adaptees (AUC-ROC, Recall, F1-score)

### Cout metier personnalise
- Cout FN (faux negatif) = 10 x cout FP (faux positif)
- Optimisation du seuil de decision base sur le cout metier
- Score metier personnalise pour comparer les modeles

### MLOps avec MLflow
- Tracking automatique des experimentations
- Enregistrement des modeles dans le registry
- Interface web pour visualiser les runs
- Model serving pour la production

### Optimisation
- Optuna pour les hyperparametres
- Validation croisee stratifiee (StratifiedKFold)
- Optimisation du seuil de classification

## Etapes du projet

1. **Exploration des donnees** : Analyse des donnees brutes, valeurs manquantes, distributions
2. **Preparation des donnees** : Nettoyage, fusion, encodage, feature engineering
3. **Entrainement** : Test de plusieurs modeles avec validation croisee et MLflow
4. **Optimisation** : Hyperparametres et seuil metier optimaux

## References

- [Kaggle - Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk)
- Kernels Kaggle recommandes pour l'exploration et le feature engineering
