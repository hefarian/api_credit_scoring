# -*- coding: utf-8 -*-
"""
Module de gestion de la base de données PostgreSQL pour l'API de scoring.

C'EST QUOI ? 
===========
Ce module s'occupe de TOUTES les interactions avec la base de données PostgreSQL.
PostgreSQL = système de gestion de base de données (SGBD) = stockage persistent des données

POURQUOI UNE BASE DE DONNÉES ?
==============================
Au lieu de créer des fichiers CSV, on utilise une base de données pour :
1. Stocker les logs de prédictions en temps réel
2. Archiver les logs anciens (tableau séparé pour les données historiques)
3. Récupérer les logs rapidement (avec des filtres, tri, etc.)
4. Permettre plusieurs services (API, dashboard, etc.) d'accéder aux mêmes données
5. Garantir les données ne seront pas perdues (transactions, backups)

TABLES POSTGRESQL
=================
Cette base contient plusieurs tables :

1. api_logs (logs actifs)
   Colonnes : log_id, timestamp, client_id, prediction_type, input_data, 
              score, latency_seconds, error_message, model_version
   Stocke : prédictions récentes (24h, 7 jours, etc.)

2. api_logs_archive (logs archivés)
   Mêmes colonnes que api_logs
   Stocke : prédictions anciennes qu'on veut garder mais pas afficher au dashboard

3. drift_detections (détections de dérive)
   Stocke : chaque fois qu'on détecte une anomalie dans les données

QU'EST-CE QUE CE MODULE FAIT ?
==============================
Gère :
- Connexion à PostgreSQL
- Logging des prédictions (enregistrer chaque prédiction dans la table api_logs)
- Archivage des logs (déplacer les vieux logs vers api_logs_archive)
- Détection de dérive (enregistrer les anomalies)
- Récupération des statistiques (moyennes, totaux, etc.)

COMMENT ÇA MARCHE TECHNIQUEMENT ?
==================================
- SQLAlchemy = bibliothèque pour interroger une BD en Python (plutôt que SQL brut)
- QueuePool = pool de connexions (maintient plusieurs connexions ouvertes pour performance)
- Session = une "conversation" avec la BD (ouvrir, exécuter query, fermer)
"""

import os
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
import logging
from zoneinfo import ZoneInfo

# Importer les composants SQLAlchemy pour la BDD
from sqlalchemy import create_engine, text, and_, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import pandas as pd

logger = logging.getLogger("database")
_prediction_schema_checked = False

# ============================================================================
# FUSEAU HORAIRE LOCAL (GMT+1)
# ============================================================================
LOCAL_TZ = ZoneInfo("Europe/Paris")  # GMT+1 (hiver) / GMT+2 (été)

def get_local_now():
    """
    Retourne l'heure actuelle au fuseau horaire local (GMT+1).
    Remplace datetime.utcnow() pour les logs.
    
    Returns:
        datetime: Datetime avec timezone GMT+1
    """
    return datetime.now(LOCAL_TZ)

# ============================================================================
# CONFIGURATION DE LA CONNEXION À POSTGRESQL
# ============================================================================
# DATABASE_URL = chaîne de connexion au serveur PostgreSQL
# Format : postgresql://utilisateur:motdepasse@serveur:port/base_de_donnees
# 
# os.getenv() = lire une variable d'environnement (définie dans docker-compose.yml)
# Si la variable n'existe pas, utiliser la valeur par défaut (localhost:5432)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/credit_scoring"
)

# ============================================================================
# CRÉER UNE "ENGINE" = MOTEUR DE CONNEXION À LA BD
# ============================================================================
# Engine = gestionnaire de connexions, crée/gère les sessions
# 
# poolclass=QueuePool = maintenir un pool (réservoir) de connexions ouvertes
#   Avantage : plus rapide que créer une nouvelle connexion à chaque fois
# 
# pool_size=5 = nombre de connexions à maintenir ouvertes en permanence
# 
# max_overflow=10 = si on a besoin de plus de 5 connexions, créer jusqu'à 10 temporaires
# 
# pool_pre_ping=True = avant d'utiliser une connexion, vérifier qu'elle est toujours valide
#   (pas fermée par PostgreSQL pendant qu'on ne l'utilisait pas)
# 
# echo=False = ne pas afficher les requêtes SQL générées (serait trop verbeux)
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False
)

# ============================================================================
# CRÉER UNE "SESSION FACTORY" = FABRIQUE DE SESSIONS
# ============================================================================
# SessionLocal = classe qui crée de nouvelles sessions
# 
# autocommit=False = ne pas sauvegarder automatiquement
#   On doit appeler session.commit() manuellement
#   Avantage : si quelque chose échoue, on peut rollback (annuler les changements)
# 
# autoflush=False = ne pas synchroniser automatiquement avec la BD
#   On doit appeler session.flush() manuellement si nécessaire
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db_session() -> Session:
    """
    Fonction utilitaire pour obtenir une nouvelle session de base de données.
    
    Returns:
        Session : une nouvelle session SQLAlchemy prête à être utilisée
    
    Exemple :
        session = get_db_session()
        # faire quelque chose...
        session.close()
    """
    return SessionLocal()


def ensure_prediction_log_schema() -> None:
    """Ajoute les colonnes de ressources si la base existe déjà sans migration."""
    global _prediction_schema_checked

    if _prediction_schema_checked:
        return

    try:
        with engine.begin() as conn:
            conn.execute(text("""
                ALTER TABLE api_logs
                ADD COLUMN IF NOT EXISTS cpu_usage_pct FLOAT8,
                ADD COLUMN IF NOT EXISTS gpu_usage_pct FLOAT8,
                ADD COLUMN IF NOT EXISTS gpu_memory_mb FLOAT8,
                ADD COLUMN IF NOT EXISTS compute_device VARCHAR(32) DEFAULT 'cpu'
            """))
            conn.execute(text("""
                ALTER TABLE api_logs_archive
                ADD COLUMN IF NOT EXISTS cpu_usage_pct FLOAT8,
                ADD COLUMN IF NOT EXISTS gpu_usage_pct FLOAT8,
                ADD COLUMN IF NOT EXISTS gpu_memory_mb FLOAT8,
                ADD COLUMN IF NOT EXISTS compute_device VARCHAR(32) DEFAULT 'cpu'
            """))
        _prediction_schema_checked = True
    except Exception as exc:
        logger.warning("Impossible de vérifier le schéma des logs de prédiction : %s", exc)


def log_prediction_to_db(
    client_id: Optional[int],
    input_data: dict,
    score: float,
    latency_seconds: float,
    prediction_type: str = "single",
    error_message: Optional[str] = None,
    model_version: str = "1.0",
    cpu_usage_pct: Optional[float] = None,
    gpu_usage_pct: Optional[float] = None,
    gpu_memory_mb: Optional[float] = None,
    compute_device: str = "cpu",
) -> bool:
    """
    Enregistre une prédiction dans la table PostgreSQL 'api_logs'.
    
    Cette fonction est appelée APRÈS chaque prédiction pour conserver une trace.
    Permet le monitoring, la détection de dérive, et l'analyse post-hoc.
    
    EXPLICATION DES PARAMÈTRES :
    ============================
    client_id (Optional[int]) :
        ID du client (numéro unique)
        Peut être None si l'ID n'est pas disponible
    
    input_data (dict) :
        Dictionnaire des données D'ENTRÉE que le client a fourni
        Exemple : {"age": 45, "revenu": 50000, "credit": 200000}
        Sera sauvegardé en JSON dans la BD
    
    score (float) :
        Probabilité de défaut retournée par le modèle
        Entre 0 (très bon client) et 1 (très mauvais client)
    
    latency_seconds (float) :
        Temps que la prédiction a pris (secondes)
        Important pour monitoring des performances
        Si > 1 seconde, algo est trop lent
    
    prediction_type (str, optional, default="single") :
        'single' = une prédiction pour un client
        'batch' = plusieurs prédictions en même temps
    
    error_message (Optional[str], optional, default=None) :
        Si la prédiction a échoué, message d'erreur
        None = pas d'erreur (prédiction réussie)
    
    model_version (str, optional, default="1.0") :
        Version du modèle qui a fait la prédiction
        Permet de savoir quel modèle a été utilisé
        Utile si on entraîne une nouvelle version plus tard
    
    RETOUR :
    ========
    bool : True si enregistrement réussi, False sinon
    
    EXEMPLE :
    =========
    success = log_prediction_to_db(
        client_id=12345,
        input_data={"age": 45, "revenu": 50000},
        score=0.35,
        latency_seconds=0.045,
        prediction_type="single",
        error_message=None,
        model_version="1.0"
    )
    if success:
        print("Prédiction enregistrée!")
    else:
        print("Erreur lors de l'enregistrement")
    """
    try:
        ensure_prediction_log_schema()
        session = get_db_session()
        
        query = text("""
            INSERT INTO api_logs 
            (
                timestamp,
                client_id,
                prediction_type,
                input_data,
                score,
                latency_seconds,
                error_message,
                model_version,
                cpu_usage_pct,
                gpu_usage_pct,
                gpu_memory_mb,
                compute_device
            )
            VALUES 
            (
                :timestamp,
                :client_id,
                :prediction_type,
                :input_data,
                :score,
                :latency_seconds,
                :error_message,
                :model_version,
                :cpu_usage_pct,
                :gpu_usage_pct,
                :gpu_memory_mb,
                :compute_device
            )
        """)
        
        session.execute(query, {
            "timestamp": get_local_now(),
            "client_id": client_id,
            "prediction_type": prediction_type,
            "input_data": json.dumps(input_data),
            "score": score,
            "latency_seconds": latency_seconds,
            "error_message": error_message,
            "model_version": model_version,
            "cpu_usage_pct": cpu_usage_pct,
            "gpu_usage_pct": gpu_usage_pct,
            "gpu_memory_mb": gpu_memory_mb,
            "compute_device": compute_device,
        })
        
        session.commit()
        session.close()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de la prédiction : {str(e)}")
        try:
            session.close()
        except:
            pass
        return False


def get_logs_as_dataframe(
    last_n_hours: int = 24,
    limit: Optional[int] = None
) -> Optional[pd.DataFrame]:
    """
    Récupère les logs des N dernières heures sous forme de DataFrame pandas.
    
    Très utile pour l'analyse : pandas DataFrame = structure tabulaire
    qu'on peut filtrer, trier, visualiser facilement.
    
    EXPLICATION :
    =============
    Une prédiction très récente (< 1 heure) = importante, l'afficher au dashboard
    Une prédiction très vieille (> 7 jours) = peut être archivée
    
    Cette fonction permet de récupérer juste les logs "actifs" (récents).
    Les très vieux logs sont dans la table api_logs_archive (archivés).
    
    PARAMÈTRES :
    ===========
    last_n_hours (int, default=24) :
        Récupérer les logs des N dernières heures
        Exemple : 24 = dernier jour, 168 = dernière semaine
    
    limit (Optional[int], default=None) :
        Maximum de lignes à retourner
        None = pas de limite
        Exemple : limit=100 = retourner les 100 plus récents
    
    RETOUR :
    ========
    DataFrame pandas avec colonnes :
    - log_id : clé primaire
    - timestamp : quand la prédiction a eu lieu
    - client_id : qui a demandé la prédiction
    - prediction_type : 'single' ou 'batch'
    - input_data : les données d'entrée (JSON)
    - score : le score de prédiction
    - latency_seconds : temps d'exécution
    - error_message : erreur si applicable
    - model_version : version du modèle
    
    Retourne None si :
    - Erreur de connexion à la BD
    - Aucun log trouvé
    
    EXEMPLE :
    =========
    # Récupérer les 100 prédictions des 24 dernières heures
    df = get_logs_as_dataframe(last_n_hours=24, limit=100)
    if df is not None:
        print(f"{len(df)} prédictions trouvées")
        print(df[['timestamp', 'score']])  # Afficher timestamp et score
    else:
        print("Pas de logs trouvés")
    """
    try:
        ensure_prediction_log_schema()
        session = get_db_session()
        
        query = text("""
            SELECT 
                log_id,
                timestamp,
                client_id,
                prediction_type,
                input_data,
                score,
                latency_seconds,
                error_message,
                model_version,
                cpu_usage_pct,
                gpu_usage_pct,
                gpu_memory_mb,
                compute_device
            FROM api_logs
            WHERE timestamp > NOW() - INTERVAL ':hours hours'
            ORDER BY timestamp DESC
        """).bindparams(hours=last_n_hours)
        
        if limit:
            query = text(f"""
                SELECT 
                    log_id,
                    timestamp,
                    client_id,
                    prediction_type,
                    input_data,
                    score,
                    latency_seconds,
                    error_message,
                    model_version,
                    cpu_usage_pct,
                    gpu_usage_pct,
                    gpu_memory_mb,
                    compute_device
                FROM api_logs
                WHERE timestamp > NOW() - INTERVAL '{last_n_hours} hours'
                ORDER BY timestamp DESC
                LIMIT {limit}
            """)
        
        result = session.execute(query)
        
        # Convertir en DataFrame
        columns = [
            "log_id",
            "timestamp",
            "client_id",
            "prediction_type",
            "input_data",
            "score",
            "latency_seconds",
            "error_message",
            "model_version",
            "cpu_usage_pct",
            "gpu_usage_pct",
            "gpu_memory_mb",
            "compute_device",
        ]
        rows = result.fetchall()
        
        if not rows:
            return None
        
        df = pd.DataFrame(rows, columns=columns)
        session.close()
        
        # Parser les JSONs
        df['input_data'] = df['input_data'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
        
        return df
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs : {str(e)}")
        try:
            session.close()
        except:
            pass
        return None


def get_prediction_stats(last_n_hours: int = 24) -> Dict:
    """
    Calcule les statistiques agrégées des prédictions.
    
    Utile pour le dashboard : afficher des KPIs (Key Performance Indicators)
    
    EXPLICATION :
    =============
    Au lieu d'afficher chaque prédiction individuellement, on affiche des résumés :
    - Combien de prédictions au total ?
    - Quel est le score moyen ?
    - Entre quels scores varie-t-on ?
    - Quelle est la performance de l'API (temps moyen) ?
    
    PARAMÈTRE :
    ===========
    last_n_hours (int, default=24) :
        Calculer les stats sur les prédictions des N dernières heures
    
    RETOUR :
    ========
    Dict avec clés :
    - total_predictions : nombre de prédictions
    - avg_score : score moyen (entre 0 et 1)
    - min_score : score minimal
    - max_score : score maximal
    - std_score : écart-type des scores (variabilité)
    - avg_latency_ms : temps moyen en millisecondes
    - success_rate : % de prédictions qui ont réussi (sans erreur)
    - error_count : nombre d'erreurs
    
    EXEMPLE :
    =========
    stats = get_prediction_stats(last_n_hours=24)
    print(f"Prédictions aujourd'hui : {stats['total_predictions']}")
    print(f"Score moyen : {stats['avg_score']:.3f}")
    print(f"Temps moyen : {stats['avg_latency_ms']:.1f}ms")
    """
    try:
        ensure_prediction_log_schema()
        session = get_db_session()
        
        query = text(f"""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN error_message IS NULL THEN 1 END) as successful,
                COUNT(CASE WHEN error_message IS NOT NULL THEN 1 END) as failed,
                AVG(score) as avg_score,
                MIN(score) as min_score,
                MAX(score) as max_score,
                AVG(latency_seconds) as avg_latency,
                MIN(latency_seconds) as min_latency,
                MAX(latency_seconds) as max_latency,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_seconds) as p95_latency,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_seconds) as p99_latency,
                AVG(cpu_usage_pct) as avg_cpu_usage_pct,
                MAX(cpu_usage_pct) as max_cpu_usage_pct,
                AVG(gpu_usage_pct) as avg_gpu_usage_pct,
                MAX(gpu_usage_pct) as max_gpu_usage_pct,
                AVG(gpu_memory_mb) as avg_gpu_memory_mb
            FROM api_logs
            WHERE timestamp > NOW() - INTERVAL '{last_n_hours} hours'
        """)
        
        result = session.execute(query).fetchone()
        session.close()
        
        if result:
            return {
                "total": result[0] or 0,
                "successful": result[1] or 0,
                "failed": result[2] or 0,
                "avg_score": float(result[3]) if result[3] else 0.0,
                "min_score": float(result[4]) if result[4] else 0.0,
                "max_score": float(result[5]) if result[5] else 0.0,
                "avg_latency_seconds": float(result[6]) if result[6] else 0.0,
                "min_latency_seconds": float(result[7]) if result[7] else 0.0,
                "max_latency_seconds": float(result[8]) if result[8] else 0.0,
                "p95_latency_seconds": float(result[9]) if result[9] else 0.0,
                "p99_latency_seconds": float(result[10]) if result[10] else 0.0,
                "avg_cpu_usage_pct": float(result[11]) if result[11] is not None else 0.0,
                "max_cpu_usage_pct": float(result[12]) if result[12] is not None else 0.0,
                "avg_gpu_usage_pct": float(result[13]) if result[13] is not None else 0.0,
                "max_gpu_usage_pct": float(result[14]) if result[14] is not None else 0.0,
                "avg_gpu_memory_mb": float(result[15]) if result[15] is not None else 0.0,
                "error_rate_pct": round(100.0 * (result[2] or 0) / ((result[0] or 1)), 2)
            }
        
        return {}
        
    except Exception as e:
        logger.error(f"Erreur lors du calcul des statistiques : {str(e)}")
        return {}


def archive_logs(days_to_archive: int = 30) -> Dict:
    """
    Archive les logs dans la table d'archive.
    
    Args:
        days_to_archive: Archiver les logs de plus de N jours (0 = archiver TOUT)
    
    Returns:
        Dict avec informations sur l'archivage
    """
    try:
        ensure_prediction_log_schema()
        session = get_db_session()
        
        # Construire la condition WHERE selon le paramètre
        if days_to_archive == 0:
            # Archiver TOUS les logs
            where_condition = "1=1"
        else:
            # Archiver seulement les logs de plus de N jours
            where_condition = f"timestamp < NOW() - INTERVAL '{days_to_archive} days'"
        
        # Copier vers archive
        insert_query = text(f"""
            INSERT INTO api_logs_archive 
            (
                log_id,
                timestamp,
                client_id,
                prediction_type,
                input_data,
                score,
                latency_seconds,
                error_message,
                model_version,
                cpu_usage_pct,
                gpu_usage_pct,
                gpu_memory_mb,
                compute_device,
                archive_reason
            )
            SELECT
                log_id,
                timestamp,
                client_id,
                prediction_type,
                input_data,
                score,
                latency_seconds,
                error_message,
                model_version,
                cpu_usage_pct,
                gpu_usage_pct,
                gpu_memory_mb,
                compute_device,
                'manual_archive'
            FROM api_logs
            WHERE {where_condition}
            ON CONFLICT DO NOTHING
        """)
        
        result = session.execute(insert_query)
        archived_count = result.rowcount
        session.commit()
        
        # Supprimer de la table principale
        delete_query = text(f"""
            DELETE FROM api_logs
            WHERE {where_condition}
        """)
        
        result = session.execute(delete_query)
        deleted_count = result.rowcount
        session.commit()
        
        session.close()
        
        return {
            "status": "success",
            "archived_count": archived_count,
            "deleted_count": deleted_count,
            "timestamp": get_local_now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'archivage : {str(e)}")
        try:
            session.close()
        except:
            pass
        return {"status": "error", "detail": str(e)}


def create_alert(alert_type: str, severity: str, message: str, metadata: Optional[Dict] = None) -> bool:
    """
    Crée une alerte dans la base de données.
    
    Args:
        alert_type: Type d'alerte ('latency', 'error_rate', 'drift', 'anomaly')
        severity: Sévérité ('INFO', 'WARNING', 'CRITICAL')
        message: Message d'alerte
        metadata: Métadonnées additionnelles
    
    Returns:
        bool: True si succès
    """
    try:
        session = get_db_session()
        
        query = text("""
            INSERT INTO api_alerts 
            (alert_type, severity, message, metadata)
            VALUES 
            (:alert_type, :severity, :message, :metadata)
        """)
        
        session.execute(query, {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "metadata": json.dumps(metadata) if metadata else None
        })
        
        session.commit()
        session.close()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la création d'alerte : {str(e)}")
        try:
            session.close()
        except:
            pass
        return False


def record_drift_detection(
    is_drift_detected: bool,
    drift_score: Optional[float] = None,
    affected_features: Optional[List[str]] = None,
    details: Optional[Dict] = None,
    model_version: str = "1.0"
) -> bool:
    """
    Enregistre un résultat de détection de dérive.
    
    Args:
        is_drift_detected: Booléen indiquant si drift est détecté
        drift_score: Score de drift
        affected_features: Liste des features affectées
        details: Détails additionnels
        model_version: Version du modèle
    
    Returns:
        bool: True si succès
    """
    try:
        session = get_db_session()
        
        query = text("""
            INSERT INTO drift_detection_results 
            (is_drift_detected, drift_score, affected_features, details, model_version, action_required)
            VALUES 
            (:is_drift_detected, :drift_score, :affected_features, :details, :model_version, :action_required)
        """)
        
        session.execute(query, {
            "is_drift_detected": is_drift_detected,
            "drift_score": drift_score,
            "affected_features": affected_features,
            "details": json.dumps(details) if details else None,
            "model_version": model_version,
            "action_required": is_drift_detected
        })
        
        session.commit()
        session.close()
        
        # Si drift détecté, créer une alerte
        if is_drift_detected:
            create_alert(
                alert_type="drift",
                severity="CRITICAL",
                message=f"Data drift detected with score {drift_score:.4f}",
                metadata={
                    "affected_features": affected_features,
                    "drift_score": drift_score,
                    "model_version": model_version
                }
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de drift : {str(e)}")
        try:
            session.close()
        except:
            pass
        return False


def get_recent_alerts(limit: int = 10, unacknowledged_only: bool = False) -> List[Dict]:
    """
    Récupère les alertes récentes.
    
    Args:
        limit: Nombre d'alertes à récupérer
        unacknowledged_only: Si True, retourne uniquement les alertes non confirmées
    
    Returns:
        Liste des alertes
    """
    try:
        session = get_db_session()
        
        where_clause = ""
        if unacknowledged_only:
            where_clause = "WHERE acknowledged = FALSE"
        
        query = text(f"""
            SELECT 
                alert_id,
                alert_type,
                severity,
                message,
                metadata,
                acknowledged,
                created_at
            FROM api_alerts
            {where_clause}
            ORDER BY created_at DESC
            LIMIT {limit}
        """)
        
        result = session.execute(query)
        
        alerts = []
        for row in result.fetchall():
            alerts.append({
                "alert_id": row[0],
                "alert_type": row[1],
                "severity": row[2],
                "message": row[3],
                "metadata": json.loads(row[4]) if row[4] else None,
                "acknowledged": row[5],
                "created_at": row[6].isoformat() if row[6] else None
            })
        
        session.close()
        return alerts
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des alertes : {str(e)}")
        return []


def acknowledge_alert(alert_id: int) -> bool:
    """
    Marque une alerte comme confirmée.
    
    Args:
        alert_id: ID de l'alerte
    
    Returns:
        bool: True si succès
    """
    try:
        session = get_db_session()
        
        query = text("""
            UPDATE api_alerts
            SET acknowledged = TRUE, updated_at = NOW()
            WHERE alert_id = :alert_id
        """)
        
        session.execute(query, {"alert_id": alert_id})
        session.commit()
        session.close()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la confirmation d'alerte : {str(e)}")
        try:
            session.close()
        except:
            pass
        return False


def test_connection() -> bool:
    """
    Test la connexion à la base de données.
    
    Returns:
        bool: True si connexion réussie
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("PostgreSQL connection successful")
            return True
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {str(e)}")
        return False
