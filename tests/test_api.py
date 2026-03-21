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
import numpy as np

# Charger les données d'entrée pour créer un sample valide
# Fallback sur des données mock si le fichier n'existe pas (GitHub Actions)
_csv_path = Path(__file__).parent.parent / "data" / "application_train.csv"
if _csv_path.exists():
    _train = pd.read_csv(_csv_path)
    _sample = _train.drop(columns=["TARGET"]).iloc[0]
    _sample = _sample.where(pd.notnull(_sample), None)
    SAMPLE = {"data": _sample.to_dict()}
else:
    # Données mock pour CI/CD (GitHub Actions)
    SAMPLE = {
        "data": {
            "SK_ID_CURR": 100002,
            "CODE_GENDER": "M",
            "FLAG_OWN_CAR": "N",
            "FLAG_OWN_REALTY": "Y",
            "AMT_INCOME_TOTAL": 202500.0,
            "AMT_CREDIT": 406597.5,
            "AMT_ANNUITY": 24700.5,
            "AMT_GOODS_PRICE": 351000.0,
            "NAME_EDUCATION_TYPE": "Secondary / secondary special",
            "OCCUPATION_TYPE": "Laborers",
            "CNT_CHILDREN": 0,
            "CNT_FAM_MEMBERS": 1,
            "DAYS_BIRTH": -14229,
            "DAYS_EMPLOYED": -1000,
            "DAYS_REGISTRATION": -7292,
            "DAYS_ID_PUBLISH": -4380,
        }
    }



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
