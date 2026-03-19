#!/usr/bin/env powershell
# Script pour executer les tests avec couverture et afficher les rapports

param(
    [switch]$OpenReport = $true,
    [switch]$QuickRun = $false
)

Write-Host ""
Write-Host "---" -ForegroundColor Cyan
Write-Host "                    TESTS UNITAIRES & COUVERTURE                  " -ForegroundColor Cyan
Write-Host "---" -ForegroundColor Cyan
Write-Host ""

# Determiner la commande pytest
if (Test-Path "docker-compose.yml") {
    Write-Host "[Docker] Utilisation de Docker..." -ForegroundColor Green
    $test_cmd = if ($QuickRun) {
        "docker-compose exec -T api pytest tests/ --ignore=tests/test_api.py -q --tb=no"
    } else {
        "docker-compose exec -T api pytest tests/ --ignore=tests/test_api.py -v --tb=short --cov=src --cov=utils --cov-report=term-missing --cov-report=html"
    }
} else {
    Write-Host "[Local] Utilisation du Python local..." -ForegroundColor Green
    $test_cmd = if ($QuickRun) {
        "pytest tests/ --ignore=tests/test_api.py -q --tb=no"
    } else {
        "pytest tests/ --ignore=tests/test_api.py -v --tb=short --cov=src --cov=utils --cov-report=term-missing --cov-report=html"
    }
}

Write-Host ""
Write-Host "[EXECUTION]" -ForegroundColor Yellow
Write-Host "---" -ForegroundColor Gray
Write-Host ""

# Executer les tests
Invoke-Expression $test_cmd

Write-Host ""
Write-Host "---" -ForegroundColor Gray
Write-Host ""

# Verifier si les rapports ont ete generes
if (Test-Path "htmlcov/index.html") {
    Write-Host "[OK] Rapport de couverture genere: htmlcov/index.html" -ForegroundColor Green
    Write-Host ""
    
    if ($OpenReport) {
        Write-Host "[INFO] Ouverture du rapport HTML..." -ForegroundColor Cyan
        Start-Process "htmlcov/index.html"
    } else {
        Write-Host "[TIP] Astuce: Ouvrez htmlcov/index.html dans votre navigateur" -ForegroundColor Gray
    }
} else {
    Write-Host "[WARNING] Aucun rapport de couverture genere (mode rapide?)" -ForegroundColor Yellow
}

Write-Host ""

# Afficher les fichiers de resume
if (Test-Path "TEST_SUMMARY.md") {
    Write-Host "[INFO] Resume des tests:" -ForegroundColor Yellow
    Write-Host "    Voir TEST_SUMMARY.md" -ForegroundColor Gray
}

if (Test-Path "COVERAGE_REPORT.md") {
    Write-Host "[INFO] Rapport de couverture detaille:" -ForegroundColor Yellow
    Write-Host "    Voir COVERAGE_REPORT.md" -ForegroundColor Gray
}

Write-Host ""
Write-Host "---" -ForegroundColor Cyan
Write-Host "                           SUGGESTIONS" -ForegroundColor Cyan
Write-Host "---" -ForegroundColor Cyan
Write-Host ""
Write-Host "[INFO] Consulter les resultats:" -ForegroundColor Green
Write-Host "   1. Ouvrez htmlcov/index.html pour voir la couverture interactive"
Write-Host "   2. Lisez TEST_SUMMARY.md pour un resume"
Write-Host "   3. Lisez COVERAGE_REPORT.md pour l'analyse detaillee"
Write-Host ""
Write-Host "[INFO] Commandes utiles:" -ForegroundColor Green
Write-Host "   # Executer un seul fichier de test"
Write-Host "   pytest tests/test_preprocessing.py -v"
Write-Host ""
Write-Host "   # Executer avec moins verbeux"
Write-Host "   pytest tests/ --ignore=tests/test_api.py -q"
Write-Host ""
Write-Host "   # Executer, montrer les lignes non couvertes"
Write-Host "   pytest tests/ --cov --cov-report=term-missing"
Write-Host ""
Write-Host "---" -ForegroundColor Cyan
Write-Host ""
