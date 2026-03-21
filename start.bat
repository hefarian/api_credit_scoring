@echo off
REM Démarrage/Redémarrage de Docker avec purge complète
REM Ce script arrête, supprime TOUT (conteneurs, volumes, networks) et redémarre

echo.
echo ========================================
echo ARRÊT ET REDÉMARRAGE DES SERVICES...
echo ========================================
echo Arrêt et suppression des conteneurs (données préservées)...
docker-compose down --remove-orphans

echo Suppression des images de ce projet...
docker rmi credit_scoring_api credit_scoring_streamlit 2>nul
docker rmi projet08-api projet08-streamlit 2>nul

echo Nettoyage des networks...
docker network rm scoring_network 2>nul

echo.
echo ========================================
echo Reconstruction complète et démarrage...
echo ========================================
docker-compose up -d --build --remove-orphans

echo.
echo ========================================
echo Attente du démarrage de PostgreSQL...
echo ========================================
timeout /t 5 /nobreak

echo.
echo ========================================
echo Vérification du statut des conteneurs...
echo ========================================
docker-compose ps

echo.
echo ========================================
echo Vérification de la connexion PostgreSQL...
echo ========================================
docker exec credit_scoring_postgres pg_isready -U postgres

echo.
echo ========================================
echo Vérification du health de l'API...
echo ========================================
timeout /t 3 /nobreak
curl.exe http://localhost:8000/health || echo API non prête, patientez...

echo.
echo ========================================
echo DÉMARRAGE COMPLÉTÉ !
echo ========================================
echo Services disponibles:
echo   - API: http://localhost:8000
echo   - Swagger: http://localhost:8000/docs
echo   - Streamlit: http://localhost:8501
echo ========================================
pause
