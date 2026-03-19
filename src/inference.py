# -*- coding: utf-8 -*-
"""
Module d'inférence réutilisable - explications en français pour un débutant

Ce module fournit des fonctions utilitaires pour :
- charger paresseusement (lazy) les artefacts nécessaires à la prédiction
    (le modèle et éventuellement le scaler),
- appliquer le même prétraitement que celui utilisé lors de l'entraînement
    (feature engineering, encodage catégoriel si un artefact est disponible,
    mise à l'échelle),
- préparer les données pour la prédiction (alignement des colonnes attendues
    par le modèle) et retourner les probabilités.

Fonction principale : `predict_proba(df)`
- Entrée : un `pandas.DataFrame` où chaque ligne représente un exemple à
    scorer et les colonnes correspondent aux noms de features d'origine.
- Sortie : un `numpy.ndarray` contenant, pour chaque ligne, la probabilité de
    la classe positive (probabilité de défaut).

Notes pédagogiques :
- "Lazy loading" signifie que le modèle n'est chargé qu'à la première
    utilisation, ce qui accélère le démarrage du script si on n'appelle pas
    immédiatement la prédiction.
- Si vous avez encodé vos variables catégorielles pendant l'entraînement
    à l'aide d'un `ColumnTransformer` / `OneHotEncoder` / `Pipeline`, il est
    fortement recommandé de sauvegarder cet objet dans `models/encoder.pkl`.
    L'utilisation du même encodeur garantit que les noms de colonnes et les
    valeurs générées correspondent exactement à ce qui a été utilisé lors du
    fitting du modèle.

Auteur : généré et enrichi (commentaires en français)
Date : 2026-02
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.feature_engineering import create_ratio_features, create_interaction_features


_logger = logging.getLogger("inference")

MODEL_PATH = Path(__file__).parent.parent / "models" / "best_model.pkl"
SCALER_PATH = Path(__file__).parent.parent / "models" / "scaler.pkl"
ENCODER_PATH = Path(__file__).parent.parent / "models" / "encoder.pkl"

_model = None
_scaler = None


def _load_artifacts():
    global _model, _scaler
    if _model is None:
        try:
            _model = joblib.load(MODEL_PATH)
        except Exception as exc:
            _logger.error("impossible de charger le modèle: %s", exc)
            raise
    if _scaler is None and SCALER_PATH.exists():
        try:
            _scaler = joblib.load(SCALER_PATH)
        except Exception as exc:
            _logger.warning("scaler introuvable ou invalide: %s", exc)
            _scaler = None


def predict_proba(df: pd.DataFrame) -> np.ndarray:
    """Applique le prétraitement et renvoie les probabilités.

    Paramètres
    ----------
    df : pandas.DataFrame
        DataFrame contenant les features brutes. Chaque ligne est un exemple
        à scorer. Il est préférable que les colonnes correspondent aux noms
        utilisés à l'entraînement ; si des colonnes manquent, la fonction
        tente de compenser en ajoutant des colonnes à zéro (fallback).

    Retour
    ------
    numpy.ndarray
        Vecteur de forme (n_samples,) contenant la probabilité de la classe
        positive (ex: probabilité de défaut).
    """
    _load_artifacts()
    # Feature engineering (mêmes transformations que pour l'entraînement)
    df2 = create_ratio_features(df)
    df2 = create_interaction_features(df2)

    # --- Encodage catégoriel optionnel ---
    # Si un artefact `encoder.pkl` a été sauvegardé lors du preprocessing
    # d'entraînement (par exemple un OneHotEncoder, ColumnTransformer ou
    # une Pipeline), on le recharge ici et on l'applique aux nouvelles
    # observations afin de reproduire exactement les mêmes colonnes que
    # pendant l'entraînement. Si l'artefact n'existe pas, on continue en
    # mode dégradé (on tente quand même la prédiction en alignant les
    # colonnes numériques ensuite).
    try:
        if ENCODER_PATH.exists():
            encoder = joblib.load(ENCODER_PATH)
        else:
            encoder = None
    except Exception as exc:
        _logger.warning("Impossible de charger encoder.pkl : %s", exc)
        encoder = None

    if encoder is not None:
        try:
            # Supporter un dict {col: encoder} (ex: LabelEncoder par colonne)
            if isinstance(encoder, dict):
                encoded_parts = []
                for col, enc in encoder.items():
                    if col in df2.columns:
                        try:
                            ser = df2[col].astype(object).fillna("__MISSING__")
                            transformed = enc.transform(ser)
                            if getattr(transformed, 'ndim', 1) == 1:
                                s = pd.Series(transformed, index=df2.index, name=f"{col}_enc")
                                encoded_parts.append(s)
                            else:
                                cols = [f"{col}_enc_{i}" for i in range(transformed.shape[1])]
                                encoded_parts.append(pd.DataFrame(transformed, columns=cols, index=df2.index))
                        except Exception:
                            _logger.warning(f"échec encodage colonne {col}, on continue")
                if encoded_parts:
                    enc_df = pd.concat(encoded_parts, axis=1)
                    df2 = pd.concat([df2.drop(columns=[c for c in encoder.keys() if c in df2.columns], errors='ignore'), enc_df], axis=1)
            elif hasattr(encoder, "transform"):
                enc_array = encoder.transform(df2)
                try:
                    if hasattr(enc_array, "toarray"):
                        enc_array = enc_array.toarray()
                except Exception:
                    pass
                try:
                    out_cols = encoder.get_feature_names_out(df2.columns)
                except Exception:
                    out_cols = [f"enc_{i}" for i in range(getattr(enc_array, "shape", (0,))[1])]
                enc_df = pd.DataFrame(enc_array, columns=out_cols, index=df2.index)
                numeric_orig = df2.select_dtypes(include=["number"]).copy()
                df2 = pd.concat([numeric_orig, enc_df], axis=1)
        except Exception:
            _logger.warning("Échec de l'application de l'encodeur catégoriel, on continue sans encoder")

    # garder uniquement les colonnes numériques (XGBoost / sklearn attendent des types numériques)
    df2 = df2.select_dtypes(include=["number"]).copy()

    if _scaler is not None:
        df2 = pd.DataFrame(_scaler.transform(df2), columns=df2.columns)

    # Alignement avec les features attendues par le modèle :
    # On crée les colonnes manquantes et on réordonne les colonnes pour
    # correspondre exactement à l'ordre attendu par le booster. Cela évite
    # des erreurs lorsque le modèle attend une colonne qui n'est pas fournie
    # dans l'entrée.
    try:
        expected = _model.get_booster().feature_names or []
        missing = [c for c in expected if c not in df2.columns]
        if missing:
            zeros = pd.DataFrame(0, index=df2.index, columns=missing)
            df2 = pd.concat([df2, zeros], axis=1)
        if expected:
            df2 = df2[expected]
    except Exception:
        pass

    return _model.predict_proba(df2)[:, 1]
