# -*- coding: utf-8 -*-
"""
Module de monitoring et détection de dérive (Data Drift)

Ce module fournit les fonctionnalités de monitoring :
- Chargement des logs d'API (format NDJSON)
- Calcul de statistiques sur les prédictions
- Détection de dérive (comparaison avec données d'entraînement)
- Analyse des performances en temps réel

Auteur : Copilot | Date : 2026-03-06
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

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


def load_api_logs(log_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Charge les logs de l'API au format NDJSON.
    
    Chaque ligne du fichier est un JSON contenant :
    - timestamp : datetime ISO
    - input : dictionnaire des features du client
    - score : probabilité de défaut (float)
    - latency_seconds : temps de réponse (float)
    
    Parameters:
    -----------
    log_path : Path, optional
        Chemin du fichier de logs. Par défaut : ../logs/api.log
    
    Returns:
    --------
    pd.DataFrame
        DataFrame contenant tous les logs chargés
    """
    if log_path is None:
        log_path = Path(__file__).parent.parent / "logs" / "api.log"
    
    logs_list = []
    
    if not log_path.exists():
        return pd.DataFrame()
    
    try:
        with open(log_path, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        logs_list.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        print(f"⚠️ Erreur lors de la lecture des logs : {e}")
        return pd.DataFrame()
    
    if not logs_list:
        return pd.DataFrame()
    
    # Convertir en DataFrame
    logs_df = pd.DataFrame(logs_list)
    
    # Convertir timestamp en datetime
    if 'timestamp' in logs_df.columns:
        logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
    
    return logs_df


def compute_prediction_stats(logs_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Calcule des statistiques sur les prédictions, séparées par type (single/batch) et combinées.
    
    Parameters:
    -----------
    logs_df : pd.DataFrame, optional
        DataFrame des logs chargés. Si None, les logs sont chargés automatiquement.
    
    Returns:
    --------
    dict
        Dictionnaire contenant statistiques pour single, batch et combinées
    """
    if logs_df is None:
        logs_df = load_api_logs()
    
    def compute_stats_for_df(df, label):
        """Fonction helper pour calculer les stats d'un DataFrame"""
        if df.empty:
            return {
                f"{label}_total": 0,
                f"{label}_avg_score": None,
                f"{label}_min_score": None,
                f"{label}_max_score": None,
                f"{label}_high_risk": 0,
                f"{label}_medium_risk": 0,
                f"{label}_low_risk": 0,
                f"{label}_avg_latency_ms": None,
                f"{label}_max_latency_ms": None,
                f"{label}_last_hour": 0,
            }
        
        result = {
            f"{label}_total": len(df),
            f"{label}_avg_score": float(df['score'].mean()) if 'score' in df.columns else None,
            f"{label}_min_score": float(df['score'].min()) if 'score' in df.columns else None,
            f"{label}_max_score": float(df['score'].max()) if 'score' in df.columns else None,
            f"{label}_std_score": float(df['score'].std()) if 'score' in df.columns else None,
        }
        
        # Clients à haut risque
        if 'score' in df.columns:
            result[f"{label}_high_risk"] = len(df[df['score'] > 0.6])
            result[f"{label}_medium_risk"] = len(df[(df['score'] > 0.45) & (df['score'] <= 0.6)])
            result[f"{label}_low_risk"] = len(df[df['score'] <= 0.45])
        
        # Latence
        if 'latency_seconds' in df.columns:
            result[f"{label}_avg_latency_ms"] = float(df['latency_seconds'].mean() * 1000)
            result[f"{label}_max_latency_ms"] = float(df['latency_seconds'].max() * 1000)
        
        # Dernière heure
        if 'timestamp' in df.columns:
            now = get_local_now()
            one_hour_ago = now - timedelta(hours=1)
            result[f"{label}_last_hour"] = len(df[df['timestamp'] > one_hour_ago])
        
        return result
    
    if logs_df.empty:
        return {
            "single_total": 0,
            "batch_total": 0,
            "combined_total": 0,
            "status": "Aucun log disponible"
        }
    
    # Séparer par type
    single_df = logs_df[logs_df.get('prediction_type', '') == 'single'] if 'prediction_type' in logs_df.columns else logs_df[logs_df.index.isin([])]
    batch_df = logs_df[logs_df.get('prediction_type', '') == 'batch'] if 'prediction_type' in logs_df.columns else logs_df[logs_df.index.isin([])]
    
    # Calculer les stats pour chaque type
    single_stats = compute_stats_for_df(single_df, "single")
    batch_stats = compute_stats_for_df(batch_df, "batch")
    combined_stats = compute_stats_for_df(logs_df, "combined")
    
    # Fusionner tous les résultats
    all_stats = {**single_stats, **batch_stats, **combined_stats}
    
    return all_stats


def detect_data_drift(
    logs_df: Optional[pd.DataFrame] = None,
    reference_data: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Détecte la dérive des données (data drift) avec seuils adaptatifs.
    
    Critères de dérive :
    - ALERTE (warning): 4-6 colonnes avec >30% de variation
    - CRITIQUE (danger): >6 colonnes avec >30% de variation OU >2 colonnes avec >50% de variation
    
    Parameters:
    -----------
    logs_df : pd.DataFrame, optional
        DataFrame des logs. Si None, les logs sont chargés automatiquement.
    reference_data : pd.DataFrame, optional
        Données de référence pour comparaison. Si None, chargées depuis data/application_train.csv
    """
    if logs_df is None:
        logs_df = load_api_logs()
    
    if logs_df.empty:
        return {
            "drift_detected": False,
            "drift_severity": "none",
            "status": "Pas assez de données pour détecter la dérive"
        }
    
    # Charger les données de référence si non fournies
    if reference_data is None:
        try:
            reference_data = pd.read_csv(
                Path(__file__).parent.parent / "data" / "application_train.csv"
            )
        except Exception as e:
            return {
                "drift_detected": False,
                "drift_severity": "unknown",
                "status": f"Impossible de charger les données de référence : {e}"
            }
    
    # Extraire les features des logs
    if 'input' not in logs_df.columns:
        return {
            "drift_detected": False,
            "drift_severity": "none",
            "status": "Format de logs incompatible"
        }
    
    try:
        input_data = pd.json_normalize(logs_df['input'])
    except Exception as e:
        return {
            "drift_detected": False,
            "drift_severity": "none",
            "status": f"Erreur lors de l'extraction des features : {e}"
        }
    
    # Comparer les colonnes numériques (exclure les IDs)
    numeric_cols = input_data.select_dtypes(include=[np.number]).columns.tolist()
    
    # Exclure les colonnes d'ID (SK_ID_*, ID, etc.)
    excluded_cols = {'SK_ID_CURR', 'SK_ID', 'ID','CNT_CHILDREN_'}
    numeric_cols = [col for col in numeric_cols if col not in excluded_cols]
    
    drift_details = {}
    drift_count_30pct = 0  # Colonnes avec >30% de variation
    drift_count_50pct = 0  # Colonnes avec >50% de variation
    DRIFT_THRESHOLD_MILD = 0.30    # 30% = alerte
    DRIFT_THRESHOLD_SEVERE = 0.50  # 50% = critique
    
    for col in numeric_cols[:20]:
        if col in reference_data.columns:
            ref_mean = reference_data[col].mean()
            curr_mean = input_data[col].mean()
            
            if abs(ref_mean) > 1e-6:
                variation = abs((curr_mean - ref_mean) / ref_mean)
                drift_details[col] = {
                    "reference_mean": float(ref_mean),
                    "current_mean": float(curr_mean),
                    "variation_ratio": float(variation),
                    "severity": "severe" if variation > DRIFT_THRESHOLD_SEVERE else ("mild" if variation > DRIFT_THRESHOLD_MILD else "normal")
                }
                
                if variation > DRIFT_THRESHOLD_SEVERE:
                    drift_count_50pct += 1
                    drift_count_30pct += 1
                elif variation > DRIFT_THRESHOLD_MILD:
                    drift_count_30pct += 1
    
    # Déterminer la sévérité
    drift_detected = False
    drift_severity = "none"
    
    if drift_count_50pct >= 2:
        drift_detected = True
        drift_severity = "severe"  # >50% sur 2+ colonnes
    elif drift_count_30pct > 6:
        drift_detected = True
        drift_severity = "severe"  # >30% sur 7+ colonnes
    elif drift_count_30pct >= 4:
        drift_severity = "warning"  # 4-6 colonnes avec >30%
    
    return {
        "drift_detected": drift_detected,
        "drift_severity": drift_severity,
        "drift_columns_30pct": drift_count_30pct,
        "drift_columns_50pct": drift_count_50pct,
        "total_monitored": len(numeric_cols),
        "details": drift_details
    }


def generate_drift_columns_html(drift_stats: Dict[str, Any]) -> str:
    """
    Génère un tableau HTML listant les colonnes critiques et alertes.
    """
    details = drift_stats.get("details", {})
    
    if not details:
        return ""
    
    # Séparer les colonnes par sévérité
    critical_cols = []
    alert_cols = []
    normal_cols = []
    
    for col, info in details.items():
        severity = info.get("severity", "normal")
        variation = info.get("variation_ratio", 0) * 100
        
        if severity == "severe":
            critical_cols.append((col, variation, info))
        elif severity == "mild":
            alert_cols.append((col, variation, info))
        else:
            normal_cols.append((col, variation, info))
    
    # Générer le HTML
    html_parts = []
    
    if critical_cols:
        html_parts.append('<div style="margin-top: 15px;">')
        html_parts.append('<h6 style="color: #dc3545; font-weight: bold;">🔴 Colonnes Critiques (>50% variation):</h6>')
        html_parts.append('<table style="width: 100%; font-size: 0.85rem; border-collapse: collapse;">')
        html_parts.append('<tr style="background: #f8d7da; border: 1px solid #dc3545;">')
        html_parts.append('<th style="padding: 8px; text-align: left;">Colonne</th>')
        html_parts.append('<th style="padding: 8px; text-align: right;">Variation</th>')
        html_parts.append('<th style="padding: 8px; text-align: right;">Ref Mean</th>')
        html_parts.append('<th style="padding: 8px; text-align: right;">Prod Mean</th>')
        html_parts.append('</tr>')
        
        for col, var, info in critical_cols:
            html_parts.append(f'<tr style="border-bottom: 1px solid #ddd;">')
            html_parts.append(f'<td style="padding: 8px;"><strong>{col}</strong></td>')
            html_parts.append(f'<td style="padding: 8px; text-align: right; color: #dc3545;"><strong>{var:.1f}%</strong></td>')
            html_parts.append(f'<td style="padding: 8px; text-align: right;">{info.get("reference_mean", 0):,.2f}</td>')
            html_parts.append(f'<td style="padding: 8px; text-align: right;">{info.get("current_mean", 0):,.2f}</td>')
            html_parts.append('</tr>')
        
        html_parts.append('</table>')
        html_parts.append('</div>')
    
    if alert_cols:
        html_parts.append('<div style="margin-top: 15px;">')
        html_parts.append('<h6 style="color: #ffc107; font-weight: bold;">🟠 Colonnes Alertes (30-50% variation):</h6>')
        html_parts.append('<table style="width: 100%; font-size: 0.85rem; border-collapse: collapse;">')
        html_parts.append('<tr style="background: #fff3cd; border: 1px solid #ffc107;">')
        html_parts.append('<th style="padding: 8px; text-align: left;">Colonne</th>')
        html_parts.append('<th style="padding: 8px; text-align: right;">Variation</th>')
        html_parts.append('<th style="padding: 8px; text-align: right;">Ref Mean</th>')
        html_parts.append('<th style="padding: 8px; text-align: right;">Prod Mean</th>')
        html_parts.append('</tr>')
        
        for col, var, info in alert_cols:
            html_parts.append(f'<tr style="border-bottom: 1px solid #ddd;">')
            html_parts.append(f'<td style="padding: 8px;"><strong>{col}</strong></td>')
            html_parts.append(f'<td style="padding: 8px; text-align: right; color: #ffc107;"><strong>{var:.1f}%</strong></td>')
            html_parts.append(f'<td style="padding: 8px; text-align: right;">{info.get("reference_mean", 0):,.2f}</td>')
            html_parts.append(f'<td style="padding: 8px; text-align: right;">{info.get("current_mean", 0):,.2f}</td>')
            html_parts.append('</tr>')
        
        html_parts.append('</table>')
        html_parts.append('</div>')
    
    return '\n'.join(html_parts)

def generate_html_dashboard(
    prediction_stats: Dict[str, Any],
    drift_stats: Dict[str, Any]
) -> str:
    """
    Génère un dashboard HTML pour le monitoring.
    """
    
    drift_severity = drift_stats.get("drift_severity", "none")
    
    # Déterminer la couleur et l'icône selon la sévérité
    if drift_severity == "severe":
        drift_color = "danger"
        drift_icon = "🔴"
        drift_message = "ALERTE CRITIQUE - Dérive sévère détectée"
    elif drift_severity == "warning":
        drift_color = "warning"
        drift_icon = "🟠"
        drift_message = "⚠️ ALERTE - Possible dérive légère"
    else:
        drift_color = "success"
        drift_icon = "🟢"
        drift_message = "✅ Stabilité normale"
    
    high_risk = prediction_stats.get("high_risk_count", 0)
    
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Monitoring API - Prêt à Dépenser</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }}
            .dashboard {{ background: white; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); padding: 30px; }}
            .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px; padding: 20px; margin: 10px 0; }}
            .stat-card h6 {{ font-size: 0.9rem; opacity: 0.9; margin-bottom: 10px; }}
            .stat-card .value {{ font-size: 2rem; font-weight: bold; }}
            .alert-badge {{ padding: 5px 10px; border-radius: 20px; font-size: 0.9rem; font-weight: bold; }}
            .drift-section {{ background: #f8f9fa; border-left: 4px solid; padding: 15px; border-radius: 5px; margin-top: 20px; }}
            .drift-section.danger {{ border-left-color: #dc3545; background: #f8d7da; }}
            .drift-section.warning {{ border-left-color: #ffc107; background: #fff3cd; }}
            .drift-section.success {{ border-left-color: #28a745; background: #d4edda; }}
            h2 {{ color: #667eea; margin-bottom: 30px; text-align: center; }}
            .timestamp {{ text-align: center; color: #999; font-size: 0.9rem; margin-top: 20px; }}
            .drift-details {{ margin-top: 15px; font-size: 0.9rem; }}
            .drift-details ul {{ list-style: none; padding-left: 0; }}
            .drift-details li {{ padding: 5px 0; margin: 3px 0; }}
            .drift-col-severe {{ color: #dc3545; font-weight: bold; }}
            .drift-col-mild {{ color: #ffc107; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="dashboard">
                <h2>Dashboard de Monitoring - Scoring API</h2>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="stat-card">
                            <h6>Total Prédictions (Combiné)</h6>
                            <div class="value">{prediction_stats.get('combined_total', 0)}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="stat-card">
                            <h6>Score Moyen Combiné</h6>
                            <div class="value">{(prediction_stats.get('combined_avg_score') or 0):.2%}</div>
                        </div>
                    </div>
                </div>
                
                <h4 style="margin-top: 30px; color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px;">Prédictions Uniques (/predict)</h4>
                <div class="row">
                    <div class="col-md-4">
                        <div class="stat-card">
                            <h6>Total</h6>
                            <div class="value">{prediction_stats.get('single_total', 0)}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="stat-card">
                            <h6>Score Moyen</h6>
                            <div class="value">{(prediction_stats.get('single_avg_score') or 0):.2%}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="stat-card">
                            <h6>Latence Moyenne</h6>
                            <div class="value">{(prediction_stats.get('single_avg_latency_ms') or 0):.2f} ms</div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-4">
                        <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                            <h6>Haut Risque (>60%)</h6>
                            <div class="value">{prediction_stats.get('single_high_risk', 0)}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="stat-card" style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);">
                            <h6>Risque Modéré (45-60%)</h6>
                            <div class="value">{prediction_stats.get('single_medium_risk', 0)}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="stat-card" style="background: linear-gradient(135deg, #30cfd0 0%, #330867 100%);">
                            <h6>Bon Clients (<45%)</h6>
                            <div class="value">{prediction_stats.get('single_low_risk', 0)}</div>
                        </div>
                    </div>
                </div>
                
                <h4 style="margin-top: 30px; color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px;">Prédictions Batch (/multipredict)</h4>
                <div class="row">
                    <div class="col-md-4">
                        <div class="stat-card">
                            <h6>Total</h6>
                            <div class="value">{prediction_stats.get('batch_total', 0)}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="stat-card">
                            <h6>Score Moyen</h6>
                            <div class="value">{(prediction_stats.get('batch_avg_score') or 0):.2%}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="stat-card">
                            <h6>Latence Moyenne</h6>
                            <div class="value">{(prediction_stats.get('batch_avg_latency_ms') or 0):.2f} ms</div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-4">
                        <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                            <h6>Haut Risque (>60%)</h6>
                            <div class="value">{prediction_stats.get('batch_high_risk', 0)}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="stat-card" style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);">
                            <h6>Risque Modéré (45-60%)</h6>
                            <div class="value">{prediction_stats.get('batch_medium_risk', 0)}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="stat-card" style="background: linear-gradient(135deg, #30cfd0 0%, #330867 100%);">
                            <h6>Bon Clients (<45%)</h6>
                            <div class="value">{prediction_stats.get('batch_low_risk', 0)}</div>
                        </div>
                    </div>
                </div>
                </div>
                
                <div class="row" style="margin-top: 20px;">
                    <div class="col-md-6">
                        <h4 style="color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px;">📋 Résumé des Prédictions</h4>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; font-size: 0.9rem;">
                            <p><strong>Prédictions Uniques:</strong> {prediction_stats.get('single_total', 0)}</p>
                            <p><strong>Prédictions Batch:</strong> {prediction_stats.get('batch_total', 0)}</p>
                            <p><strong>Score Moyen Combiné:</strong> {(prediction_stats.get('combined_avg_score') or 0):.2%}</p>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="drift-section {drift_color}">
                            <h5>{drift_icon} Détection de Dérive (Data Drift)</h5>
                            <p><strong>Statut:</strong> 
                                <span class="alert-badge alert-{drift_color}">
                                    {drift_message}
                                </span>
                            </p>
                            <div class="drift-details">
                                <ul>
                                    <li>🔴 <span class="drift-col-severe">Colonnes critiques (>50% variation)</span>: {drift_stats.get('drift_columns_50pct', 0)}</li>
                                    <li>🟠 <span class="drift-col-mild">Colonnes alertes (>30% variation)</span>: {drift_stats.get('drift_columns_30pct', 0)}</li>
                                    <li><strong>Colonnes monitorées : {drift_stats.get('total_monitored', 0)}</strong></li>
                                </ul>
                            </div>
                            
                            {generate_drift_columns_html(drift_stats)}
                            
                            <p style="color: #555; font-size: 0.85rem; margin-top: 10px;">
                                <strong>Seuils de dérive:</strong><br>
                                ✅ Normal: &lt;4 colonnes avec variation &gt;30%<br>
                                ⚠️ Alerte: 4-6 colonnes avec variation &gt;30%<br>
                                🔴 Critique: &gt;6 colonnes OU &gt;2 colonnes avec variation &gt;50%
                            </p>
                        </div>
                    </div>
                </div>
                
                <div class="timestamp">
                    ✅ Mise à jour: {get_local_now().strftime('%Y-%m-%d %H:%M:%S %Z')}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html
