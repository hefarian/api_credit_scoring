@echo off
REM Script de déploiement local avec gestion des environnements (Windows/PowerShell)

setlocal enabledelayedexpansion

set ENV=%1
if "!ENV!"=="" set ENV=dev

echo Deployment environment: !ENV!

if not exist ".env.!ENV!" (
    echo File .env.!ENV! not found!
    exit /b 1
)

echo Using environment file: .env.!ENV!

REM Load environment variables from file
for /f "tokens=* usebackq" %%i in (".env.!ENV!") do (
    if not "%%i"=="" (
        if not "%%i:~0,1%"=="#" (
            set %%i
        )
    )
)

set COMPOSE_PROJECT_NAME=credit-scoring-!ENV!

echo Project name: !COMPOSE_PROJECT_NAME!

REM Deploy with docker compose
docker compose --file docker-compose.yml ^
    --project-name !COMPOSE_PROJECT_NAME! ^
    --env-file ".env.!ENV!" ^
    up -d --build

echo Deployment completed for environment: !ENV!
docker compose -p !COMPOSE_PROJECT_NAME! ps

endlocal
