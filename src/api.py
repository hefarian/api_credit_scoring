# -*- coding: utf-8 -*-
"""
API de scoring (service de prédiction) - explication détaillée pour un débutant

Ce module expose un service HTTP (via FastAPI) permettant de demander la
probabilité de défaut d'un client à partir d'un ensemble de caractéristiques
(features). L'objectif est de fournir un point d'entrée simple et réutilisable
pour la production.

Principes importants (explication pas-à-pas) :
- Le modèle est chargé une seule fois au démarrage de l'application. Cela
    évite de recharger le fichier pickle à chaque requête (coût élevé en I/O
    et en temps).
- L'entrée attendue est un objet JSON de la forme `{"data": {"col1": val1, ...}}`.
    Les clés sont les noms des variables (features) et les valeurs leurs
    observations pour le client à scorer.
- Pour garantir que la prédiction soit la même qu'à l'entraînement, il faut
    appliquer les mêmes transformations (feature engineering, encodage,
    normalisation). Si possible, sauvegardez l'encodeur utilisé lors de
    l'entraînement sous `models/encoder.pkl` et le scaler sous `models/scaler.pkl`.
- L'API écrit un log (fichier `api.log`) contenant pour chaque prédiction :
    l'entrée, le score retourné et la latence. Ce fichier sert ensuite pour le
    monitoring et la détection de dérive.

Comment utiliser (rapide) :
- Démarrer localement : `uvicorn src.api:app --reload --port 8000`
- Tester l'état : GET `/health`
- Demander une prédiction : POST `/predict` avec corps JSON `{"data": {...}}`

Auteur : généré et enrichi (commentaires en français)
Date : 2026-02
"""

import time
import logging
import shutil
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional
import pandas as pd
import psutil

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel

# Importer les fonctions de prétraitement / feature engineering du projet.
from src.feature_engineering import create_ratio_features, create_interaction_features
from src.preprocessing import scale_features
from src.database import (
    log_prediction_to_db,
    get_logs_as_dataframe,
    get_prediction_stats,
    test_connection,
    record_drift_detection,
    create_alert,
    get_local_now,
    ensure_prediction_log_schema,
)
from src.monitoring_pg import detect_data_drift


# -------- Configuration du logger --------
logger = logging.getLogger("api")
logger.setLevel(logging.INFO)

# Handler pour la console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)
logger.propagate = False

# -------- structures de données (schémas de requête/réponse) --------------
class PredictionRequest(BaseModel):
    data: dict


class MultiPredictRequest(BaseModel):
    """Schéma pour requête /multipredict avec liste de clients"""
    data: list


class PredictionResponse(BaseModel):
    score: float
    model_version: str
    cpu_usage_pct: Optional[float] = None
    gpu_usage_pct: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    compute_device: str = "cpu"


# -------- définition de l'application FastAPI -----------------------------
app = FastAPI(
    title="Prêt à Dépenser - Scoring API",
    description="Service de prédiction de probabilité de défaut de paiement",
    version="1.0",
)

# -------- Événements de démarrage/arrêt --------
@app.on_event("startup")
async def startup_event():
    """Vérifie la connexion à PostgreSQL au démarrage."""
    logger.info("Application démarrée")
    ensure_prediction_log_schema()
    if test_connection():
        logger.info("PostgreSQL connection verified")
    else:
        logger.warning("PostgreSQL connection failed - API may have limited functionality")


def _capture_prediction_start() -> Dict[str, Any]:
    process = psutil.Process(os.getpid())
    cpu_times = process.cpu_times()
    return {
        "started_at": time.perf_counter(),
        "process_cpu_seconds": float(cpu_times.user + cpu_times.system),
    }


def _read_gpu_metrics() -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=1,
            check=True,
        )
    except Exception:
        return {
            "gpu_usage_pct": None,
            "gpu_memory_mb": None,
            "compute_device": "cpu",
        }

    rows = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            rows.append(
                {
                    "name": parts[0],
                    "gpu_usage_pct": float(parts[1]),
                    "gpu_memory_mb": float(parts[2]),
                }
            )
        except ValueError:
            continue

    if not rows:
        return {
            "gpu_usage_pct": None,
            "gpu_memory_mb": None,
            "compute_device": "cpu",
        }

    busiest_gpu = max(rows, key=lambda item: item["gpu_usage_pct"])
    return {
        "gpu_usage_pct": busiest_gpu["gpu_usage_pct"],
        "gpu_memory_mb": busiest_gpu["gpu_memory_mb"],
        "compute_device": busiest_gpu["name"] if busiest_gpu["gpu_usage_pct"] > 0 or busiest_gpu["gpu_memory_mb"] > 0 else "cpu",
    }


def _finalize_prediction_metrics(start_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    wall_seconds = max(time.perf_counter() - start_snapshot["started_at"], 1e-6)
    process = psutil.Process(os.getpid())
    cpu_times = process.cpu_times()
    cpu_seconds = float(cpu_times.user + cpu_times.system) - start_snapshot["process_cpu_seconds"]
    cpu_count = max(psutil.cpu_count(logical=True) or 1, 1)
    cpu_usage_pct = max(0.0, min(100.0, (cpu_seconds / (wall_seconds * cpu_count)) * 100.0))

    gpu_metrics = _read_gpu_metrics()
    return {
        "cpu_usage_pct": round(cpu_usage_pct, 2),
        "gpu_usage_pct": round(gpu_metrics["gpu_usage_pct"], 2) if gpu_metrics["gpu_usage_pct"] is not None else None,
        "gpu_memory_mb": round(gpu_metrics["gpu_memory_mb"], 2) if gpu_metrics["gpu_memory_mb"] is not None else None,
        "compute_device": gpu_metrics["compute_device"],
    }


def _get_system_resource_snapshot() -> Dict[str, Any]:
    gpu_metrics = _read_gpu_metrics()
    return {
        "cpu_usage_pct": round(psutil.cpu_percent(interval=0.05), 2),
        "gpu_usage_pct": round(gpu_metrics["gpu_usage_pct"], 2) if gpu_metrics["gpu_usage_pct"] is not None else None,
        "gpu_memory_mb": round(gpu_metrics["gpu_memory_mb"], 2) if gpu_metrics["gpu_memory_mb"] is not None else None,
        "compute_device": gpu_metrics["compute_device"],
    }

# chemins vers les artefacts. On charge le modèle et les objets de
# prétraitement (scaler, encodeur) depuis le dossier `models/`.
MODEL_PATH = Path(__file__).parent.parent / "models" / "best_model.pkl"
SCALER_PATH = Path(__file__).parent.parent / "models" / "scaler.pkl"
ENCODER_PATH = Path(__file__).parent.parent / "models" / "encoder.pkl"

# déterminer quelles colonnes du jeu d'entraînement étaient numériques
# Nous utilisons cette liste pour vérifier que les valeurs reçues pour
# ces colonnes peuvent bien être converties en `float`. Cela évite les
# erreurs si le client envoie une chaîne de caractères à la place d'un
# nombre pour une variable numérique.
_numeric_columns = []
try:
    _train_sample = pd.read_csv(Path(__file__).parent.parent / "data" / "application_train.csv", nrows=1)
    _numeric_columns = _train_sample.select_dtypes(include=["number"]).columns.tolist()
except Exception:
    # si le fichier d'entraînement est absent ou illisible (ex: CI/CD)
    # on utilise une liste par défaut de colonnes numériques connues
    # pour maintenir la validation des types en CI/CD
    _numeric_columns = [
        "SK_ID_CURR", "CNT_CHILDREN", "CNT_FAM_MEMBERS",
        "AMT_INCOME_TOTAL", "AMT_CREDIT", "AMT_ANNUITY", "AMT_GOODS_PRICE",
        "DAYS_BIRTH", "DAYS_EMPLOYED", "DAYS_REGISTRATION", "DAYS_ID_PUBLISH",
        "OWN_CAR_AGE", "FLAG_MOBIL", "FLAG_EMP_PHONE",
        "REGION_POPULATION_RELATIVE", "HOUR_APPR_PROCESS_START",
        "EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3",
        "DAYS_LAST_PHONE_CHANGE", "CREDIT_INCOME_PERC", "ANNUITY_INCOME_PERC",
        "ANNUITY_CREDIT_PERC", "GOODS_CREDIT_PERC", "PAYMENT_RATE",
        "AGE_YEARS", "EMPLOYED_YEARS"
    ]

# --- Chargement optionnel d'un encodeur catégoriel ---
# Nous essayons de charger un artefact `encoder.pkl` situé dans `models/`.
# Cet objet peut être :
# - un `sklearn.compose.ColumnTransformer` / `OneHotEncoder` / `Pipeline`
# - un dict {col: encoder} où chaque encoder est par ex. un LabelEncoder
# - tout objet offrant une méthode `.transform()` et idéalement
#   `.get_feature_names_out()` pour retrouver les noms de colonnes créés.
# Si aucun encodeur n'est présent, l'API fonctionne en mode dégradé :
# elle n'encode pas les colonnes catégorielles mais essaie de gérer les
# colonnes manquantes et numériques. Charger l'encodeur permet de
# reproduire exactement le preprocessing utilisé en entraînement.
try:
    if ENCODER_PATH.exists():
        encoder = joblib.load(ENCODER_PATH)
    else:
        encoder = None
except Exception as exc:
    logger.warning(f"Impossible de charger encoder.pkl : {exc}")
    encoder = None

try:
    model = joblib.load(MODEL_PATH)
except Exception as exc:
    logger.error(f"erreur chargement du modèle : {exc}")
    model = None

scaler = None
if SCALER_PATH.exists():
    try:
        scaler = joblib.load(SCALER_PATH)
    except Exception as exc:
        logger.warning(f"scaler non trouvé ou invalide : {exc}")


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest, log_prediction: bool = True):
    """Predict the default probability for a single client.

    The input JSON must contain a `data` key whose value is a dictionary of
    feature names and numerical values.  Any missing feature will raise a 422
    error and is considered a client error.
    
    Parameters:
    -----------
    request : PredictionRequest
        Requête avec les données du client
    log_prediction : bool
        Si False, n'enregistre pas le log (utilisé quand appelé depuis /multipredict)
    """

    if model is None:
        raise HTTPException(status_code=500, detail="Modèle non chargé")

    # early validation: any key that corresponds to a numeric column in the
    # original training dataset must be convertible to float.  categorical
    # features are ignored because they may legitimately contain strings.
    for key, val in request.data.items():
        if key in _numeric_columns and val is not None:
            try:
                float(val)
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail=f"valeur non numérique pour '{key}': {val}",
                )

    # transform input into a DataFrame with a single row
    try:
        df = pd.DataFrame([request.data])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"données invalides : {exc}")

    # ---------------------------
    # 1) Feature engineering
    # ---------------------------
    # On applique les mêmes transformations que pendant l'entraînement :
    # - création de ratios financiers (CREDIT_INCOME_PERC, ...)
    # - features d'interaction (INCOME_PER_PERSON, ...)
    # Ces fonctions ajoutent des colonnes au DataFrame. Elles ne modifient
    # pas l'ordre original des colonnes mais ajoutent de nouvelles colonnes
    # calculées à partir des données brutes reçues.
    df = create_ratio_features(df)
    df = create_interaction_features(df)

    # ---------------------------
    # 2) Encodage des catégorielles (si on a un encodeur enregistré)
    # ---------------------------
    # Beaucoup de modèles (XGBoost, etc.) ont été entraînés sur des
    # variables numériques uniquement. Si, lors du prétraitement, on a
    # utilisé un `OneHotEncoder` ou un `ColumnTransformer`, il faut réutiliser
    # exactement le même objet pour encoder les nouvelles données. Ceci évite
    # les erreurs de mismatch de features et garde la reproductibilité.
    if encoder is not None:
        try:
            # Cas A : l'encodeur est un dict {col: encoder} (ex: LabelEncoder par colonne)
            if isinstance(encoder, dict):
                encoded_parts = []
                for col, enc in encoder.items():
                    if col in df.columns:
                        try:
                            ser = df[col].astype(object).fillna("__MISSING__")
                            transformed = enc.transform(ser)
                            if getattr(transformed, 'ndim', 1) == 1:
                                s = pd.Series(transformed, index=df.index, name=f"{col}_enc")
                                encoded_parts.append(s)
                            else:
                                cols = [f"{col}_enc_{i}" for i in range(transformed.shape[1])]
                                encoded_parts.append(pd.DataFrame(transformed, columns=cols, index=df.index))
                        except Exception:
                            logger.warning(f"échec encodage colonne {col}, on continue")
                if encoded_parts:
                    enc_df = pd.concat(encoded_parts, axis=1)
                    df = pd.concat([df.drop(columns=[c for c in encoder.keys() if c in df.columns], errors='ignore'), enc_df], axis=1)
            # Cas B : l'encodeur est un transformeur sklearn (ColumnTransformer / Pipeline / OneHotEncoder)
            elif hasattr(encoder, "transform"):
                enc_array = encoder.transform(df)
                # si sortie sparse, convertir en dense
                try:
                    if hasattr(enc_array, "toarray"):
                        enc_array = enc_array.toarray()
                except Exception:
                    pass
                # tenter de récupérer les noms de colonnes générés
                try:
                    out_cols = encoder.get_feature_names_out(df.columns)
                except Exception:
                    out_cols = [f"enc_{i}" for i in range(getattr(enc_array, "shape", (0,))[1])]
                enc_df = pd.DataFrame(enc_array, columns=out_cols, index=df.index)
                # Conserver les colonnes numériques d'origine puis ajouter les colonnes encodées
                numeric_orig = df.select_dtypes(include=["number"]).copy()
                df = pd.concat([numeric_orig, enc_df], axis=1)
        except Exception:
            # Si l'encodage échoue, on continue sans encoder et on loggue
            logger.warning("L'encodage catégoriel a échoué, on poursuit sans encoder")

    # ---------------------------
    # 3) Supprimer les colonnes non numériques :
    #    - certains modèles n'acceptent pas les strings
    #    - on conservera uniquement les colonnes numériques pour la suite
    # ---------------------------
    df = df.select_dtypes(include=["number"]).copy()

    # Supprimer à nouveau toute colonne non numérique :
    # - Pendant l'entraînement, les catégories ont été converties en
    #   représentations numériques (ex: one-hot). Mais une requête brute
    #   peut contenir des chaînes de caractères. XGBoost et sklearn
    #   demandent des entrées numériques, donc on garde uniquement les
    #   colonnes numériques. Les colonnes manquantes attendues par le
    #   modèle seront ajoutées et initialisées à 0 plus bas.
    df = df.select_dtypes(include=["number"])

    # Mise à l'échelle (scaling) : si un `scaler` a été sauvegardé lors de
    # l'entraînement (par ex. StandardScaler), on l'applique ici pour que
    # la mise à l'échelle soit cohérente entre entraînement et inference.
    if scaler is not None:
        try:
            # scaler.transform returns numpy array; wrap back to DataFrame to keep
            df = pd.DataFrame(scaler.transform(df), columns=df.columns)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"erreur de mise à l'échelle : {exc}")

    # Alignement des colonnes avec ce que le modèle attend :
    # L'entraînement a produit un ensemble de colonnes (features) particulier.
    # Si la requête client ne fournit pas toutes ces colonnes (cas courant
    # pour de nouvelles catégories ou features optionnelles), on crée les
    # colonnes manquantes et on les initialise à 0. C'est un palliatif
    # simple pour éviter une erreur, mais l'idéal est de fournir le même
    # schéma que pendant l'entraînement (sauvegarder l'encodeur aide ici).
    if model is not None:
        try:
            booster = model.get_booster()
            expected = booster.feature_names or []
            # calculer les colonnes manquantes
            missing = [c for c in expected if c not in df.columns]
            if missing:
                # créer un DataFrame de zéros pour toutes les colonnes manquantes
                zeros = pd.DataFrame(0, index=df.index, columns=missing)
                # concaténer en une seule opération (plus efficace que d'ajouter
                # colonne par colonne, évite la fragmentation mémoire)
                df = pd.concat([df, zeros], axis=1)
            if expected:
                df = df[expected]
        except Exception:
            # si le modèle ne fournit pas la liste des noms de features (cas
            # rare) ou si une erreur survient, on ignore l'alignement et on
            # laisse la prédiction potentiellement échouer avec une erreur
            # explicite afin que l'utilisateur puisse corriger l'entrée.
            pass

    resource_start = _capture_prediction_start()
    start = time.time()
    try:
        proba = model.predict_proba(df)[:, 1][0]
    except Exception as exc:
        # Les erreurs communes proviennent d'un mismatch de colonnes ou de
        # types invalides (ex: une chaîne où il faut un nombre).
        logger.error("échec de la prédiction : %s", exc)
        # Enregistrer l'erreur dans PostgreSQL
        # Chercher le client_id avec les deux clés possibles (SK_ID_CURR ou client_id)
        client_id = request.data.get('SK_ID_CURR') or request.data.get('client_id')
        latency = time.time() - start
        prediction_metrics = _finalize_prediction_metrics(resource_start)
        log_prediction_to_db(
            client_id=client_id,
            input_data=request.data,
            score=None,
            latency_seconds=latency,
            prediction_type="single",
            error_message=str(exc),
            model_version="1.0",
            **prediction_metrics,
        )
        raise HTTPException(status_code=400, detail=f"erreur de prédiction: {exc}")
    latency = time.time() - start
    prediction_metrics = _finalize_prediction_metrics(resource_start)

    # Enregistrer la prédiction dans PostgreSQL
    if log_prediction:
        # Chercher le client_id avec les deux clés possibles (SK_ID_CURR ou client_id)
        client_id = request.data.get('SK_ID_CURR') or request.data.get('client_id')
        log_prediction_to_db(
            client_id=client_id,
            input_data=request.data,
            score=float(proba),
            latency_seconds=latency,
            prediction_type="single",
            error_message=None,
            model_version="1.0",
            **prediction_metrics,
        )

    return PredictionResponse(score=float(proba), model_version="1.0", **prediction_metrics)


@app.get("/health")
def health():
    return {"status": "ok"}








@app.post("/multipredict")
def multipredict(request: MultiPredictRequest):
    """
    Endpoint pour prédictions batch (jusqu'à 50 clients à la fois).
    
    Entrée:
        {
            "data": [
                {"SK_ID_CURR": 100001, "AMT_INCOME_TOTAL": 75000, ...},
                {"SK_ID_CURR": 100002, "AMT_INCOME_TOTAL": 85000, ...},
                ...
            ]
        }
    
    Sortie:
        {
            "predictions": [
                {"SK_ID_CURR": 100001, "score": 0.42, "latency_ms": 15.3},
                {"SK_ID_CURR": 100002, "score": 0.38, "latency_ms": 14.8},
                ...
            ],
            "total": 2,
            "avg_score": 0.40,
            "total_latency_ms": 30.1
        }
    """
    
    if model is None:
        raise HTTPException(status_code=500, detail="Modèle non chargé")
    
    # Vérifier que request.data est une liste
    if not isinstance(request.data, list):
        raise HTTPException(
            status_code=400,
            detail="Pour /multipredict, data doit être une LISTE de dictionnaires"
        )
    
    if len(request.data) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 clients à la fois"
        )
    
    if len(request.data) == 0:
        raise HTTPException(
            status_code=400,
            detail="Minimum 1 client requis"
        )
    
    predictions = []
    start_time = time.time()
    
    for idx, client_data in enumerate(request.data):
        resource_start = _capture_prediction_start()
        start = time.time()
        
        # Créer une requête simple pour chaque client
        single_request = PredictionRequest(data=client_data)
        
        try:
            # Appeler predict() pour chaque client SANS enregistrer le log
            # (le log sera enregistré en tant que batch)
            response = predict(single_request, log_prediction=False)
            latency = (time.time() - start) * 1000
            
            # Extraire client_id avec les deux clés possibles (SK_ID_CURR ou client_id)
            sk_id = client_data.get('SK_ID_CURR') or client_data.get('client_id')
            
            # Log la prédiction en PostgreSQL
            log_prediction_to_db(
                client_id=sk_id,
                input_data=client_data,
                score=response.score,
                latency_seconds=latency / 1000,
                prediction_type="batch",
                error_message=None,
                model_version="1.0",
                cpu_usage_pct=response.cpu_usage_pct,
                gpu_usage_pct=response.gpu_usage_pct,
                gpu_memory_mb=response.gpu_memory_mb,
                compute_device=response.compute_device,
            )
            
            predictions.append({
                "SK_ID_CURR": sk_id,
                "score": response.score,
                "latency_ms": round(latency, 2)
            })
            
        except Exception as e:
            # Si une prédiction échoue, continuer avec les autres
            sk_id = client_data.get('SK_ID_CURR') or client_data.get('client_id')
            latency = (time.time() - start) * 1000
            
            # Enregistrer l'erreur dans PostgreSQL
            prediction_metrics = _finalize_prediction_metrics(resource_start)
            log_prediction_to_db(
                client_id=sk_id,
                input_data=client_data,
                score=None,
                latency_seconds=latency / 1000,
                prediction_type="batch",
                error_message=str(e),
                model_version="1.0",
                **prediction_metrics,
            )
            
            # Créer une alerte pour l'erreur
            create_alert(
                alert_type="error_rate",
                severity="WARNING",
                message=f"Error in batch prediction for client {sk_id}: {str(e)}",
                metadata={"client_id": sk_id, "error": str(e)}
            )
            
            predictions.append({
                "SK_ID_CURR": sk_id,
                "error": str(e),
                "score": None
            })
    
    total_latency = (time.time() - start_time) * 1000
    avg_score = sum([p['score'] for p in predictions if p.get('score') is not None]) / len([p for p in predictions if p.get('score') is not None]) if predictions else 0
    
    return {
        "predictions": predictions,
        "total": len(predictions),
        "avg_score": round(avg_score, 4),
        "total_latency_ms": round(total_latency, 2)
    }


@app.get("/health-detailed")
def health_detailed():
    """
    Retourne l'état de santé détaillé de l'API et de la base de données.
    
    Exemple :
    - GET /health-detailed
    """
    
    db_health = test_connection()
    model_loaded = model is not None
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok" if (db_health and model_loaded) else "degraded",
            "database": "connected" if db_health else "disconnected",
            "model": "loaded" if model_loaded else "not loaded",
            "resources": _get_system_resource_snapshot(),
            "timestamp": get_local_now().isoformat()
        }
    )



