#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour exécuter les tests unitaires et générer un rapport de couverture.

Utilise pytest avec coverage pour :
1. Exécuter tous les tests
2. Mesurer la couverture du code
3. Générer un rapport HTML

Installation des dépendances :
    pip install pytest pytest-cov coverage

Utilisation :
    python run_tests_with_coverage.py
    
Le rapport de couverture sera généré en HTML dans htmlcov/index.html
"""

import subprocess
import sys
from pathlib import Path


def run_tests_with_coverage():
    """
    Exécuter les tests avec coverage et générer des rapports.
    
    Cela exécute :
    1. pytest avec coverage pour tous les fichiers src/, utils/, tests/
    2. Génère un rapport terminal
    3. Génère un rapport HTML pour navigation
    """
    
    # Dossier de base
    project_root = Path(__file__).parent
    
    print("=" * 80)
    print("EXÉCUTION DES TESTS AVEC COUVERTURE DE CODE")
    print("=" * 80)
    print()
    
    # Modules à tester
    modules_to_test = [
        "src/preprocessing.py",
        "src/feature_engineering.py",
        "src/metrics.py",
        "src/inference.py",
        "src/monitoring.py",
        "src/monitoring_pg.py",
        "src/database.py",
        "utils/business_cost.py",
        "utils/feature_importance.py",
    ]
    
    print("📋 Modules à tester :")
    for module in modules_to_test:
        print(f"   - {module}")
    print()
    
    # Commande pytest
    cmd = [
        "pytest",
        "tests/",  # Répertoire des tests
        "-v",      # Verbose = affiche chaque test
        "--tb=short",  # Traceback court pour les erreurs
        "--cov=src",   # Coverage pour le répertoire src
        "--cov=utils", # Coverage pour le répertoire utils
        "--cov-report=term-missing",  # Rapport terminal avec lignes non couvertes
        "--cov-report=html",  # Rapport HTML
        "--cov-report=json",  # Rapport JSON (pour traitement automatisé)
    ]
    
    print("🏃 Exécution des tests...")
    print(f"   Commande : {' '.join(cmd)}")
    print()
    
    # Exécuter pytest
    result = subprocess.run(cmd, cwd=str(project_root))
    
    print()
    print("=" * 80)
    if result.returncode == 0:
        print("✅ TOUS LES TESTS SONT PASSÉS")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
    print("=" * 80)
    print()
    
    # Afficher le chemin du rapport HTML
    htmlcov_path = project_root / "htmlcov" / "index.html"
    if htmlcov_path.exists():
        print("📊 RAPPORT DE COUVERTURE")
        print(f"   Consultez le rapport HTML complet :")
        print(f"   {htmlcov_path}")
        print()
        print("   Ouvrez ce fichier dans un navigateur pour voir :")
        print("   - Couverture par fichier")
        print("   - Couverture par fonction")
        print("   - Lignes couvertes / non couvertes")
        print("   - Graphique de couverture")
    
    # Instructions supplémentaires
    print()
    print("📝 INTERPRÉTATION DES RÉSULTATS")
    print("-" * 80)
    print("Couverture (Coverage) :")
    print("  - Lines covered : % de lignes exécutées par les tests")
    print("  - Branches covered : % de chemins d'exécution (if/else) testés")
    print()
    print("Objectifs de couverture recommandés :")
    print("  - 80% : bon couverture général")
    print("  - 90%+ : excellente couverture")
    print("  - 100% : tous les chemins testés (difficile en pratique)")
    print()
    print("Lignes non couvertes (missing lines) :")
    print("  - Affichées avec leur numéro")
    print("  - Généralement : code d'erreur, cas limites, fallback")
    print()
    
    return result.returncode


def run_specific_test_file(test_file):
    """
    Exécuter un seul fichier de test avec coverage.
    
    Args:
        test_file : nom du fichier de test (ex: "test_preprocessing.py")
    """
    cmd = [
        "pytest",
        f"tests/{test_file}",
        "-v",
        "--tb=short",
        "--cov=src",
        "--cov=utils",
        "--cov-report=term-missing",
    ]
    
    print(f"Exécution : {' '.join(cmd)}")
    subprocess.run(cmd)


def generate_coverage_report_only():
    """
    Générer un rapport de couverture à partir des données existantes.
    
    Utile si vous avez déjà exécuté les tests.
    """
    cmd = [
        "coverage",
        "report",  # Rapport terminal
        "-m",      # Afficher les lignes manquantes
    ]
    
    print("Génération du rapport de couverture...")
    subprocess.run(cmd)


if __name__ == "__main__":
    # Interpréter les arguments de la ligne de commande
    if len(sys.argv) > 1:
        if sys.argv[1] == "--file":
            # Exécuter un seul fichier de test
            test_file = sys.argv[2] if len(sys.argv) > 2 else "test_preprocessing.py"
            run_specific_test_file(test_file)
        elif sys.argv[1] == "--report-only":
            # Générer un rapport uniquement
            generate_coverage_report_only()
        elif sys.argv[1] == "--help":
            # Afficher l'aide
            print(__doc__)
    else:
        # Exécuter les tests
        exit_code = run_tests_with_coverage()
        sys.exit(exit_code)
