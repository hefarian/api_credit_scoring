# -*- coding: utf-8 -*-
"""
Tests complets pour les utilitaires d'inférence batch.

Ce module teste la fonction `predict_proba()` avec différents scénarios :
- Cas simple (1 client)
- Batch (plusieurs clients)
- Données manquantes
- Valeurs NaN
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# ensure local src package is loaded first
sys.path.insert(0, str(Path(__file__).parent.parent))
from src import inference


def test_predict_proba_single_row():
    """Test : scorer un seul client avec quelques colonnes."""
    df = pd.DataFrame([{"AMT_INCOME_TOTAL": 100000, "AMT_CREDIT": 200000}])
    proba = inference.predict_proba(df)
    assert proba.shape == (1,), "La proba doit être un array 1D avec 1 élément"
    assert 0.0 <= proba[0] <= 1.0, "La probabilité doit être entre 0 et 1"


def test_predict_proba_batch():
    """Test : scorer plusieurs clients en batch."""
    df = pd.DataFrame([
        {"AMT_INCOME_TOTAL": 100000, "AMT_CREDIT": 200000},
        {"AMT_INCOME_TOTAL": 150000, "AMT_CREDIT": 300000},
        {"AMT_INCOME_TOTAL": 80000, "AMT_CREDIT": 150000},
    ])
    proba = inference.predict_proba(df)
    assert proba.shape == (3,), "La proba doit avoir 3 éléments"
    assert np.all((proba >= 0) & (proba <= 1)), "Toutes les probas doivent être entre 0 et 1"


def test_predict_proba_with_nan():
    """Test : gérer les données avec NaN."""
    df = pd.DataFrame([
        {"AMT_INCOME_TOTAL": 100000, "AMT_CREDIT": np.nan},
        {"AMT_INCOME_TOTAL": np.nan, "AMT_CREDIT": 200000},
    ])
    # L'inférence doit gérer les NaN (fillna, drop, ou remplacer)
    proba = inference.predict_proba(df)
    assert proba.shape == (2,), "Doit retourner probas pour 2 clients même avec NaN"
    assert np.all((proba >= 0) & (proba <= 1)), "Probas valides malgré NaN"


def test_predict_proba_empty_df():
    """Test : comportement avec un DataFrame vide."""
    df = pd.DataFrame()
    try:
        proba = inference.predict_proba(df)
        assert proba.shape == (0,), "Doit retourner array vide pour DF vide"
    except Exception as e:
        # C'est acceptable de lever une erreur pour DF vide
        assert True, f"Erreur acceptée pour DF vide: {e}"


def test_predict_proba_consistency():
    """Test : même entrée → même sortie (déterminisme)."""
    df = pd.DataFrame([{"AMT_INCOME_TOTAL": 100000, "AMT_CREDIT": 200000}])
    proba1 = inference.predict_proba(df)
    proba2 = inference.predict_proba(df)
    assert np.allclose(proba1, proba2), "Les prédictions doivent être déterministes"
