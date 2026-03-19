-- ============================================================================
-- Schema de base de données pour le Credit Scoring API
-- Tables pour logs d'appels, archivage et monitoring
-- ============================================================================

-- Table principale : API_LOGS
-- Enregistre chaque appel à l'API avec inputs, outputs et performance
CREATE TABLE IF NOT EXISTS api_logs (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    client_id INTEGER,
    prediction_type VARCHAR(50) NOT NULL DEFAULT 'single', -- 'single' ou 'batch'
    input_data JSONB NOT NULL,
    score FLOAT8 NOT NULL,
    latency_seconds FLOAT8 NOT NULL,
    cpu_usage_pct FLOAT8,
    gpu_usage_pct FLOAT8,
    gpu_memory_mb FLOAT8,
    compute_device VARCHAR(32) DEFAULT 'cpu',
    error_message TEXT,
    model_version VARCHAR(50) DEFAULT '1.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index sur timestamp pour les requêtes de time-series
CREATE INDEX IF NOT EXISTS idx_api_logs_timestamp ON api_logs(timestamp DESC);
-- Index sur client_id pour les requêtes par client
CREATE INDEX IF NOT EXISTS idx_api_logs_client_id ON api_logs(client_id);
-- Index sur prediction_type pour les filtres
CREATE INDEX IF NOT EXISTS idx_api_logs_prediction_type ON api_logs(prediction_type);
-- Index BRIN pour scan efficace
CREATE INDEX IF NOT EXISTS idx_api_logs_timestamp_brin ON api_logs USING BRIN(timestamp);


-- Table d'archivage : API_LOGS_ARCHIVE
-- Copie historique des logs pour conservation long terme
CREATE TABLE IF NOT EXISTS api_logs_archive (
    archive_id SERIAL PRIMARY KEY,
    log_id INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    client_id INTEGER,
    prediction_type VARCHAR(50) NOT NULL,
    input_data JSONB NOT NULL,
    score FLOAT8 NOT NULL,
    latency_seconds FLOAT8 NOT NULL,
    cpu_usage_pct FLOAT8,
    gpu_usage_pct FLOAT8,
    gpu_memory_mb FLOAT8,
    compute_device VARCHAR(32) DEFAULT 'cpu',
    error_message TEXT,
    model_version VARCHAR(50),
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    archive_reason VARCHAR(255) DEFAULT 'periodic_archive'
);

-- Index sur archive_id et timestamp
CREATE INDEX IF NOT EXISTS idx_api_logs_archive_timestamp ON api_logs_archive(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_logs_archive_archived_at ON api_logs_archive(archived_at DESC);


-- Table de monitoring : DRIFT_DETECTION_RESULTS
-- Enregistre les résultats de détection de dérive
CREATE TABLE IF NOT EXISTS drift_detection_results (
    drift_id SERIAL PRIMARY KEY,
    detection_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_drift_detected BOOLEAN NOT NULL DEFAULT FALSE,
    drift_score FLOAT8,
    affected_features TEXT[], -- Array de noms de features affectées
    details JSONB, -- Détails additionnels (p-values, statistiques, etc.)
    model_version VARCHAR(50),
    action_required BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index pour requêtes chronologiques
CREATE INDEX IF NOT EXISTS idx_drift_detection_timestamp ON drift_detection_results(detection_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_drift_detection_is_drift ON drift_detection_results(is_drift_detected);


-- Table de monitoring : API_PERFORMANCE
-- Résumés de performance (agrégations)
CREATE TABLE IF NOT EXISTS api_performance (
    perf_id SERIAL PRIMARY KEY,
    time_bucket TIMESTAMP WITH TIME ZONE NOT NULL,
    total_requests INTEGER DEFAULT 0,
    avg_latency_seconds FLOAT8,
    min_latency_seconds FLOAT8,
    max_latency_seconds FLOAT8,
    p95_latency_seconds FLOAT8,
    p99_latency_seconds FLOAT8,
    error_count INTEGER DEFAULT 0,
    error_rate FLOAT8, -- pourcentage d'erreurs
    avg_score FLOAT8,
    min_score FLOAT8,
    max_score FLOAT8,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index sur time_bucket
CREATE INDEX IF NOT EXISTS idx_api_performance_time_bucket ON api_performance(time_bucket DESC);


-- Table d'alertes : API_ALERTS
-- Enregistre les anomalies détectées (seuils dépassés, dérives, etc.)
CREATE TABLE IF NOT EXISTS api_alerts (
    alert_id SERIAL PRIMARY KEY,
    alert_type VARCHAR(100) NOT NULL, -- 'latency', 'error_rate', 'drift', 'anomaly'
    severity VARCHAR(50) NOT NULL, -- 'INFO', 'WARNING', 'CRITICAL'
    message TEXT NOT NULL,
    metadata JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index pour les alertes non lues
CREATE INDEX IF NOT EXISTS idx_api_alerts_acknowledged ON api_alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_api_alerts_created_at ON api_alerts(created_at DESC);


-- ============================================================================
-- Vues pour les requêtes courantes
-- ============================================================================

-- Vue: Statistiques des 24 dernières heures
CREATE OR REPLACE VIEW last_24h_stats AS
SELECT 
    COUNT(*) as total_predictions,
    COUNT(CASE WHEN error_message IS NULL THEN 1 END) as successful_predictions,
    COUNT(CASE WHEN error_message IS NOT NULL THEN 1 END) as failed_predictions,
    ROUND(AVG(latency_seconds)::numeric, 4) as avg_latency_seconds,
    MIN(latency_seconds) as min_latency_seconds,
    MAX(latency_seconds) as max_latency_seconds,
    ROUND(AVG(score)::numeric, 4) as avg_score,
    MIN(score) as min_score,
    MAX(score) as max_score,
    ROUND(100.0 * COUNT(CASE WHEN error_message IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0)::numeric, 2) as error_rate_pct
FROM api_logs
WHERE timestamp > NOW() - INTERVAL '24 hours';


-- Vue: Distribution des scores
CREATE OR REPLACE VIEW score_distribution AS
SELECT 
    CASE 
        WHEN score < 0.2 THEN '0.0-0.2 (Very Low Risk)'
        WHEN score < 0.4 THEN '0.2-0.4 (Low Risk)'
        WHEN score < 0.6 THEN '0.4-0.6 (Medium Risk)'
        WHEN score < 0.8 THEN '0.6-0.8 (High Risk)'
        ELSE '0.8-1.0 (Very High Risk)'
    END as risk_bucket,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM api_logs), 0)::numeric, 2) as percentage
FROM api_logs
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY risk_bucket
ORDER BY risk_bucket;


-- Vue: Anomalies potentielles (latence > 95e percentile)
CREATE OR REPLACE VIEW latency_anomalies AS
WITH latency_percentile AS (
    SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_seconds) as p95_latency
    FROM api_logs
    WHERE timestamp > NOW() - INTERVAL '24 hours'
)
SELECT 
    log_id,
    timestamp,
    client_id,
    score,
    latency_seconds,
    (SELECT p95_latency FROM latency_percentile) as p95_latency,
    ROUND(100.0 * (latency_seconds / (SELECT p95_latency FROM latency_percentile))::numeric, 2) as pct_of_p95
FROM api_logs
WHERE latency_seconds > (SELECT p95_latency FROM latency_percentile)
  AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY latency_seconds DESC;


-- ============================================================================
-- Fonctions utiles
-- ============================================================================

-- Fonction pour archiver les logs de plus de X jours
CREATE OR REPLACE FUNCTION archive_old_logs(days_threshold INTEGER DEFAULT 30)
RETURNS TABLE(archived_count INTEGER, archive_date TIMESTAMP WITH TIME ZONE) AS $$
DECLARE
    v_archived_count INTEGER;
    v_cutoff_date TIMESTAMP WITH TIME ZONE;
BEGIN
    v_cutoff_date := NOW() - (days_threshold || ' days')::INTERVAL;
    
    -- Copier vers archive
    INSERT INTO api_logs_archive (log_id, timestamp, client_id, prediction_type, input_data, score, latency_seconds, error_message, model_version, archive_reason)
    SELECT log_id, timestamp, client_id, prediction_type, input_data, score, latency_seconds, error_message, model_version, 'periodic_archive'
    FROM api_logs
    WHERE timestamp < v_cutoff_date
    ON CONFLICT DO NOTHING;
    
    GET DIAGNOSTICS v_archived_count = ROW_COUNT;
    
    -- Supprimer de la table principale
    DELETE FROM api_logs WHERE timestamp < v_cutoff_date;
    
    RETURN QUERY SELECT v_archived_count, CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;


-- Fonction pour nettoyer les alertes anciennes
CREATE OR REPLACE FUNCTION cleanup_old_alerts(days_threshold INTEGER DEFAULT 90)
RETURNS TABLE(deleted_count INTEGER) AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    DELETE FROM api_alerts
    WHERE created_at < NOW() - (days_threshold || ' days')::INTERVAL;
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RETURN QUERY SELECT v_deleted_count;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- Permissions (si utilisateur non-superuser)
-- ============================================================================

-- Créer un utilisateur de base de données pour l'application (facultatif)
-- CREATE USER api_user WITH PASSWORD 'secure_password';
-- GRANT USAGE ON SCHEMA public TO api_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO api_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO api_user;
