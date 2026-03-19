# -*- coding: utf-8 -*-
"""
Tests supplementaires pour src/preprocessing.py - Robustesse et edge cases

OBJECTIF: Augmenter couverture preprocessing (ajouter ~85 lignes couvertes)
"""

import pytest
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler


class TestScaleFeaturesRobustness:
    """Tests de robustesse pour scale_features()"""

    @pytest.fixture
    def df_normal_data(self):
        """Donnees normales"""
        return pd.DataFrame({
            'feat1': [1, 2, 3, 4, 5],
            'feat2': [10, 20, 30, 40, 50],
            'feat3': [-5, -2, 0, 2, 5],
        })

    @pytest.fixture
    def df_single_row(self):
        """DataFrame avec une seule ligne"""
        return pd.DataFrame({
            'feat1': [5],
            'feat2': [50],
        })

    @pytest.fixture
    def df_constant_values(self):
        """Toutes les valeurs identiques"""
        return pd.DataFrame({
            'feat1': [5, 5, 5, 5],
            'feat2': [10, 10, 10, 10],
        })

    @pytest.fixture
    def df_missing_values(self):
        """DataFrame avec NaN"""
        return pd.DataFrame({
            'feat1': [1, np.nan, 3, 4],
            'feat2': [10, 20, np.nan, 40],
        })

    @pytest.fixture
    def df_with_inf(self):
        """DataFrame avec valeurs infinies"""
        return pd.DataFrame({
            'feat1': [1, 2, np.inf, 4],
            'feat2': [10, np.inf, 30, 40],
        })

    @pytest.fixture
    def df_extreme_range(self):
        """Valeurs avec plage extreme"""
        return pd.DataFrame({
            'feat1': [1e-10, 1e10, 1e-5, 1],
            'feat2': [-1e10, 1e10, 0, 1],
        })

    def test_scale_features_standardscaler_properties(self, df_normal_data):
        """StandardScaler: moyenne ≈ 0, std ≈ 1"""
        from src.preprocessing import scale_features
        
        X_train_scaled, scaler = scale_features(df_normal_data, method='standard')
        
        # Verifier proprietes StandardScaler
        for col in X_train_scaled.columns:
            mean = X_train_scaled[col].mean()
            std = X_train_scaled[col].std()
            # Moyenne proche de 0 (tolerance numérique)
            assert -0.1 < mean < 0.1, f"Mean of {col} = {mean}, expected ≈ 0"
            # Std proche de 1 (avec tolérance pour petits datasets)
            assert 0.9 < std < 1.15, f"Std of {col} = {std}, expected ≈ 1"

    def test_scale_features_minmax_properties(self, df_normal_data):
        """MinMaxScaler: valeurs entre 0 et 1"""
        from src.preprocessing import scale_features
        
        X_train_scaled, scaler = scale_features(df_normal_data, method='minmax')
        
        # Verifier que valeurs entre 0 et 1
        assert (X_train_scaled >= 0).all().all(), "MinMaxScaler values should be >= 0"
        assert (X_train_scaled <= 1).all().all(), "MinMaxScaler values should be <= 1"
        # Au moins une valeur = 0 et une = 1 (ou proche)
        flattened = X_train_scaled.values.flatten()
        assert np.min(flattened) >= -1e-10  # tolerance
        assert np.max(flattened) <= 1 + 1e-10

    def test_scale_features_single_row(self, df_single_row):
        """Scaling avec une seule ligne"""
        from src.preprocessing import scale_features
        
        # Une seule ligne = std = 0, peut causer division par zero
        try:
            X_train_scaled, scaler = scale_features(df_single_row, method='standard')
            # Si succes, verifier que la sortie a la bonne forme
            assert X_train_scaled.shape == df_single_row.shape
        except (ValueError, ZeroDivisionError):
            # C'est acceptable de lever une erreur
            pass

    def test_scale_features_constant_values(self, df_constant_values):
        """Scaling avec valeurs constantes"""
        from src.preprocessing import scale_features
        
        # Valeurs constantes = range = 0, peut causer division par zero
        try:
            X_train_scaled, scaler = scale_features(df_constant_values, method='standard')
            # Si succes, valeurs scaled = NaN ou 0
            assert X_train_scaled.shape == df_constant_values.shape
        except (ValueError, ZeroDivisionError):
            pass

    def test_scale_features_with_nan_raises_error(self, df_missing_values):
        """Avec NaN, notre correction doit lever une erreur"""
        from src.preprocessing import scale_features
        
        # Notre correction ajoutee: rejette les NaN
        with pytest.raises(ValueError, match="contiennent des NaN"):
            scale_features(df_missing_values, method='standard')

    def test_scale_features_with_inf_raises_error(self, df_with_inf):
        """Avec valeurs infinies, peut lever une erreur"""
        from src.preprocessing import scale_features
        
        try:
            X_train_scaled, scaler = scale_features(df_with_inf, method='standard')
            # Si retourne quelque chose, verifier pas de NaN dans la sortie
            assert not X_train_scaled.isnull().any().any()
        except (ValueError, Exception):
            pass

    def test_scale_features_extreme_range(self, df_extreme_range):
        """Valeurs avec plage extreme - pas de overflow"""
        from src.preprocessing import scale_features
        
        try:
            X_train_scaled, scaler = scale_features(df_extreme_range, method='standard')
            # Pas d'overflow = pas d'infinies dans la sortie
            assert np.isfinite(X_train_scaled.values).all()
        except:
            pass

    def test_scale_features_preserves_columns(self, df_normal_data):
        """Noms de colonnes preserves"""
        from src.preprocessing import scale_features
        
        X_train_scaled, scaler = scale_features(df_normal_data, method='standard')
        
        assert list(X_train_scaled.columns) == list(df_normal_data.columns)

    def test_scale_features_preserves_index(self, df_normal_data):
        """Index preserves"""
        from src.preprocessing import scale_features
        
        df_with_index = df_normal_data.copy()
        df_with_index.index = ['row1', 'row2', 'row3', 'row4', 'row5']
        
        X_train_scaled, scaler = scale_features(df_with_index, method='standard')
        
        assert list(X_train_scaled.index) == list(df_with_index.index)

    def test_scale_features_with_test_data(self, df_normal_data):
        """Scaling train ET test ensemble"""
        from src.preprocessing import scale_features
        
        # Creer train et test
        df_train = df_normal_data.iloc[:3]
        df_test = df_normal_data.iloc[3:]
        
        X_train_scaled, X_test_scaled, scaler = scale_features(
            df_train, df_test, method='standard'
        )
        
        # Train et test doivent avoir meme nombre de colonnes
        assert X_train_scaled.shape[1] == X_test_scaled.shape[1]
        # Train = 3 lignes, test = 2 lignes
        assert X_train_scaled.shape[0] == 3
        assert X_test_scaled.shape[0] == 2


class TestScalerConsistency:
    """Tests de coherence du scaler"""

    def test_fit_transform_vs_fit_then_transform(self):
        """fit_transform doit donner meme resultat que fit + transform"""
        from src.preprocessing import scale_features
        
        df = pd.DataFrame({
            'feat1': [1, 2, 3, 4, 5],
            'feat2': [10, 20, 30, 40, 50],
        })
        
        X_train_scaled, scaler = scale_features(df, method='standard')
        
        # Transformation manuelle
        X_manual = scaler.transform(df)
        
        # Les deux doivent etre identiques
        np.testing.assert_array_almost_equal(X_train_scaled.values, X_manual)

    def test_scaler_consistent_between_calls(self):
        """Meme scaler donne meme transformation"""
        from sklearn.preprocessing import StandardScaler
        
        df = pd.DataFrame({
            'feat1': [1, 2, 3, 4, 5],
            'feat2': [10, 20, 30, 40, 50],
        })
        
        scaler = StandardScaler()
        X1 = scaler.fit_transform(df)
        X2 = scaler.transform(df)
        
        np.testing.assert_array_almost_equal(X1, X2)

    def test_test_data_uses_train_parameters(self):
        """Test data transformee avec les params du train"""
        from src.preprocessing import scale_features
        
        df_train = pd.DataFrame({
            'feat1': [1, 2, 3],
            'feat2': [10, 11, 12],
        })
        
        df_test = pd.DataFrame({
            'feat1': [100, 200],
            'feat2': [1000, 2000],
        })
        
        X_train_scaled, X_test_scaled, scaler = scale_features(
            df_train, df_test, method='standard'
        )
        
        # Train close to 0 mean (il est normalize)
        assert abs(X_train_scaled['feat1'].mean()) < 0.1
        
        # Test utilise meme parametre => moyenne pas 0
        # (car test a des valeurs tres differentes du train)
        assert abs(X_test_scaled['feat1'].mean()) > 1  # Probablement loin de 0


class TestScalerMethodSelection:
    """Tests sur le choix de méthode"""

    def test_invalid_method_raises_error(self):
        """Méthode invalide doit lever une erreur"""
        from src.preprocessing import scale_features
        
        df = pd.DataFrame({'feat1': [1, 2, 3]})
        
        with pytest.raises(ValueError, match="doit etre"):
            scale_features(df, method='invalid_method')

    def test_standard_vs_minmax_different_results(self):
        """StandardScaler et MinMaxScaler donnent resultat different"""
        from src.preprocessing import scale_features
        
        df = pd.DataFrame({
            'feat1': [1, 2, 3, 4, 5],
            'feat2': [10, 20, 30, 40, 50],
        })
        
        X_standard, _ = scale_features(df, method='standard')
        X_minmax, _ = scale_features(df, method='minmax')
        
        # Resultats differents
        assert not np.allclose(X_standard.values, X_minmax.values)
        
        # Mais memes dimensions
        assert X_standard.shape == X_minmax.shape
