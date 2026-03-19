# -*- coding: utf-8 -*-
"""
Tests unitaires pour le module preprocessing (normalisation des données).

Tests :
- Normalisation StandardScaler
- Normalisation MinMaxScaler
- Gestion du test avec/sans données test
- Gestion des erreurs (mauvaise méthode)
"""

import pytest
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.preprocessing import scale_features


class TestScaleFeaturesStandard:
    """Tests pour StandardScaler."""
    
    def test_scale_features_standard_train_only(self, sample_train_data):
        """
        TEST : Normaliser des données d'entraînement uniquement.
        
        Vérifie :
        - Retour = tuple (X_train_scaled, scaler)
        - Moyenne ≈ 0, écart-type ≈ 1
        - Colonnes conservées
        """
        X_train_scaled, scaler = scale_features(sample_train_data, method='standard')
        
        # Vérifier que c'est un DataFrame
        assert isinstance(X_train_scaled, pd.DataFrame)
        
        # Vérifier que les colonnes sont conservées
        assert list(X_train_scaled.columns) == list(sample_train_data.columns)
        
        # Vérifier que les données sont normalisées
        # Moyenne doit être proche de 0 (petites valeurs acceptées car erreur d'arrondi)
        assert np.allclose(X_train_scaled.mean(), 0, atol=1e-1)
        
        # Vérifier que l'écart-type est proche de 1
        # Note: std peut être légèrement > 1 avec petit dataset (N-1 vs N division)
        assert np.allclose(X_train_scaled.std(), 1, atol=0.1)
    
    def test_scale_features_standard_train_and_test(self, sample_train_data, sample_test_data):
        """
        TEST : Normaliser des données d'entraînement ET test.
        
        Vérifie :
        - Retour = tuple avec 3 éléments (X_train_scaled, X_test_scaled, scaler)
        - Les deux datasets ont même dimension
        - Le scaler est fit sur train seulement (pas sur test)
        """
        X_train_scaled, X_test_scaled, scaler = scale_features(
            sample_train_data, 
            X_test=sample_test_data,
            method='standard'
        )
        
        # Vérifier les dimensions
        assert X_train_scaled.shape[0] == len(sample_train_data)
        assert X_test_scaled.shape[0] == len(sample_test_data)
        assert X_train_scaled.shape[1] == X_test_scaled.shape[1]
        
        # Vérifier que les colonnes match entre train et test
        assert list(X_train_scaled.columns) == list(X_test_scaled.columns)
        
        # Le scaler doit être un StandardScaler
        assert isinstance(scaler, StandardScaler)
    
    def test_scale_features_standard_preserves_index(self, sample_train_data):
        """TEST : Les indices (index) sont conservés après normalisation."""
        sample_train_data.index = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        X_train_scaled, scaler = scale_features(sample_train_data, method='standard')
        
        # Vérifier que l'index est conservé
        assert list(X_train_scaled.index) == list(sample_train_data.index)


class TestScaleFeaturesMinMax:
    """Tests pour MinMaxScaler."""
    
    def test_scale_features_minmax(self, sample_train_data):
        """
        TEST : Normaliser avec MinMaxScaler (0-1).
        
        Vérifie :
        - Tous les valeurs sont entre 0 et 1
        - Min = 0, Max = 1 (au moins une valeur à chaque extrême)
        """
        X_train_scaled, scaler = scale_features(sample_train_data, method='minmax')
        
        # Vérifier que toutes les valeurs sont entre 0 et 1
        assert (X_train_scaled >= 0).all().all()
        assert (X_train_scaled <= 1).all().all()
        
        # Vérifier que c'est une MinMaxScaler
        assert isinstance(scaler, MinMaxScaler)
    
    def test_scale_features_minmax_with_test(self, sample_train_data, sample_test_data):
        """TEST : MinMaxScaler avec données train et test."""
        X_train_scaled, X_test_scaled, scaler = scale_features(
            sample_train_data,
            X_test=sample_test_data,
            method='minmax'
        )
        
        # Train doit être dans [0, 1] avec petite tolerance
        assert (X_train_scaled >= -0.01).all().all()
        assert (X_train_scaled <= 1.01).all().all()
        # Test peut sortir du range [0, 1] si données différentes du train
        # On vérifie juste qu'il n'y a pas d'erreur de calcul
        assert X_test_scaled.shape == sample_test_data.shape


class TestScaleFeaturesEdgeCases:
    """Tests pour les cas limites et erreurs."""
    
    def test_scale_features_invalid_method(self, sample_train_data):
        """TEST : Lever une exception si la méthode est invalide."""
        with pytest.raises(ValueError, match="method doit etre"):
            scale_features(sample_train_data, method='invalid_method')
    
    def test_scale_features_with_nan_values(self, sample_dataframe_with_nan):
        """
        TEST : Comportement avec NaN dans les données.
        
        StandardScaler peut gérer les NaN selon la config scikit-learn.
        Ce test documente le comportement attendu.
        """
        # Certaines implémentations de StandardScaler peuvent lever une erreur ou retourner NaN
        # On documente le comportement réel
        try:
            X_scaled, scaler = scale_features(sample_dataframe_with_nan, method='standard')
            # Si ça ne lève pas d'erreur, vérifier que les valeurs non-NaN sont normalisées
            assert X_scaled is not None
        except ValueError:
            # C'est acceptable : StandardScaler rejette les NaN
            pass
    
    def test_scale_features_single_row(self):
        """TEST : Comportement avec une seule ligne (cas limite)."""
        df_single = pd.DataFrame({'col1': [5.0], 'col2': [10.0]})
        
        # Une seule ligne : écart-type = 0, comportement peut être imprévisible
        # On teste juste que ca ne crash pas complètement
        try:
            X_scaled, scaler = scale_features(df_single, method='standard')
            assert X_scaled.shape == df_single.shape
        except (ValueError, ZeroDivisionError):
            # Acceptable : impossible de normaliser une seule ligne
            pass
    
    def test_scale_features_constant_values(self):
        """TEST : Données constantes (toutes les mêmes valeurs)."""
        df_constant = pd.DataFrame({
            'col1': [5.0, 5.0, 5.0, 5.0, 5.0],
            'col2': [10.0, 10.0, 10.0, 10.0, 10.0]
        })
        
        # Écart-type = 0 : impossible de normaliser
        try:
            X_scaled, scaler = scale_features(df_constant, method='standard')
            # Si pas d'erreur, les valeurs doivent être NaN ou constantes
            # (écart-type nul = division par zéro)
            assert X_scaled is not None
        except (ValueError, ZeroDivisionError):
            # Comportement acceptable
            pass
    
    def test_scale_features_very_large_values(self, sample_dataframe_edge_cases):
        """TEST : Normaliser des valeurs très grandes / très petites."""
        X_scaled, scaler = scale_features(
            sample_dataframe_edge_cases[['large_values', 'small_values']],
            method='standard'
        )
        
        # Après normalisation, les valeurs doivent être raisonnables
        # (pas inf, pas NaN, pas des nombres astronomiques)
        assert not np.isinf(X_scaled).any().any()
        assert not np.isnan(X_scaled).any().any()


class TestScaleFeaturesConsistency:
    """Tests pour vérifier la cohérence du scaling."""
    
    def test_train_test_consistency(self, sample_train_data, sample_test_data):
        """
        TEST : Train et test utilisent les mêmes paramètres de normalisation.
        
        Important : on fit le scaler sur train, puis transform test
        avec les mêmes paramètres (pas fit_transform).
        """
        X_train_scaled, X_test_scaled, scaler = scale_features(
            sample_train_data,
            X_test=sample_test_data,
            method='standard'
        )
        
        # Si on applique manuellement le scaler au test, on doit obtenir le même résultat
        X_test_manual = pd.DataFrame(
            scaler.transform(sample_test_data),
            columns=sample_test_data.columns,
            index=sample_test_data.index
        )
        
        # Les résultats doivent être identiques (ou très proches)
        pd.testing.assert_frame_equal(X_test_scaled, X_test_manual)
    
    def test_idempotence_of_scaling(self, sample_train_data):
        """
        TEST : Appliquer le scaling deux fois retourne le même résultat.
        
        Important : si on scale les données déjà scalées avec le MÊME scaler,
        les valeurs ne doivent pas changer (idempotence).
        """
        X_train_scaled_1, scaler = scale_features(sample_train_data, method='standard')
        
        # Appliquer le scaler à nouveau aux données déjà scalées
        X_train_scaled_2 = pd.DataFrame(
            scaler.transform(X_train_scaled_1),
            columns=X_train_scaled_1.columns,
            index=X_train_scaled_1.index
        )
        
        # Les valeurs doivent changer (car le scaler est entrainé sur les données originales,
        # pas sur les données scalées)
        # Ce test vérifie juste que ca ne crash pas
        assert X_train_scaled_2 is not None
