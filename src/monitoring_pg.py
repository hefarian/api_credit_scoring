# -*- coding: utf-8 -*-
"""
Module de monitoring pour Streamlit et dashboard - utilisant PostgreSQL.

Récupère les données depuis la base de données PostgreSQL au lieu du fichier.
"""

import pandas as pd
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, List, Any
from pathlib import Path
import json

from src.database import (
    get_logs_as_dataframe,
    get_prediction_stats,
    get_recent_alerts,
    record_drift_detection
)

logger = logging.getLogger("monitoring")

# ============================================================================
# CHARGER LES STATISTIQUES DE RÉFÉRENCE (données d'entraînement)
# ============================================================================
RAW_REFERENCE_PATH = Path("data/application_train.csv")

MONITORED_INPUT_FIELDS = [
    "CODE_GENDER",
    "FLAG_OWN_CAR",
    "FLAG_OWN_REALTY",
    "CNT_CHILDREN",
    "AMT_INCOME_TOTAL",
    "AMT_CREDIT",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "NAME_EDUCATION_TYPE",
    "NAME_FAMILY_STATUS",
    "NAME_HOUSING_TYPE",
    "DAYS_BIRTH",
    "DAYS_EMPLOYED",
    "OCCUPATION_TYPE",
    "CNT_FAM_MEMBERS",
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
]

NUMERIC_MONITORED_FIELDS = {
    "CNT_CHILDREN",
    "AMT_INCOME_TOTAL",
    "AMT_CREDIT",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "DAYS_BIRTH",
    "DAYS_EMPLOYED",
    "CNT_FAM_MEMBERS",
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
}

_reference_stats_cache: Dict[str, Dict[str, Dict[str, float]]] = {}
_reference_frame_cache: Dict[str, pd.DataFrame] = {}


def _load_reference_frame(reference_path: Path) -> pd.DataFrame:
    if not reference_path.exists():
        logger.warning("Reference file %s not found", reference_path)
        return pd.DataFrame()
    return pd.read_csv(reference_path)


def get_reference_frame(reference_kind: str = "raw") -> pd.DataFrame:
    """Récupère le jeu de référence brut avec cache."""
    if reference_kind != "raw":
        logger.warning("Only raw reference data is supported for drift comparison")
        return pd.DataFrame()

    if reference_kind not in _reference_frame_cache:
        _reference_frame_cache[reference_kind] = _load_reference_frame(RAW_REFERENCE_PATH)
    return _reference_frame_cache[reference_kind].copy()


def _build_reference_stats(reference_df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    if reference_df is None or reference_df.empty:
        return {}

    reference_numeric = reference_df.select_dtypes(include=["number"])
    reference_stats: Dict[str, Dict[str, float]] = {}

    for col in reference_numeric.columns:
        series = reference_numeric[col].dropna()
        if series.empty:
            continue
        reference_stats[col] = {
            "mean": float(series.mean()),
            "std": float(series.std()),
            "min": float(series.min()),
            "max": float(series.max()),
            "count": int(series.count()),
        }

    return reference_stats


def load_reference_stats(reference_kind: str = "raw") -> Dict[str, Dict[str, float]]:
    """
    Charge les statistiques de référence depuis les données brutes ou le jeu préparé du modèle.
    """
    reference_files = {
        "raw": RAW_REFERENCE_PATH,
    }

    reference_path = reference_files.get(reference_kind)
    if reference_path is None:
        logger.warning("Unknown reference kind %s", reference_kind)
        return {}

    try:
        reference_df = _load_reference_frame(reference_path)
        reference_stats = _build_reference_stats(reference_df)
        logger.info(
            "Loaded %s reference stats for %s numeric features",
            reference_kind,
            len(reference_stats),
        )
        return reference_stats
    except Exception as e:
        logger.error("Error loading %s reference stats: %s", reference_kind, str(e))
        return {}


def get_reference_stats(reference_kind: str = "raw") -> Dict[str, Dict[str, float]]:
    """Récupère les stats de référence avec cache."""
    if reference_kind not in _reference_stats_cache:
        _reference_stats_cache[reference_kind] = load_reference_stats(reference_kind)
    return _reference_stats_cache[reference_kind]


def _parse_input_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str) and payload.strip():
        try:
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _extract_recent_input_frame(logs_df: pd.DataFrame) -> pd.DataFrame:
    payload_rows: List[Dict[str, Any]] = []

    for _, row in logs_df.iterrows():
        parsed = _parse_input_payload(row.get("input_data"))
        if parsed:
            payload_rows.append(parsed)

    if not payload_rows:
        return pd.DataFrame()

    return pd.DataFrame(payload_rows)


def _compare_recent_input_fields(
    recent_df: pd.DataFrame,
    reference_df: pd.DataFrame,
    threshold: float,
) -> Dict[str, Any]:
    if recent_df is None or recent_df.empty:
        return {
            "comparison_key": "raw_input",
            "comparison_label": "Comparaison des champs d'entrée",
            "reference_path": str(RAW_REFERENCE_PATH).replace("\\", "/"),
            "has_drift": False,
            "details": "Pas de données récentes exploitables",
            "drift_score": 0.0,
            "threshold": threshold,
            "num_features_analyzed": 0,
            "recent_sample_size": 0,
            "variables": [],
        }

    if reference_df is None or reference_df.empty:
        return {
            "comparison_key": "raw_input",
            "comparison_label": "Comparaison des champs d'entrée",
            "reference_path": str(RAW_REFERENCE_PATH).replace("\\", "/"),
            "has_drift": False,
            "details": "Données de référence brutes indisponibles",
            "drift_score": 0.0,
            "threshold": threshold,
            "num_features_analyzed": 0,
            "recent_sample_size": len(recent_df),
            "variables": [],
        }

    shared_features = [
        feature for feature in MONITORED_INPUT_FIELDS
        if feature in recent_df.columns and feature in reference_df.columns
    ]
    variables_drift = []
    global_changes = []

    for feature in shared_features:
        recent_series = recent_df[feature].dropna()
        reference_series = reference_df[feature].dropna()
        if recent_series.empty or reference_series.empty:
            continue

        if feature in NUMERIC_MONITORED_FIELDS:
            avg_recent = float(pd.to_numeric(recent_series, errors="coerce").dropna().mean())
            avg_reference = float(pd.to_numeric(reference_series, errors="coerce").dropna().mean())
            if abs(avg_reference) > 1e-6:
                change_ratio = abs(avg_recent - avg_reference) / abs(avg_reference)
            else:
                change_ratio = abs(avg_recent - avg_reference)

            reference_display = f"moyenne = {avg_reference:.4f}"
            recent_display = f"moyenne = {avg_recent:.4f}"
            comparison_type = "Numérique"
            ref_std = float(pd.to_numeric(reference_series, errors="coerce").dropna().std())
            ref_min = float(pd.to_numeric(reference_series, errors="coerce").dropna().min())
            ref_max = float(pd.to_numeric(reference_series, errors="coerce").dropna().max())
        else:
            recent_counts = recent_series.astype(str).value_counts(normalize=True)
            reference_counts = reference_series.astype(str).value_counts(normalize=True)
            reference_top = str(reference_counts.index[0])
            recent_top = str(recent_counts.index[0])
            reference_share = float(reference_counts.iloc[0])
            recent_share = float(recent_counts.iloc[0])
            if reference_top == recent_top:
                change_ratio = abs(recent_share - reference_share) / max(reference_share, 1e-6)
            else:
                change_ratio = 1.0

            avg_reference = reference_share
            avg_recent = recent_share
            reference_display = f"modalité dominante = {reference_top} ({reference_share * 100:.1f}%)"
            recent_display = f"modalité dominante = {recent_top} ({recent_share * 100:.1f}%)"
            comparison_type = "Catégorielle"
            ref_std = 0.0
            ref_min = 0.0
            ref_max = 0.0

        global_changes.append(change_ratio)

        if change_ratio <= 0.05:
            status = "✅ OK"
            status_code = "ok"
        elif change_ratio < 0.15:
            status = "🟡 Bas"
            status_code = "low"
        elif change_ratio < 0.25:
            status = "🟠 Moyen"
            status_code = "medium"
        else:
            status = "🚨 Critique"
            status_code = "critical"

        variables_drift.append({
            "feature": feature,
            "avg_reference": avg_reference,
            "avg_recent": avg_recent,
            "change_pct": change_ratio * 100,
            "status": status,
            "status_code": status_code,
            "ref_std": ref_std,
            "ref_min": ref_min,
            "ref_max": ref_max,
            "source": "Entrée API",
            "formula": feature,
            "comparison_type": comparison_type,
            "reference_display": reference_display,
            "recent_display": recent_display,
        })

    drift_score = float(sum(global_changes) / len(global_changes)) if global_changes else 0.0
    return {
        "comparison_key": "raw_input",
        "comparison_label": "Comparaison des champs d'entrée",
        "reference_path": str(RAW_REFERENCE_PATH).replace("\\", "/"),
        "has_drift": drift_score > threshold,
        "details": (
            f"Comparaison limitée aux champs d'entrée métier. Dérive moyenne: {drift_score:.4f} "
            f"(seuil: {threshold}, variables comparées: {len(variables_drift)})"
        ),
        "drift_score": drift_score,
        "threshold": threshold,
        "num_features_analyzed": len(variables_drift),
        "recent_sample_size": len(recent_df),
        "variables": variables_drift,
    }

# ============================================================================
# FUSEAU HORAIRE LOCAL (GMT+1)
# ============================================================================
LOCAL_TZ = ZoneInfo("Europe/Paris")  # GMT+1 (hiver) / GMT+2 (été)

def get_local_now():
    """
    Retourne l'heure actuelle au fuseau horaire local (GMT+1).
    Utilisée pour les logs et affichages.
    
    Returns:
        datetime: Datetime avec timezone GMT+1
    """
    return datetime.now(LOCAL_TZ)


def get_local_now_naive() -> datetime:
    """Retourne l'heure locale sans timezone pour comparer avec des timestamps pandas naïfs."""
    return get_local_now().replace(tzinfo=None)


def normalize_timestamps_to_local_naive(timestamp_series: pd.Series) -> pd.Series:
    """Convertit des timestamps pandas en heure locale sans timezone.

    Les timestamps PostgreSQL arrivent souvent timezone-aware en UTC. Il faut d'abord
    les convertir en heure locale, puis retirer la timezone pour pouvoir comparer
    proprement avec des bornes locales naïves.
    """
    if getattr(timestamp_series.dt, "tz", None) is not None:
        return timestamp_series.dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    return timestamp_series


def load_api_logs(last_n_hours: int = 24, limit: Optional[int] = None) -> Optional[pd.DataFrame]:
    """
    Charger les logs depuis PostgreSQL.
    
    Args:
        last_n_hours: Nombre d'heures à récupérer
        limit: Limite du nombre de lignes
    
    Returns:
        DataFrame avec les logs ou None
    """
    try:
        df = get_logs_as_dataframe(last_n_hours=last_n_hours, limit=limit)
        
        if df is None or df.empty:
            logger.warning("No logs found in database")
            return None
        
        # Convertir timestamp en datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        for column in ["cpu_usage_pct", "gpu_usage_pct", "gpu_memory_mb", "compute_device"]:
            if column not in df.columns:
                df[column] = None
        
        logger.info(f"Loaded {len(df)} logs from PostgreSQL")
        return df
        
    except Exception as e:
        logger.error(f"Error loading logs: {str(e)}")
        return None


def compute_prediction_stats(logs_df: Optional[pd.DataFrame] = None) -> Dict:
    """
    Calculer les statistiques des prédictions.
    
    Args:
        logs_df: DataFrame des logs (si None, les récupère depuis DB)
    
    Returns:
        Dict avec statistiques
    """
    if logs_df is None:
        logs_df = load_api_logs(last_n_hours=24)
    
    if logs_df is None or logs_df.empty:
        return {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "avg_score": 0.0,
            "min_score": 0.0,
            "max_score": 0.0,
            "avg_latency_seconds": 0.0,
            "avg_cpu_usage_pct": 0.0,
            "avg_gpu_usage_pct": 0.0,
            "avg_gpu_memory_mb": 0.0,
            "error_rate_pct": 0.0
        }
    
    try:
        if 'timestamp' in logs_df.columns:
            logs_df['timestamp'] = normalize_timestamps_to_local_naive(logs_df['timestamp'])
        
        # Today starts at 00:00:00 local time
        today_start = get_local_now_naive().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = len(logs_df[logs_df['timestamp'] >= today_start]) if 'timestamp' in logs_df.columns else 0
        
        stats = {
            "total": len(logs_df),
            "successful": len(logs_df[logs_df['error_message'].isna()]),
            "failed": len(logs_df[logs_df['error_message'].notna()]),
            "avg_score": float(logs_df['score'].mean()) if logs_df['score'].notna().any() else 0.0,
            "min_score": float(logs_df['score'].min()) if logs_df['score'].notna().any() else 0.0,
            "max_score": float(logs_df['score'].max()) if logs_df['score'].notna().any() else 0.0,
            "avg_latency_seconds": float(logs_df['latency_seconds'].mean()),
            "avg_cpu_usage_pct": float(pd.to_numeric(logs_df.get('cpu_usage_pct'), errors='coerce').mean()) if 'cpu_usage_pct' in logs_df.columns else 0.0,
            "avg_gpu_usage_pct": float(pd.to_numeric(logs_df.get('gpu_usage_pct'), errors='coerce').mean()) if 'gpu_usage_pct' in logs_df.columns else 0.0,
            "avg_gpu_memory_mb": float(pd.to_numeric(logs_df.get('gpu_memory_mb'), errors='coerce').mean()) if 'gpu_memory_mb' in logs_df.columns else 0.0,
            "error_rate_pct": round(100.0 * len(logs_df[logs_df['error_message'].notna()]) / len(logs_df), 2) if len(logs_df) > 0 else 0.0,
            "today_count": today_count
        }
        
        logger.info(f"Computed stats: {stats['total']} predictions, error_rate={stats['error_rate_pct']}%")
        return stats
        
    except Exception as e:
        logger.error(f"Error computing stats: {str(e)}")
        # Retourner un dictionnaire par défaut avec toutes les clés en cas d'erreur
        return {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "avg_score": 0.0,
            "min_score": 0.0,
            "max_score": 0.0,
            "avg_latency_seconds": 0.0,
            "avg_cpu_usage_pct": 0.0,
            "avg_gpu_usage_pct": 0.0,
            "avg_gpu_memory_mb": 0.0,
            "error_rate_pct": 0.0,
            "today_count": 0
        }


def detect_data_drift(logs_df: Optional[pd.DataFrame] = None, threshold: float = 0.05) -> Dict:
    """
    Détecter la dérive des données en comparant avec les données d'entraînement.
    
    Args:
        logs_df: DataFrame des logs
        threshold: Seuil de dérive
    
    Returns:
        Dict avec résultats de drift detection
    """
    if logs_df is None:
        logs_df = load_api_logs(last_n_hours=24)
    
    if logs_df is None or logs_df.empty:
        return {
            "has_drift": False,
            "details": "Pas de données",
            "variables": [],
            "reference_comparisons": {}
        }

    try:
        if 'timestamp' in logs_df.columns:
            logs_df['timestamp'] = normalize_timestamps_to_local_naive(logs_df['timestamp'])
        
        # Comparer sur toutes les prédictions chargées plutôt que sur une fenêtre récente.
        df_analyzed = logs_df.copy()

        if df_analyzed.empty:
            return {
                "has_drift": False,
                "details": "Aucune prédiction exploitable dans la fenêtre de chargement",
                "variables": [],
                "reference_comparisons": {}
            }
        raw_recent_df = _extract_recent_input_frame(df_analyzed)
        if raw_recent_df.empty:
            logger.warning("No parseable input_data found in loaded logs")
            return {
                "has_drift": False,
                "details": "Aucune entrée exploitable trouvée dans les prédictions chargées",
                "variables": [],
                "debug": "input_data vide ou mal formé",
                "reference_comparisons": {}
            }

        raw_comparison = _compare_recent_input_fields(
            recent_df=raw_recent_df,
            reference_df=get_reference_frame("raw"),
            threshold=threshold,
        )

        primary_comparison = raw_comparison
        reference_comparisons = {
            raw_comparison["comparison_key"]: raw_comparison,
        }

        result = {
            "has_drift": primary_comparison["has_drift"],
            "details": primary_comparison["details"],
            "drift_score": primary_comparison["drift_score"],
            "threshold": threshold,
            "num_features_analyzed": primary_comparison["num_features_analyzed"],
            "variables": primary_comparison["variables"],
            "comparison_used": primary_comparison["comparison_key"],
            "reference_comparisons": reference_comparisons,
            "recent_sample_size": len(raw_recent_df),
        }
        
        # Enregistrer le résultat dans PostgreSQL
        try:
            record_drift_detection(
                is_drift_detected=primary_comparison["has_drift"],
                drift_score=primary_comparison["drift_score"],
                details=result
            )
        except:
            pass
        
        if primary_comparison["has_drift"]:
            logger.warning("Drift detected! Overall change: %.4f", primary_comparison["drift_score"])
        
        return result
        
    except Exception as e:
        logger.error(f"Error detecting drift: {str(e)}")
        return {
            "has_drift": False,
            "details": f"Error: {str(e)}",
            "variables": []
        }


def generate_html_dashboard(prediction_stats: Dict, drift_stats: Dict) -> str:
    """
    Générer un dashboard HTML pour /monitor endpoint.
    
    Args:
        prediction_stats: Statistiques des prédictions
        drift_stats: Résultats de détection de drift
    
    Returns:
        HTML string
    """
    
    drift_alert = ""
    if drift_stats.get("has_drift"):
        drift_alert = """
        <div style="background: #C41E3A; padding: 15px; margin: 10px 0; color: white;">
            <h3>ALERTE: DRIFT DÉTECTÉ</h3>
            <p>Les données montrent une dérive significative</p>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Credit Scoring Monitoring</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #0B162C;
                color: #FFFFFF;
            }}
            h1 {{ color: #5FC2BA; }}
            .metric {{
                display: inline-block;
                margin: 20px;
                padding: 15px;
                background: #1C2942;
                border-left: 4px solid #5FC2BA;
                min-width: 200px;
            }}
            .metric-label {{ font-size: 12px; color: #5FC2BA; }}
            .metric-value {{ font-size: 24px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>Dashboard de Monitoring - Scoring Credit</h1>
        
        {drift_alert}
        
        <div class="metric">
            <div class="metric-label">Total Prédictions</div>
            <div class="metric-value">{prediction_stats.get('total', 0):,}</div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Score Moyen</div>
            <div class="metric-value">{prediction_stats.get('avg_score', 0):.4f}</div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Latence Moyenne</div>
            <div class="metric-value">{prediction_stats.get('avg_latency_seconds', 0)*1000:.2f} ms</div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Taux d'Erreur</div>
            <div class="metric-value">{prediction_stats.get('error_rate_pct', 0):.2f}%</div>
        </div>

        <div class="metric">
            <div class="metric-label">CPU moyen</div>
            <div class="metric-value">{prediction_stats.get('avg_cpu_usage_pct', 0):.2f}%</div>
        </div>

        <div class="metric">
            <div class="metric-label">GPU moyen</div>
            <div class="metric-value">{prediction_stats.get('avg_gpu_usage_pct', 0):.2f}%</div>
        </div>
        
        <h2>Détection de Dérive</h2>
        <p>Drift Score: {drift_stats.get('drift_score', 0):.4f}</p>
        <p>{drift_stats.get('details', 'N/A')}</p>
        
        <h2>Alertes Récentes</h2>
        <p>Voir endpoint /alerts pour la liste complète des alertes</p>
        
        <p style="margin-top: 40px; font-size: 12px; color: #5FC2BA;">
            Dernière mise à jour : {get_local_now().isoformat()}
        </p>
    </body>
    </html>
    """
    
    return html


def get_recent_alerts(limit: int = 10) -> List[Dict]:
    """
    Récupérer les alertes récentes.
    
    Args:
        limit: Nombre d'alertes
    
    Returns:
        Liste des alertes
    """
    return get_recent_alerts(limit=limit)


# Alias pour compatibilité avec le code existant
load_api_logs_pg = load_api_logs
compute_prediction_stats_pg = compute_prediction_stats
detect_data_drift_pg = detect_data_drift
