# -*- coding: utf-8 -*-
"""
Fixtures pytest partagées entre tous les tests.

Ce fichier contient les données et configurations utilisées par plusieurs tests.
Les fixtures sont des objets qu'on peut réutiliser dans les tests.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Ajouter la racine du projet au path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fixer la seed aléatoire pour des tests déterministes
np.random.seed(42)


@pytest.fixture
def sample_train_data():
    """
    Fixture : données d'entraînement minimales pour tester.
    
    Retourne un DataFrame avec 10 lignes et 5 colonnes numériques.
    Élimine la complexité : pas besoin de charger les vrais gros fichiers CSV.
    """
    data = {
        'feature_1': np.random.randn(10),
        'feature_2': np.random.randn(10),
        'feature_3': np.random.randn(10),
        'feature_4': np.random.randn(10),
        'feature_5': np.random.randn(10),
    }
    df = pd.DataFrame(data)
    return df


@pytest.fixture
def sample_test_data():
    """Fixture : données de test minimales."""
    data = {
        'feature_1': np.random.randn(5),
        'feature_2': np.random.randn(5),
        'feature_3': np.random.randn(5),
        'feature_4': np.random.randn(5),
        'feature_5': np.random.randn(5),
    }
    df = pd.DataFrame(data)
    return df


@pytest.fixture
def sample_data_with_ratios():
    """
    Fixture : données avec colonnes pour tester le feature engineering
    (ratios, interactions).
    """
    data = {
        'AMT_INCOME_TOTAL': [100000, 150000, 200000, 80000, 120000],
        'AMT_CREDIT': [200000, 300000, 400000, 150000, 250000],
        'AMT_ANNUITY': [15000, 20000, 25000, 12000, 18000],
        'AMT_GOODS_PRICE': [200000, 300000, 400000, 150000, 250000],
        'DAYS_BIRTH': [-13297, -10950, -15200, -12000, -14500],
        'DAYS_EMPLOYED': [-762, -1500, -2000, -800, -1200],
    }
    df = pd.DataFrame(data)
    return df


@pytest.fixture
def sample_predictions():
    """
    Fixture : prédictions et vraies valeurs pour tester les métriques.
    
    Structure :
    - y_true : vraies labels (0 ou 1)
    - y_pred : prédictions binaires (0 ou 1)
    - y_proba : probabilités prédites (entre 0 et 1)
    """
    y_true = np.array([0, 1, 1, 0, 1, 0, 1, 1, 0, 0])
    y_pred = np.array([0, 1, 1, 0, 1, 1, 1, 1, 0, 0])  # 1 erreur (FP à index 5)
    y_proba = np.array([0.1, 0.9, 0.8, 0.2, 0.7, 0.6, 0.75, 0.85, 0.1, 0.15])
    
    return {
        'y_true': y_true,
        'y_pred': y_pred,
        'y_proba': y_proba
    }


@pytest.fixture
def sample_dataframe_with_nan():
    """Fixture : données avec valeurs manquantes (NaN) pour tester la robustesse."""
    data = {
        'col1': [1.0, 2.0, np.nan, 4.0, 5.0],
        'col2': [10.0, np.nan, 30.0, 40.0, 50.0],
        'col3': [100.0, 200.0, 300.0, 400.0, 500.0],
    }
    return pd.DataFrame(data)


@pytest.fixture
def mock_model():
    """
    Fixture: Mock du modèle pour les tests en CI/CD.
    
    Retourne un objet mock qui simule un modèle sklearn avec une méthode
    predict_proba() retournant des probabilités au format numpy array.
    """
    from unittest import mock
    
    mock_model = mock.MagicMock()
    # Simuler predict_proba pour retourner un numpy array [[prob_default, prob_no_default]]
    # Format: 2D array de shape (n_samples, 2) pour binary classification
    # Le premier appel retourne [[0.25, 0.75]], mais en numpy array pour support indexing
    mock_model.predict_proba.return_value = np.array([[0.25, 0.75]])
    mock_model.predict.return_value = np.array([0])
    return mock_model


@pytest.fixture(autouse=True)
def patch_model_if_missing(mock_model, monkeypatch):
    """
    Fixture autouse: Patch le modèle globalement si best_model.pkl n'existe pas.
    
    Cette fixture s'exécute avant chaque test et patche :
    - src.api.model
    - src.inference._model
    
    Cela résout les problèmes en CI/CD où les fichiers modèles ne sont pas disponibles.
    """
    model_path = Path(__file__).parent.parent / "models" / "best_model.pkl"
    
    if not model_path.exists():
        # Patcher src.api.model
        try:
            import src.api
            monkeypatch.setattr(src.api, "model", mock_model)
        except Exception:
            pass
        
        # Patcher src.inference._model
        try:
            import src.inference
            monkeypatch.setattr(src.inference, "_model", mock_model)
        except Exception:
            pass


@pytest.fixture
def api_client(mock_model, monkeypatch):
    """
    Fixture: Client HTTP pour tester l'API FastAPI.
    
    Contourne l'incompatibilité Starlette 0.27 + httpx 0.28 en utilisant
    httpx.Client avec un wrapper ASGI personnalisé.
    
    Patch également le modèle en CI/CD si best_model.pkl n'existe pas.
    """
    import httpx
    from pathlib import Path as PathlibPath
    
    # Vérifier si le modèle existe
    model_path = PathlibPath(__file__).parent.parent / "models" / "best_model.pkl"
    
    # Si le modèle n'existe pas (CI/CD), patcher src.api.model avec le mock
    if not model_path.exists():
        import src.api
        monkeypatch.setattr(src.api, "model", mock_model)
    
    from src.api import app
    
    # Créer un transport ASGI personnalisé
    class ASGITransport(httpx.BaseTransport):
        def __init__(self, asgi_app):
            self.asgi_app = asgi_app
        
        def handle_request(self, request):
            """Convertir requête httpx en appel ASGI"""
            import asyncio
            from starlette.datastructures import Headers
            
            # Préparer le scope ASGI
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": request.method,
                "scheme": request.url.scheme,
                "path": request.url.path or "/",
                "query_string": request.url.query.encode() if request.url.query else b"",
                "root_path": "",
                "headers": request.headers.raw,
                "server": (request.url.host or "testserver", request.url.port or 80),
                "client": ("testclient", 50000),
                "extensions": {},
            }
            
            # Préparer le body
            body_parts = []
            
            async def receive():
                if not body_parts:
                    body_parts.append(True)  # Marqueur
                    return {"type": "http.request", "body": request.content, "more_body": False}
                return {"type": "http.disconnect"}
            
            # Exécuter l'app ASGI et récupérer la réponse
            response_started = False
            status_code = 200
            response_headers = []
            body = []
            
            async def send(message):
                nonlocal response_started, status_code, response_headers
                if message["type"] == "http.response.start":
                    response_started = True
                    status_code = message["status"]
                    response_headers = message.get("headers", [])
                elif message["type"] == "http.response.body":
                    body.append(message.get("body", b""))
            
            # Exécuter
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.asgi_app(scope, receive, send))
            finally:
                loop.close()
            
            # Créer la réponse httpx
            return httpx.Response(
                status_code=status_code,
                headers=response_headers,
                content=b"".join(body),
                request=request,
            )
    
    # Créer le client httpx avec le transport ASGI personnalisé
    transport = ASGITransport(asgi_app=app)
    return httpx.Client(transport=transport, base_url="http://testserver")




@pytest.fixture
def sample_dataframe_edge_cases():
    """Fixture : données avec cas limites (zéros, valeurs très grandes, etc.)."""
    data = {
        'zeros': [0, 0, 0, 0, 0],
        'large_values': [1e10, 2e10, 3e10, 4e10, 5e10],
        'small_values': [1e-10, 2e-10, 3e-10, 4e-10, 5e-10],
        'mixed': [-1000, -10, 0, 10, 1000],
    }
    return pd.DataFrame(data)
