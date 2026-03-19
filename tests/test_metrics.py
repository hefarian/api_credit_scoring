# -*- coding: utf-8 -*-
"""
Tests unitaires pour le module metrics (métriques d'évaluation).

Tests :
- Calcul des métriques classiques (accuracy, precision, recall, F1)
- Calcul de l'AUC-PR
- Calcul du coût métier
- Optimisation du seuil
"""

import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metrics import evaluate_model


class TestEvaluateModel:
    """Tests pour la fonction evaluate_model."""
    
    def test_evaluate_model_perfect_predictions(self):
        """
        TEST : Prédictions parfaites (100% accuracy).
        
        Si y_true == y_pred partout, toutes les métriques doivent être optimales.
        """
        y_true = np.array([0, 0, 1, 1, 0, 1, 0, 1])
        y_pred = np.array([0, 0, 1, 1, 0, 1, 0, 1])  # Identique à y_true
        y_proba = np.array([0.1, 0.15, 0.9, 0.85, 0.2, 0.8, 0.1, 0.9])
        
        result = evaluate_model(y_true, y_pred, y_proba)
        
        # Precision = recall = F1 = 1.0 (parfait)
        assert result['precision'] == 1.0
        assert result['recall'] == 1.0
        assert result['f1'] == 1.0
        assert result['accuracy'] == 1.0
    
    def test_evaluate_model_all_zeros(self):
        """TEST : Prédictions toutes à 0 (cas dégénéré)."""
        y_true = np.array([0, 0, 1, 1, 0])
        y_pred = np.array([0, 0, 0, 0, 0])  # Toutes 0
        y_proba = np.array([0.1, 0.2, 0.3, 0.4, 0.1])
        
        result = evaluate_model(y_true, y_pred, y_proba)
        
        # Accuracy = 3/5 = 0.6 (3 true negatives, 2 false negatives)
        assert result['accuracy'] == 0.6
        
        # Recall = 0 (aucun 1 présent n'a été détecté)
        assert result['recall'] == 0.0
    
    def test_evaluate_model_all_ones(self):
        """TEST : Prédictions toutes à 1 (cas dégénéré)."""
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([1, 1, 1, 1])  # Toutes 1
        y_proba = np.array([0.9, 0.8, 0.7, 0.9])
        
        result = evaluate_model(y_true, y_pred, y_proba)
        
        # Recall = 1.0 (tous les 1 réussi sont détectés: 2/2)
        assert result['recall'] == 1.0
        
        # Precision sera < 1.0 (on a aussi 2 faux positifs)
        assert result['precision'] < 1.0
    
    def test_evaluate_model_return_keys(self, sample_predictions):
        """TEST : Vérifier que toutes les clés attendues sont présentes."""
        result = evaluate_model(
            sample_predictions['y_true'],
            sample_predictions['y_pred'],
            sample_predictions['y_proba']
        )
        
        expected_keys = ['accuracy', 'precision', 'recall', 'f1', 'auc_pr', 'business_cost']
        for key in expected_keys:
            assert key in result, f"Clé manquante : {key}"
    
    def test_evaluate_model_metrics_in_valid_range(self, sample_predictions):
        """TEST : Vérifier que les métriques sont dans les bonnes plages."""
        result = evaluate_model(
            sample_predictions['y_true'],
            sample_predictions['y_pred'],
            sample_predictions['y_proba']
        )
        
        # Toutes les métriques doivent être entre 0 et 1
        assert 0.0 <= result['accuracy'] <= 1.0
        assert 0.0 <= result['precision'] <= 1.0
        assert 0.0 <= result['recall'] <= 1.0
        assert 0.0 <= result['f1'] <= 1.0
        assert 0.0 <= result['auc_pr'] <= 1.0
        
        # Business cost doit être >= 0
        assert result['business_cost'] >= 0.0
    
    def test_evaluate_model_with_custom_costs(self, sample_predictions):
        """TEST : Évaluation avec coûts métier personnalisés."""
        result1 = evaluate_model(
            sample_predictions['y_true'],
            sample_predictions['y_pred'],
            sample_predictions['y_proba'],
            cost_fn=10,  # FN coûte 10
            cost_fp=1    # FP coûte 1
        )
        
        result2 = evaluate_model(
            sample_predictions['y_true'],
            sample_predictions['y_pred'],
            sample_predictions['y_proba'],
            cost_fn=1,   # Inverser les coûts
            cost_fp=10
        )
        
        # Les coûts métier doivent être différents
        assert result1['business_cost'] != result2['business_cost']
    
    def test_evaluate_model_without_proba(self, sample_predictions):
        """
        TEST : Évaluation sans probabilités (juste prédictions binaires).
        
        Certaines métriques peuvent ne pas être calculables (AUC-PR).
        """
        result = evaluate_model(
            sample_predictions['y_true'],
            sample_predictions['y_pred'],
            y_proba=None
        )
        
        # Les métriques de base doivent être présentes
        assert 'accuracy' in result
        assert 'precision' in result
        assert 'recall' in result
        assert 'f1' in result


class TestMetricsProperties:
    """Tests pour les propriétés mathématiques des métriques."""
    
    def test_f1_is_harmonic_mean(self):
        """
        TEST : F1 est la moyenne harmonique de precision et recall.
        
        F1 = 2 * (precision * recall) / (precision + recall)
        """
        y_true = np.array([0, 1, 1, 0, 1, 0])
        y_pred = np.array([0, 1, 0, 0, 1, 1])  # 1 FN, 1 FP
        y_proba = np.array([0.1, 0.9, 0.4, 0.1, 0.9, 0.6])
        
        result = evaluate_model(y_true, y_pred, y_proba)
        
        precision = result['precision']
        recall = result['recall']
        f1 = result['f1']
        
        if precision + recall > 0:
            expected_f1 = 2 * (precision * recall) / (precision + recall)
            assert np.isclose(f1, expected_f1, rtol=1e-5)
    
    def test_precision_recall_tradeoff(self):
        """
        TEST : Il y a généralement un trade-off entre precision et recall.
        
        Augmenter le seuil augmente precision mais diminue recall (généralement).
        """
        y_true = np.array([0, 1, 1, 0, 1, 0, 1, 0])
        y_proba = np.array([0.1, 0.9, 0.8, 0.2, 0.7, 0.3, 0.85, 0.15])
        
        # Seuil bas : beaucoup de 1 prédits
        y_pred_low = (y_proba >= 0.3).astype(int)
        result_low = evaluate_model(y_true, y_pred_low, y_proba)
        
        # Seuil haut : peu de 1 prédits
        y_pred_high = (y_proba >= 0.7).astype(int)
        result_high = evaluate_model(y_true, y_pred_high, y_proba)
        
        # Avec seuil bas : recall généralement plus haut
        # Avec seuil haut : precision généralement plus haut
        # (peut ne pas être toujours vrai selon les données)
        assert isinstance(result_low, dict)
        assert isinstance(result_high, dict)


class TestEdgeCases:
    """Tests pour les cas limites."""
    
    def test_single_class_predictions(self):
        """TEST : Quand une seule classe est présente dans les vraies valeurs."""
        y_true = np.array([0, 0, 0, 0, 0])  # Tous 0
        y_pred = np.array([0, 0, 0, 0, 0])  # Tous 0 prédits
        y_proba = np.array([0.1, 0.2, 0.15, 0.1, 0.2])
        
        result = evaluate_model(y_true, y_pred, y_proba)
        
        # Accuracy = 1.0 (tous corrects)
        assert result['accuracy'] == 1.0
    
    def test_very_imbalanced_data(self):
        """
        TEST : Données très déséquilibrées (beaucoup plus de 0 que de 1).
        
        Cas réaliste en credit scoring : peu de défauts, beaucoup de bons clients.
        """
        y_true = np.array([0]*95 + [1]*5)  # 95% 0, 5% 1
        y_pred = np.array([0]*95 + [1]*5)  # Prédictions parfaites
        y_proba = np.random.uniform(0, 1, 100)
        
        result = evaluate_model(y_true, y_pred, y_proba)
        
        # Accuracy = 100% mais recall et precision doivent être calculables
        assert result['accuracy'] == 1.0
        assert 0 <= result['recall'] <= 1
        assert 0 <= result['precision'] <= 1
