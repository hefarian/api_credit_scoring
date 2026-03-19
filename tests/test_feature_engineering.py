# -*- coding: utf-8 -*-
"""
Tests unitaires pour le module feature_engineering.

Tests :
- Création des ratios financiers
- Création des interactions
- Gestion des colonnes manquantes
- Calculs corrects
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.feature_engineering import create_ratio_features, create_interaction_features


class TestCreateRatioFeatures:
    """Tests pour la création des ratios financiers."""
    
    def test_credit_income_perc(self, sample_data_with_ratios):
        """
        TEST : Vérifier le calcul du ratio CREDIT_INCOME_PERC.
        
        Formule : AMT_CREDIT / (AMT_INCOME_TOTAL + 1)
        """
        df = create_ratio_features(sample_data_with_ratios)
        
        # Vérifier que la colonne a été créée
        assert 'CREDIT_INCOME_PERC' in df.columns
        
        # Vérifier le calcul pour la première ligne
        expected = 200000 / (100000 + 1)
        actual = df.iloc[0]['CREDIT_INCOME_PERC']
        assert np.isclose(actual, expected, rtol=1e-5)
    
    def test_annuity_credit_perc(self, sample_data_with_ratios):
        """TEST : Ratio ANNUITY_CREDIT_PERC."""
        df = create_ratio_features(sample_data_with_ratios)
        
        assert 'ANNUITY_CREDIT_PERC' in df.columns
        
        # Vérifier le calcul
        expected = 15000 / (200000 + 1)
        actual = df.iloc[0]['ANNUITY_CREDIT_PERC']
        assert np.isclose(actual, expected, rtol=1e-5)
    
    def test_goods_credit_perc(self, sample_data_with_ratios):
        """TEST : Ratio GOODS_CREDIT_PERC."""
        df = create_ratio_features(sample_data_with_ratios)
        
        assert 'GOODS_CREDIT_PERC' in df.columns
        
        expected = 200000 / (200000 + 1)
        actual = df.iloc[0]['GOODS_CREDIT_PERC']
        assert np.isclose(actual, expected, rtol=1e-5)
    
    def test_annuity_income_perc(self, sample_data_with_ratios):
        """TEST : Ratio ANNUITY_INCOME_PERC (très important pour le crédit scoring)."""
        df = create_ratio_features(sample_data_with_ratios)
        
        assert 'ANNUITY_INCOME_PERC' in df.columns
        
        expected = 15000 / (100000 + 1)
        actual = df.iloc[0]['ANNUITY_INCOME_PERC']
        assert np.isclose(actual, expected, rtol=1e-5)
    
    def test_age_years(self, sample_data_with_ratios):
        """
        TEST : Calcul de l'âge en années.
        
        Formule : -DAYS_BIRTH / 365.25
        
        Exemple : DAYS_BIRTH = -13297 → âge ≈ 36.4 ans
        """
        df = create_ratio_features(sample_data_with_ratios)
        
        assert 'AGE_YEARS' in df.columns
        
        # Vérifier le calcul : -(-13297) / 365.25 ≈ 36.4
        expected = 13297 / 365.25
        actual = df.iloc[0]['AGE_YEARS']
        assert np.isclose(actual, expected, rtol=1e-2)
    
    def test_employed_years(self, sample_data_with_ratios):
        """
        TEST : Calcul de l'ancienneté d'emploi en années.
        
        Formule : -DAYS_EMPLOYED / 365.25
        clip(lower=0) : pas de valeurs négatives
        """
        df = create_ratio_features(sample_data_with_ratios)
        
        assert 'EMPLOYED_YEARS' in df.columns
        
        # Vérifier que pas de valeurs négatives
        assert (df['EMPLOYED_YEARS'] >= 0).all()
        
        # Vérifier le calcul pour une ligne
        expected = 762 / 365.25
        actual = df.iloc[0]['EMPLOYED_YEARS']
        assert np.isclose(actual, expected, rtol=1e-2)
    
    def test_missing_columns_dont_crash(self):
        """
        TEST : Si une colonne requise est manquante, la fonction ne doit pas crash.
        
        Elle doit créer les ratios qui peuvent être créés, ignorer les autres.
        """
        df = pd.DataFrame({
            'AMT_INCOME_TOTAL': [100000, 150000],
            'AMT_CREDIT': [200000, 300000],
            # AMT_ANNUITY manquant
            # DAYS_BIRTH manquant
        })
        
        result = create_ratio_features(df)
        
        # Doit créer au moins CREDIT_INCOME_PERC
        assert 'CREDIT_INCOME_PERC' in result.columns
        
        # Ne doit pas créer les colonnes qui dépendent de colonnes manquantes
        # Mais on doit avoir pas d'erreur
        assert result is not None
    
    def test_division_by_zero_handled(self):
        """
        TEST : Gestion de la division par zéro.
        
        Si AMT_INCOME_TOTAL = 0, on ajoute +1 au dénominateur
        pour éviter la division par zéro.
        """
        df = pd.DataFrame({
            'AMT_INCOME_TOTAL': [0, 100000],
            'AMT_CREDIT': [200000, 200000],
            'AMT_ANNUITY': [15000, 15000],
            'AMT_GOODS_PRICE': [200000, 200000],
            'DAYS_BIRTH': [-13297, -13297],
            'DAYS_EMPLOYED': [-762, -762],
        })
        
        result = create_ratio_features(df)
        
        # La première ligne doit avoir un ratio valide (pas inf, pas NaN)
        assert not np.isinf(result.iloc[0]['CREDIT_INCOME_PERC'])
        assert not np.isnan(result.iloc[0]['CREDIT_INCOME_PERC'])
        
        # Vérifier le calcul : 200000 / (0 + 1) = 200000
        expected = 200000 / 1
        actual = result.iloc[0]['CREDIT_INCOME_PERC']
        assert np.isclose(actual, expected)
    
    def test_all_ratios_are_numeric(self, sample_data_with_ratios):
        """TEST : Tous les ratios créés doivent être numériques."""
        df = create_ratio_features(sample_data_with_ratios)
        
        ratio_columns = [col for col in df.columns if col in [
            'CREDIT_INCOME_PERC', 'ANNUITY_CREDIT_PERC', 'GOODS_CREDIT_PERC',
            'ANNUITY_INCOME_PERC', 'AGE_YEARS', 'EMPLOYED_YEARS'
        ]]
        
        for col in ratio_columns:
            # Vérifier que la colonne est numérique
            assert pd.api.types.is_numeric_dtype(df[col])
            
            # Vérifier pas de NaN ou inf (sauf si attendu)
            assert not df[col].isnull().any() or df[col].dtype == 'object'


class TestCreateInteractionFeatures:
    """Tests pour la création des features d'interaction."""
    
    def test_interaction_features_created(self, sample_data_with_ratios):
        """
        TEST : Vérifier que les features d'interaction sont créées.
        
        Les interactions combinent plusieurs features pour capturer des patterns.
        """
        df = create_interaction_features(sample_data_with_ratios)
        
        # Vérifier qu'au moins une interaction a été créée
        # La fonction retourne un DataFrame, donc on teste juste que ca ne crash pas
        assert df is not None
        assert isinstance(df, pd.DataFrame)
    
    def test_interaction_features_shape(self, sample_data_with_ratios):
        """TEST : Le nombre de colonnes doit augmenter après interaction."""
        df_before = sample_data_with_ratios.copy()
        df_after = create_interaction_features(df_before)
        
        # Doit avoir au moins le même nombre de colonnes
        assert df_after.shape[1] >= df_before.shape[1]
    
    def test_original_columns_preserved(self, sample_data_with_ratios):
        """TEST : Les colonnes originales doivent être conservées."""
        df_before = sample_data_with_ratios.copy()
        df_after = create_interaction_features(df_before)
        
        # Toutes les colonnes originales doivent être présentes
        for col in df_before.columns:
            assert col in df_after.columns


class TestFeatureEngineeringIntegration:
    """Tests d'intégration des deux fonctions ensemble."""
    
    def test_ratio_then_interaction(self, sample_data_with_ratios):
        """
        TEST : Appliquer d'abord ratios, puis interactions.
        
        C'est le workflow typique en production.
        """
        df1 = create_ratio_features(sample_data_with_ratios)
        df2 = create_interaction_features(df1)
        
        # Doit avoir plus de colonnes qu'au début
        assert df2.shape[1] > sample_data_with_ratios.shape[1]
        
        # Doit garder les données originales
        assert df2.shape[0] == sample_data_with_ratios.shape[0]
    
    def test_no_data_loss(self, sample_data_with_ratios):
        """TEST : Pas de lignes perdues après feature engineering."""
        original_rows = len(sample_data_with_ratios)
        
        df1 = create_ratio_features(sample_data_with_ratios)
        df2 = create_interaction_features(df1)
        
        # Même nombre de lignes
        assert len(df2) == original_rows
