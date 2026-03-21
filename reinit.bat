@echo off
REM Réinitialisation complète Docker + cache + base PostgreSQL
REM ATTENTION : ce script supprime les volumes Docker du projet, donc la base de données est recréée à zéro.

echo.
echo ========================================
echo REINITIALISATION COMPLETE DU PROJET
echo ========================================
echo Ce script va supprimer :
echo   - les conteneurs du projet
echo   - les volumes Docker du projet (base PostgreSQL incluse)
echo   - les images du projet
echo   - le cache de build Docker
echo.
choice /M "Continuer"
if errorlevel 2 goto :cancel

echo.
echo ========================================
echo ARRET ET SUPPRESSION COMPLETE...
echo ========================================
echo Suppression des conteneurs, reseaux et volumes...
docker-compose down -v --remove-orphans

echo Suppression des images de ce projet...
docker rmi credit_scoring_api credit_scoring_streamlit 2>nul
docker rmi projet08-api projet08-streamlit 2>nul

echo Nettoyage du cache de build Docker...
docker builder prune -f

echo Nettoyage des volumes orphelins Docker...
docker volume prune -f

echo Nettoyage des reseaux orphelins Docker...
docker network prune -f

echo Nettoyage des caches Python locaux...
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "src\__pycache__" rmdir /s /q "src\__pycache__"
if exist "tests\__pycache__" rmdir /s /q "tests\__pycache__"
if exist ".pytest_cache" rmdir /s /q ".pytest_cache"

echo.
echo ========================================
echo RECONSTRUCTION COMPLETE ET REDEMARRAGE...
echo ========================================
docker-compose up -d --build --remove-orphans

echo.
echo ========================================
echo ATTENTE DU DEMARRAGE DE POSTGRESQL...
echo ========================================
timeout /t 8 /nobreak

echo.
echo ========================================
echo VERIFICATION DU STATUT DES CONTENEURS...
echo ========================================
docker-compose ps

echo.
echo ========================================
echo VERIFICATION DE LA CONNEXION POSTGRESQL...
echo ========================================
docker exec credit_scoring_postgres pg_isready -U postgres

echo.
echo ========================================
echo VERIFICATION DU HEALTH DE L'API...
echo ========================================
timeout /t 5 /nobreak
curl.exe http://localhost:8000/health || echo API non prete, patientez...

echo.
echo ========================================
echo REINITIALISATION TERMINEE
echo ========================================
echo Services disponibles:
echo   - API: http://localhost:8000
echo   - Swagger: http://localhost:8000/docs
echo   - Streamlit: http://localhost:8501
echo ========================================
pause
goto :eof

:cancel
echo.
echo Operation annulee.
pause