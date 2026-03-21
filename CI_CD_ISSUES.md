# CI/CD Issues et Solutions

## ✅ Problèmes Résolus

### 1. "Modèle non chargé" (HTTP 500 dans test_api.py)

**Problème:** Les fichiers modèles (`best_model.pkl`, `scaler.pkl`, `encoder.pkl`) ne sont pas commitées dans le repository (trop volumineux). En CI/CD, l'API essayait de charger ces fichiers au démarrage et échouait silencieusement avec `model = None`.

**Solution Implémentée:**
- Ajouté fixture `mock_model()` dans [tests/conftest.py](tests/conftest.py) qui crée un mock de modèle sklearn
- Ajouté fixture autouse `patch_model_if_missing()` qui patche automatiquement `src.api.model` et `src.inference._model` avec le mock si les fichiers n'existent pas
- Mock model retourne **numpy array** `np.array([[0.25, 0.75]])` pour support du numpy indexing `[:, 1][0]`
- Cela résout:
  - `test_api.py::test_predict_success` - Status 500 → 200
  - `test_api.py::test_predict_invalid_feature` - Status 500 → 400
  - `test_inference.py` - 4 tests avec FileNotFoundError

**Fichiers affectés:**
- [tests/conftest.py](tests/conftest.py) - Ajout de fixtures mock + numpy array return
- [.github/workflows/ci.yml](.github/workflows/ci.yml) - Déjà compatible

---

### 2. "list indices must be integers or slices, not tuple" (HTTP 400 lors indexing)

**Problème observé en CI/CD:**
```
response text: {"detail":"erreur de prédiction: list indices must be integers or slices, not tuple"}
```

**Cause:** Le mock_model retournait une **liste Python** `[[0.25, 0.75]]` au lieu d'un **numpy array**. Quand le code API faisait `proba = model.predict_proba(df)[:, 1][0]`, la notation NumPy `[:, 1]` essayait d'indexer une liste Python avec un tuple, d'où l'erreur.

**Solution Implémentée:**
- Modifié fixture `mock_model()` pour retourner `np.array([[0.25, 0.75]])` au lieu de `[[0.25, 0.75]]`
- Ajouté `np.array([0])` pour `predict()` aussi
- Code API peut maintenant faire `array[:, 1]` qui fonctionne correctement

**Fichiers affectés:**
- [tests/conftest.py](tests/conftest.py) - Return numpy arrays from mock

---

### 3. Repository Size (mlruns/, logs/, htmlcov/ non ignorés)

**Problème:** Les dossiers générés par MLflow, tests, et couverture n'étaient pas ignorés, ce qui les commitait dans le repository.

**Solution Implémentée:**
- Ajout à [.gitignore](.gitignore):
  ```
  mlruns/              # MLflow runs
  logs/                # Application logs
  htmlcov/             # HTML coverage reports
  .coverage            # Coverage metadata
  ```
- Suppression des fichiers du tracking avec `git rm --cached mlruns/`

**Fichiers affectés:**
- [.gitignore](.gitignore)

---

### 4. Dépendance httpx Manquante

**Problème:** Le client API HTTP utilisé dans les tests (`httpx.Client`) n'était pas listé dans `requirements.txt`.

**Solution Implémentée:**
- Ajouté `httpx==0.25.2` à [requirements.txt](requirements.txt)

**Impact:** Tests API peuvent maintenant importer httpx correctement

---

### 5. PostgreSQL "UndefinedTable: api_logs" (erreur attendue en CI sans Docker)

**Erreur observée en CI/CD:**
```
ERROR    database:database.py:310 Erreur lors de l'enregistrement de la prédiction : 
(psycopg2.errors.UndefinedTable) relation "api_logs" does not exist
```

**Cause:** En CI/CD sans Docker Compose, il n'y a pas de base de données PostgreSQL, donc la table `api_logs` n'existe pas.

**Pourquoi ce n'est pas un problème:** 
- Le code gère gracieusement cette erreur:
  - `ensure_prediction_log_schema()` : log un WARNING mais continue
  - `log_prediction_to_db()` : catch l'exception, log l'erreur, retourne False
- L'enregistrement en BD est optionnel - le /predict endpoint retourne le score quand même
- Tests passent car la prédiction fonctionne indépendamment du DB

**Quand c'EN EST un problème:** 
- Tests `test_monitoring_pg.py` qui ont besoin de la table pour des statistiques
- Ces tests sont probablement skippés ou mockés aussi

**Fichiers affectés:**
- [src/database.py](src/database.py) - Gestion gracieuse des erreurs DB
- [src/api.py](src/api.py) - Chaque endpoint continue même si `log_prediction_to_db()` échoue

## ⚠️ Problèmes Potentiels Résidus

### 1. Incompatibilité coverage.types.Tracer

**Erreur observée en CI/CD:**
```
AttributeError: module 'coverage.types' has no attribute 'Tracer'
```

**Cause probable:** Version incompatible entre `pytest-cov==4.1.0` et `coverage==7.3.2`

**Solution Appliquée:** 
- Mis à jour à `coverage==7.4.4` dans [requirements.txt](requirements.txt)
- Cette version devrait être compatible avec pytest-cov 4.1.0

**Si le problème persiste:**
```bash
# Mettre à jour les deux packages ensemble
pip install --upgrade pytest-cov coverage
```

---

### 2. Tests Flaky: test_scale_features_minmax

**Symptôme:** Assertion échoue aléatoirement sur les valeurs de scaling

```python
assert (X_train_scaled >= 0).all().all()
```

**Cause probable:** 
- Données générées aléatoirement par `sample_train_data` fixture
- Edge case où toutes les valeurs d'une colonne sont identiques (division par zéro)

**Solution Appliquée:**
- Fixé seed aléatoire à `np.random.seed(42)` dans [tests/conftest.py](tests/conftest.py)
- Cela rend les tests déterministes

**Si le problème persiste:** Augmenter la diversité des données dans la fixture

---

### 3. Timezone Issues: test_monitoring_pg.py

**Symptôme:** 
```
AssertionError: assert 0 == 1
```

**Cause probable:**
- Problème de gestion des timezones naïves vs aware
- Fonction `get_local_now_naive()` ou `LOCAL_TZ` mal configurée

**Comment déboguer:**
```python
# Dans le test, vérifier:
print(logs_df['timestamp'].dtype)
print(logs_df['timestamp'].iloc[0])
print(monitoring_pg.get_local_now_naive())
```

**Fix potentiel:** Vérifier que `LOCAL_TZ` est défini dans [src/monitoring_pg.py](src/monitoring_pg.py)

---

## 📋 Checklist de Validation CI/CD

Avant chaque push vers `main`:

- [ ] `pytest -q` passe localement (179 tests)
- [ ] `pytest --cov=src tests/` génère rapport de couverture
- [ ] Aucun fichier modèle (`*.pkl`) n'est staged
- [ ] Aucun dossier build (`mlruns/`, `logs/`, `htmlcov/`) n'est staged
- [ ] Les secrets GitHub sont configurés (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PRIVATE_KEY`)

---

## 🔧 Notes de Configuration

### Seed Aléatoire

- **Lieu:** [tests/conftest.py](tests/conftest.py) ligne 18
- **Valeur:** `42`
- **Effet:** Rend tous les tests avec `np.random` déterministes

### Mock Modèle

- **Lieu:** [tests/conftest.py](tests/conftest.py)
- **Comportement:** Simule `predict_proba()` → retourne `[[0.25, 0.75]]`
- **Trigger:** S'active automatiquement si `models/best_model.pkl` n'existe pas

### Couverture

- **Commande:** `pytest --cov=src --cov-report=html tests/`
- **Sortie:** `htmlcov/index.html`
- **Entrée .gitignore:** `htmlcov/`, `.coverage`

---

## 🚀 Pour Tester Localement

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Lancer les tests
pytest -v

# 3. Générer couverture
pytest --cov=src --cov-report=html tests/

# 4. Vérifier status git
git status
git diff
```

---

**Date de dernière mise à jour:** 2026-03-21  
**Responsable:** dev team
