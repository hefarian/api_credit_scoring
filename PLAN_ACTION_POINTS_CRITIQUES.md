# 🔧 PLAN D'ACTION - 3 POINTS CRITIQUES

**Durée totale:** 1h 30 min  
**Priorité:** ⚠️ À corriger AVANT soutenance  

---

## 🎯 POINT 1: Encoder & Scaler Manquants (30 min)

### Problème
```python
# ACTUELLEMENT: Encodage hardcodé dans preprocessing.py
le_dict = {'a': 0, 'b': 1, 'c': 2}

# RISQUE: Si nouvelles valeurs en prod → Crash
# ABSENT: encoder.pkl et scaler.pkl
```

### Solution
**Étape 1:** Exporter les transformers après training (5 min)
```python
# Dans greg/03_entrainement2.ipynb (dernière cellule)
import pickle

# Sauvegarder encoder
with open('models/encoder.pkl', 'wb') as f:
    pickle.dump(le, f)  # le = LabelEncoder

# Sauvegarder scaler
with open('models/scaler.pkl', 'wb') as f:
    pickle.dump(scaler, f)  # scaler = StandardScaler
```

**Étape 2:** Charger au startup API (5 min)
```python
# Dans src/api.py
import pickle

@app.on_event("startup")
async def load_models():
    global encoder, scaler
    with open('models/encoder.pkl', 'rb') as f:
        encoder = pickle.load(f)
    with open('models/scaler.pkl', 'rb') as f:
        scaler = pickle.load(f)
```

**Étape 3:** Vérifier files existent (5 min)
```bash
# Dans les logs API
if not os.path.exists('models/encoder.pkl'):
    raise FileNotFoundError("Manquant: models/encoder.pkl")
```

**Étape 4:** Tests (15 min)
```python
# tests/test_model_artifacts.py
def test_encoder_loads():
    """Vérifier encoder.pkl accessible"""
    with open('models/encoder.pkl', 'rb') as f:
        encoder = pickle.load(f)
    assert encoder is not None
    assert hasattr(encoder, 'transform')

def test_scaler_loads():
    """Vérifier scaler.pkl accessible"""
    with open('models/scaler.pkl', 'rb') as f:
        scaler = pickle.load(f)
    assert scaler is not None
```

**✓ Succès:** Quand `http://localhost:8005/health` retourne OK

---

## 🔐 POINT 2: Rate Limiting (20 min)

### Problème
```python
# ACTUELLEMENT: Pas de limitation
@app.post("/predict")
async def predict(data: PredictionInput):
    return {"score": score}  # Accepte 1000 req/sec = DOS possible
```

### Solution
**Étape 1:** Installer SlowAPI (2 min)
```bash
pip install slowapi
# ou add to requirements.txt: slowapi==0.1.9
```

**Étape 2:** Intégrer rate limiting (5 min)
```python
# Dans src/api.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/predict")
@limiter.limit("100/minute")  # Max 100 requêtes/minute par IP
async def predict(
    request: Request,  # IMPORTANT: FastAPI inject automatiquement
    data: PredictionInput
):
    return {"score": score}

# Ajouter exception handler pour 429
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded: 100 requests per minute"}
    )
```

**Étape 3:** Paramètres à ajuster (3 min)
```python
# Selon votre charge:
# - /predict: 100/minute (endpoint principal)
# - /health: 1000/minute (monitoring)
# - /monitor: 1000/minute (dashboard)

# Pour entreprise réelle ajouter:
# - Whitelist IPs de confiance
# - Tiered limits (users vs API clients)
# - Metrics exportées (Prometheus format)
```

**Étape 4:** Tests (5 min)
```python
# tests/test_rate_limiting.py
def test_rate_limit_exceeded():
    """Vérifier 429 après dépassement"""
    # Lancer 101 requêtes
    for i in range(101):
        response = client.post("/predict", json=test_data)
    
    # 101e retourne 429
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]
```

**Étape 5:** Dashboard alertes (5 min - optionnel)
```python
# Dans dashboard_streamlit.py
st.metric("API Rate Limit Status", "Normal ✓", "100/min")
# Ajouter graphique des requests/min
```

**✓ Succès:** Quand 101e requête retourne 429 Too Many Requests

---

## 🧪 POINT 3: Tests Intégration API ↔ BD (40 min)

### Problème
```python
# ACTUELLEMENT: Tests API mock la BD
# ABSENT: Tests END-TO-END (requête → BD → réponse)
# RISQUE: Bugs ignorés (connexion BD, insertion fail, etc)
```

### Solution
**Étape 1:** Setup PostgreSQL pour tests (10 min)
```python
# tests/conftest.py (fixtures pytest partagées)
import pytest
import psycopg2
from sqlalchemy import create_engine

@pytest.fixture(scope="session")
def db_engine():
    """Connexion BD de test"""
    DATABASE_URL = "postgresql://user:pass@localhost:5435/test_db"
    engine = create_engine(DATABASE_URL)
    
    # Créer tables (utiliser db/init.sql)
    yield engine
    
    # Cleanup (supprimer tables)
    engine.dispose()

@pytest.fixture
def db_session(db_engine):
    """Session BD propre pour chaque test"""
    connection = db_engine.connect()
    transaction = connection.begin()
    
    yield connection
    
    transaction.rollback()  # Annuler changements test
    connection.close()
```

**Étape 2:** Créer fixture client API (5 min)
```python
# tests/conftest.py (suite)
from fastapi.testclient import TestClient

@pytest.fixture
def api_client():
    """Client FastAPI pour tests"""
    from src.api import app
    return TestClient(app)
```

**Étape 3:** Tests intégration (20 min)
```python
# tests/test_api_db_integration.py
import pytest

def test_predict_writes_to_db(api_client, db_session):
    """Test: Requête API → Enregistrement en BD"""
    
    # Préparer données
    test_input = {
        "client_id": 12345,
        "age": 35,
        "income": 50000,
        # ... autres features
    }
    
    # Faire requête API
    response = api_client.post("/predict", json=test_input)
    assert response.status_code == 200
    
    score = response.json()["score"]
    decision = response.json()["decision"]
    
    # Vérifier enregistrement en BD
    result = db_session.execute("""
        SELECT score, decision FROM predictions 
        WHERE client_id = 12345 
        ORDER BY created_at DESC LIMIT 1
    """)
    db_record = result.fetchone()
    
    assert db_record is not None
    assert db_record[0] == score  # BD a même score
    assert db_record[1] == decision  # BD a même décision


def test_predict_with_no_db_connection(api_client, monkeypatch):
    """Test: API graceful fail si BD down"""
    
    # Simuler BD down
    import src.monitoring
    def mock_log_broken(*args, **kwargs):
        raise Exception("PostgreSQL connection failed")
    
    monkeypatch.setattr(src.monitoring, "log_prediction", mock_log_broken)
    
    # Requête devrait retourner 500 ou 503
    response = api_client.post("/predict", json=test_data)
    assert response.status_code in [500, 503]
    assert "error" in response.json()


def test_db_query_performance():
    """Test: Requête BD < 100ms même avec 1M records"""
    # À faire après avoir 1M records
    pass


def test_concurrent_predictions(api_client, db_session):
    """Test: Pas race condition avec 10 requêtes parallèles"""
    from concurrent.futures import ThreadPoolExecutor
    
    def predict():
        return api_client.post("/predict", json=test_data)
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        responses = list(executor.map(lambda _: predict(), range(10)))
    
    # Vérifier 10 records en BD
    assert db_session.execute(
        "SELECT COUNT(*) FROM predictions WHERE created_at > now() - interval '1 minute'"
    ).scalar() == 10
```

**Étape 4:** Intégrer dans CI/CD (5 min)
```yaml
# .github/workflows/ci.yml (ajouter après lint-and-test)
- name: Integration tests
  run: |
    # Lancer PostgreSQL
    docker run -d -p 5435:5432 postgres:15-alpine
    sleep 5
    # Tests intégration
    pytest tests/test_api_db_integration.py -v
```

**Étape 5:** Monitor résultats (0 min)
```bash
# Exécuter localement
cd tests/
pytest test_api_db_integration.py -v --tb=short
```

**✓ Succès:** Quand tous les tests passent et CI/CD montre ✅ integration

---

## ⏱️ TIMELINE D'EXÉCUTION

```
T+0min: Démarrer
├─ T+5min: Exporter encoder/scaler (POINT 1.1)
├─ T+10min: Charger au startup (POINT 1.2)
├─ T+15min: Tests encoder (POINT 1.4)
├─ T+20min: Installer SlowAPI (POINT 2.1)
├─ T+25min: Rate limiting code (POINT 2.2)
├─ T+30min: Tests rate limit (POINT 2.4)
├─ T+35min: Setup BD tests (POINT 3.1)
├─ T+45min: Créer fixtures (POINT 3.2-3.3)
├─ T+55min: Tests intégration (POINT 3.3)
├─ T+60min: Vérifier CI/CD (POINT 3.4)
└─ T+90min: FINI ✅
```

---

## ✅ CHECKLIST DE VALIDATION

```
POINT 1 - Encoder/Scaler:
├─ [ ] models/encoder.pkl existe et charge sans erreur
├─ [ ] models/scaler.pkl existe et charge sans erreur
├─ [ ] API startup: logs montrent "Encoder loaded ✓"
├─ [ ] curl /health retourne 200 OK
├─ [ ] tests/test_model_artifacts.py passe (2 tests)

POINT 2 - Rate Limiting:
├─ [ ] pip show slowapi confirme install
├─ [ ] src/api.py a @limiter.limit decorator
├─ [ ] curl /predict × 101 → 101e retourne 429
├─ [ ] tests/test_rate_limiting.py passe
├─ [ ] GitHub Actions montre ✅ tous tests

POINT 3 - Tests Intégration:
├─ [ ] PostgreSQL accessible sur :5435 pour tests
├─ [ ] tests/test_api_db_integration.py passe (5+ tests)
├─ [ ] BD records créés après requête API
├─ [ ] .github/workflows/ci.yml intégration tests ajoutés
├─ [ ] GitHub Actions: lint + docker + integration tous ✅
```

---

## 🚀 COMMANDS RAPIDES

```bash
# Test everything
pytest tests/ -v

# Test spécifique
pytest tests/test_model_artifacts.py -v
pytest tests/test_rate_limiting.py -v
pytest tests/test_api_db_integration.py -v

# CI/CD local
docker run -d -p 5435:5432 postgres:15-alpine
sleep 5
pytest tests/ -v

# Cleanup
docker stop $(docker ps -q)
```

---

## 📞 SUPPORT

**Si erreur encoder:**
```
Error: [Errno 2] No such file or directory: 'models/encoder.pkl'
→ Vérifier: notebook training a bien pickle les objets
→ Lancer: python -c "import pickle; pickle.load(open('models/encoder.pkl', 'rb'))"
```

**Si erreur rate limit:**
```
Error: slowapi not found
→ Fix: pip install slowapi
→ Ou: add slowapi==0.1.9 to requirements.txt
```

**Si erreur BD tests:**
```
Error: PostgreSQL connection refused on 5435
→ Fix: docker run -d -p 5435:5432 postgres:15-alpine
→ Wait 5 seconds: sleep 5
```

---

## 💡 TIPS

1. **Commit après chaque point:** `git commit -m "feat: Add encoder export + load"`
2. **Test localement d'abord:** Avant de push et laisser CI/CD
3. **Vérifier logs:** `pytest tests/ -v -s` affiche print statements
4. **Doubler effort sur Point 3:** Tests intégration sont plus complexes
5. **Garder branche dev:** Faire sur branche `fix/critical-issues`, puis PR→main

---

*Durée estimée: 1h 30 min*  
*Difficulté: Intermédiaire*  
*Impact: 3 points critiques → 0, score Mission 93% → 98%*  
