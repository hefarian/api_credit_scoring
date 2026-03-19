# -*- coding: utf-8 -*-
"""
Tests unitaires pour le service FastAPI de scoring de crédit.

Ces tests vérifient que l'API fonctionne correctement :
1. L'endpoint /health retourne "ok"
2. L'endpoint /predict accepte les données et retourne un score valide
3. L'API rejette les données malformées avec erreur 400
4. L'API gère les types de données incorrects

Avantage des tests : on peut vérifier le code sans démarrer le serveur
Le TestClient de FastAPI simule les requêtes HTTP directement.
"""

import json
from pathlib import Path
import pandas as pd
import pytest

# Charger les données d'entrée pour créer un sample valide
_train = pd.read_csv(Path(__file__).parent.parent / "data" / "application_train.csv")
_sample = _train.drop(columns=["TARGET"]).iloc[0]
_sample = _sample.where(pd.notnull(_sample), None)
SAMPLE = {"data": _sample.to_dict()}



def test_health(api_client):
    """
    TEST 1 : Vérifier que l'endpoint /health fonctionne
    """
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_predict_success(api_client):
    """
    TEST 2 : Vérifier qu'une prédiction réussit et retourne un score valide
    """
    r = api_client.post("/predict", json=SAMPLE)
    
    if r.status_code != 200:
        print("payload sample keys", list(SAMPLE["data"].keys())[:10])
        print("response text:", r.text)
    
    assert r.status_code == 200
    body = r.json()
    assert "score" in body
    assert 0.0 <= body["score"] <= 1.0
    assert "model_version" in body
    assert "cpu_usage_pct" in body
    assert "gpu_usage_pct" in body
    assert "gpu_memory_mb" in body
    assert "compute_device" in body


def test_predict_bad_payload(api_client):
    """
    TEST 3 : Vérifier que l'API rejette les données malformées
    """
    # Test 3a : payload totalement vide
    r = api_client.post("/predict", json={})
    assert r.status_code == 422

    # Test 3b : "data" n'est pas un dict mais un string
    r = api_client.post("/predict", json={"data": "not a dict"})
    assert r.status_code == 422


def test_predict_invalid_feature(api_client):
    """
    TEST 4 : Vérifier que l'API gère les valeurs impossibles
    """
    malformed = {"data": {"AMT_INCOME_TOTAL": "hh"}}
    r = api_client.post("/predict", json=malformed)
    assert r.status_code == 400
