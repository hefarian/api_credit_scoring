# Projet 08 - Scoring Credit : Pret a depenser

**Auteur :** Gregory CRESPIN  
**Date :** 06/03/2026  
**Version :** 2.0 (Production)

---

## Description du projet

Ce projet implemente l'infrastructure de **production** pour un outil de **scoring credit** destiné à la societe financiere "Pret a depenser". Le modele XGBoost predit la probabilite qu'un client rembourse son credit et permet de classifier les demandes en credit accorde ou refuse.

L'infrastructure inclut :
- **API REST** pour les predictions en temps reel
- **Monitoring** pour la detection de drift et l'alerte
- **Dashboard Streamlit** pour le suivi des performances
- **Orchestration Docker** pour le deploiement

## Arquitechture

```
PROJET08/
├── Dockerfile                   # Image Docker (dependances)
├── Dockerfile.api               # Image Docker pour l'API FastAPI
├── docker-compose.yml           # Orchestration (PostgreSQL, API, Streamlit)
├── .dockerignore                # Fichiers exclus du contexte Docker
├── data/                        # Donnees brutes et preparees
├── notebooks/
│   └── 05_deployment_and_monitoring.ipynb  # Dashboard de suivi production
├── src/                         # Modules Python
│   ├── api.py                   # API FastAPI pour les predictions
│   ├── inference.py             # Logique d'inference du modele
│   ├── monitoring.py            # Suivi des performances et drift
│   ├── data_loader.py           # Chargement des donnees
│   ├── preprocessing.py         # Preprocessing des donnees
│   ├── feature_engineering.py   # Feature engineering
│   └── metrics.py               # Metriques d'evaluation
├── utils/                       # Utilitaires
│   ├── business_cost.py         # Calcul du cout metier personnalise
│   └── feature_importance.py    # Analyse d'importance des features
├── models/                      # Modeles de production
│   ├── best_model_xgb.pkl       # Modele XGBoost retenu
│   └── optimal_threshold_xgb.json
├── tests/                       # Tests unitaires
├── README.md                    # Documentation
└── requirements.txt
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
- `.github/workflows/cd-remote.yml` : Déploiement SSH sur serveur distant



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

## 📊 Dashboards & Interfaces

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
