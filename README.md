# Projet 08 - Scoring Credit : Pret a depenser

**Auteur :** Gregory CRESPIN  
**Date :** 22/03/2026  
**Version :** 2.0 (Production)

---

## Description du projet

Ce projet implemente l'infrastructure de **production** pour un outil de **scoring credit** destiné à la societe financiere "Pret a depenser". Le modele XGBoost predit la probabilite qu'un client rembourse son credit et permet de classifier les demandes en credit accorde ou refuse.

L'infrastructure inclut :
- **API REST** pour les predictions en temps reel
- **Monitoring** pour la detection de drift et l'alerte
- **Dashboard Streamlit** pour le suivi des performances
- **Orchestration Docker** pour le deploiement

## Architecture

```
PROJET08/
├── .env                         # Variables d'environnement (actif)
├── .env.dev                     # Variables d'environnement DEV
├── .env.main                    # Variables d'environnement MAIN
├── .env.prod                    # Variables d'environnement PROD
├── .github/
│   └── workflows/
│       ├── ci.yml               # Pipeline CI (tests, linting, build)
│       ├── deploy-dev.yml       # Déploiement branche dev
│       └── deploy-main.yml      # Déploiement branche main
├── dashboard_streamlit.py       # Dashboard Streamlit (monitoring + prédiction)
├── docker-compose.yml           # Orchestration (PostgreSQL, API, Streamlit)
├── Dockerfile                   # Image Docker (dépendances de base)
├── Dockerfile.api               # Image Docker pour l'API FastAPI
├── Dockerfile.streamlit         # Image Docker pour Streamlit
├── .dockerignore                # Fichiers exclus du contexte Docker
├── requirements.txt             # Dépendances Python
├── data/                        # Données brutes et préparées
│   ├── application_train.csv    # Données principales d'entraînement
│   ├── application_test.csv     # Données principales de test
│   ├── bureau.csv               # Données d'autres institutions
│   ├── bureau_balance.csv       # Soldes bureau
│   ├── credit_card_balance.csv  # Soldes cartes de crédit
│   ├── installments_payments.csv# Paiements des versements
│   ├── POS_CASH_balance.csv     # Soldes POS
│   ├── previous_application.csv # Demandes précédentes
│   ├── HomeCredit_columns_description.csv
│   ├── X_train_prepared.csv     # Features préparées (train)
│   ├── X_test_prepared.csv      # Features préparées (test)
│   └── y_train_prepared.csv     # Labels d'entraînement
├── db/
│   └── init.sql                 # Script d'initialisation PostgreSQL
├── Documentation/               # Documentation projet
│   ├── CONFORMITE_MISSION.md    # Conformité avec la mission
│   ├── GUIDE_DEPLOIEMENT_VM.md  # Guide de déploiement sur VM
│   ├── API_DEPLOYMENT_GUIDE.md  # Guide de déploiement API
│   ├── CI_CD_ISSUES.md          # Problèmes CI/CD connus
│   ├── Mission.md               # Description de la mission
│   └── presentation_finale.md   # Présentation finale
├── models/                      # Modèles de production
│   ├── best_model.pkl           # Modèle sérialisé (générique)
│   ├── best_model_xgb.pkl       # Modèle XGBoost retenu
│   └── optimal_threshold_xgb.json # Seuil optimal
├── notebooks/
│   └── 05_deployment_and_monitoring.ipynb # Notebook déploiement & monitoring
├── samples/                     # Exemples de requêtes pour tests
│   ├── sample.json              # 10 profils exemples (chargés par Streamlit)
│   ├── data_sample.json         # Échantillon de données
│   ├── data_sample_men.json     # Échantillon hommes
│   ├── data_sample_women.json   # Échantillon femmes
│   └── SAMPLES.md               # Documentation des exemples
├── scripts/
│   └── deploy_local.sh          # Script de déploiement local
├── src/                         # Modules Python
│   ├── __init__.py
│   ├── api.py                   # API FastAPI pour les prédictions
│   ├── database.py              # Connexion et gestion PostgreSQL
│   ├── inference.py             # Logique d'inférence du modèle
│   ├── monitoring.py            # Suivi des performances et drift
│   ├── monitoring_pg.py         # Monitoring via PostgreSQL
│   ├── data_loader.py           # Chargement des données
│   ├── preprocessing.py         # Preprocessing des données
│   ├── feature_engineering.py   # Feature engineering
│   └── metrics.py               # Métriques d'évaluation
├── tests/                       # Tests unitaires (pytest)
│   ├── conftest.py              # Fixtures de test partagées
│   ├── test_api.py              # Tests API
│   ├── test_data_loader.py      # Tests chargement données
│   ├── test_feature_engineering.py
│   ├── test_feature_engineering_advanced.py
│   ├── test_feature_importance.py
│   ├── test_feature_importance_simplified.py
│   ├── test_inference.py
│   ├── test_inference_advanced.py
│   ├── test_metrics.py
│   ├── test_metrics_advanced.py
│   ├── test_monitoring_pg.py
│   ├── test_preprocessing.py
│   ├── test_preprocessing_advanced.py
│   └── test_utils.py
├── utils/                       # Utilitaires
│   ├── business_cost.py         # Calcul du coût métier personnalisé
│   └── feature_importance.py    # Analyse d'importance des features
├── deploy.bat / deploy.sh       # Scripts de déploiement
├── start.bat                    # Lancement rapide Windows
├── reinit.bat                   # Réinitialisation de l'environnement
├── run_tests.ps1                # Script de tests PowerShell
├── run_tests_with_coverage.py   # Tests avec couverture de code
└── README.md                    # Ce document
```

## Démarrage rapide

### Option 1 : Docker Complet (recommandé - Tous les services)

```bash
# Construire et lancer l'environnement complet
docker-compose up --build
```

✅ Vous aurez accès à **5 interfaces** :

| URL | Service | Description | Port |
|-----|---------|-------------|------|
| **http://localhost:8005** | 🌐 **FastAPI** | API REST - Documentation Swagger | 8005 |
| **http://localhost:8005/docs** | 📖 Swagger UI | Tester les endpoints API | 8005 |
| **http://localhost:8505** | 📊 **Streamlit** | Dashboard monitoring en temps réel | 8505 |


### Option 2 : Services spécifiques uniquement

**Juste l'API** :
```bash
docker-compose up api
```

**API + Dashboard Streamlit** :
```bash
docker-compose up api streamlit
```

## CI/CD avec Déploiement Distant

Le projet inclut un pipeline **CI/CD automatisé** via GitHub Actions pour tester et déployer sur un serveur distant.

### Intégration Continue (CI)

À chaque push sur `main` ou `dev`, le workflow `.github/workflows/ci.yml` exécute:
- ✅ Tests unitaires (pytest 179 tests)
- ✅ Vérification du code (linting)
- ✅ Construction des images Docker

### Déploiement Continu (CD)

Après succès du CI, le workflow `.github/workflows/cd-remote.yml` déploie automatiquement:
- Connexion SSH au serveur distant
- Mise à jour du code via git pull
- Redémarrage des services Docker Compose

### Configuration pour Déploiement Distant

Ajouter les **GitHub Secrets** dans `Settings > Secrets and variables > Actions`:

| Secret | Exemple |
|--------|---------|
| `DEPLOY_HOST` | `192.168.1.100` ou `api.example.com` |
| `DEPLOY_USER` | `ubuntu` |
| `DEPLOY_PRIVATE_KEY` | Contenu de votre clé SSH privée |

### Fichiers impliqués

- `.github/workflows/ci.yml` : Tests et build Docker
- `.github/workflows/deploy-dev.yml` : Déploiement branche dev
- `.github/workflows/deploy-main.yml` : Déploiement branche main



### Option 3 : Installation locale

```bash
# 1. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'API
uvicorn src.api:app --reload --host 0.0.0.0 --port 8005

# 4. Dans d'autres terminaux :
# - Dashboard Streamlit
streamlit run dashboard_streamlit.py

# - Interface Gradio
python app_gradio.py

```


## �📊 Dashboards & Interfaces

### 1. Streamlit - Dashboard de Monitoring (Port 8505)

**Accédez à :** http://localhost:8505

Dashboard interactif pour :
- 📈 **KPIs en temps réel** : Total prédictions, scores moyens, distribution
- 🚨 **Détection de drift** : Alerte automatique si dérive détectée
- 📋 **Historique** : Visualiser et filtrer les prédictions passées
- 📉 **Graphiques interactifs** : Tendances, distributions, latence

**Fonctionnalités** :
- ✅ Auto-refresh chaque 5 secondes
- ✅ Téléchargement des données en CSV
- ✅ Multi-pages (Dashboard, Drift, Historique, À propos)
- ✅ Responsive design

**Fichier source :** [dashboard_streamlit.py](dashboard_streamlit.py)



**Fichier :** [notebooks/05_deployment_and_monitoring.ipynb](notebooks/05_deployment_and_monitoring.ipynb)

---

## API REST

L'API de scoring est contenue dans [src/api.py](src/api.py) et expose :

- `GET /health` : État de santé du service

- `GET /monitor?password=greg2026` : Dashboard HTML des statistiques et drift
- `POST /predict` : Prediction de scoring credit (single client)
  - Input: `{"data": {...}}` avec les features necessaires
  - Output: Score de probabilite de défaut
- `POST /multipredict` : Predictions batch (jusqu'à 50 clients)

### Documentation interactive

FastAPI fournit une documentation interactive **automatique** :

| URL | Description |
|-----|-------------|
| **`http://localhost:8005/docs`** | 📖 Swagger UI (interactif - tester les endpoints) |
| **`http://localhost:8005/redoc`** | 📋 ReDoc (documentation lisible) |

Vous pouvez **tester directement** les endpoints dans Swagger !

### Accès rapide aux dashboards

**Monitoring Dashboard (HTML)** :
```
http://localhost:8005/monitor?password=greg2026
```

### Exemples

**Command line - Health check :**
```bash
curl http://localhost:8005/health
```

**Command line - Prédiction single :**
```bash
curl -X POST "http://localhost:8005/predict" \
  -H "Content-Type: application/json" \
  -d '{"data": {"feature1": 100, "feature2": 25, ...}}'
```

**PowerShell - Prédiction single :**
```powershell
$payload = @{
    data = @{
        SK_ID_CURR = 100002
        AMT_INCOME_TOTAL = 300000
        # ... autres colonnes
    }
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8005/predict" `
  -Method POST `
  -ContentType "application/json" `
  -Body $payload
```

  "logs_size_kb": 156.23
}
```

### Localisation des archives

Les fichiers archivés sont stockés dans le dossier `logs/` aux côtés du fichier principal :

```
logs/
├── api.log                            # Log actif
├── api.log.dat_20260308_095630        # Archive 1
├── api.log.dat_20260308_100145        # Archive 2
└── api.log.dat_20260308_105200        # Archive 3
```

### Sécurité

- ✅ Endpoint protégé par mot de passe (`password=greg2026`)
- ✅ Pas de dépendance externe (pas d'email)
- ✅ Archives horodatées (impossible de perdre de données)

## Donnees

Les donnees de production sont dans `data/` :
- `X_train_prepared.csv` / `X_test_prepared.csv` : Features preparees et normalisees
- `y_train_prepared.csv` : Labels d'entrainement

Les donnees brutes initiales (archives dans `greg/`) incluaient :
- `application_train.csv` / `application_test.csv` : Donnees principales
- `bureau.csv` / `bureau_balance.csv` : Donnees d'autres institutions
- `previous_application.csv` : Demandes precedentes
- Autres sources (POS, cartes credit, remboursements...)

## Modele et Performance

### Modele retenu
- **XGBoost** - Meilleure performance globale
- **Seuil optimal** : Défini par optimisation du cout metier personnalisé
- **Metriques** : AUC-ROC, Recall, F1-score adapte au desequilibre des classes

### Suivi de la performance


- Monitoring automatique : Detection de drift des features et des predictions

## Tests

Tests unitaires dans `tests/` :
```bash
pytest -q
```

Tests automatiques lors de chaque deployment (CI/CD via GitHub Actions).
