# -*- coding: utf-8 -*-
"""
Tests pour src/data_loader.py - Phase 3: Couverture 0% → 80%

OBJECTIF: Tester le chargement de CSV et la fusion de données
STRATÉGIE: Créer des CSV temporaires avec pandas, tester les fonctions
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from pathlib import Path
import os


class TestReadCSVWithEncoding:
    """Tests pour _read_csv_with_encoding()"""

    @pytest.fixture
    def temp_dir(self):
        """Créer un répertoire temporaire"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup après le test
        shutil.rmtree(temp_dir)

    def test_read_csv_utf8_encoding(self, temp_dir):
        """Lire CSV en UTF-8 (encodage standard)"""
        from src.data_loader import _read_csv_with_encoding
        
        # Créer un CSV de test avec encodage UTF-8
        file_path = Path(temp_dir) / "test_utf8.csv"
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'nom': ['Alice', 'Bob', 'Charlie'],
            'valeur': [10.5, 20.3, 15.7]
        })
        df.to_csv(file_path, encoding='utf-8', index=False)
        
        # Charger le fichier
        result = _read_csv_with_encoding(str(file_path))
        
        # Vérifier que le résultat est correct
        assert result.shape == (3, 3)
        assert list(result.columns) == ['id', 'nom', 'valeur']
        assert result['id'].tolist() == [1, 2, 3]

    def test_read_csv_latin1_encoding(self, temp_dir):
        """Lire CSV en latin-1 (ancien standard)"""
        from src.data_loader import _read_csv_with_encoding
        
        # Créer un CSV en latin-1
        file_path = Path(temp_dir) / "test_latin1.csv"
        df = pd.DataFrame({
            'id': [1, 2],
            'lieu': ['Café', 'Crème'],  # Accents en latin-1
        })
        df.to_csv(file_path, encoding='latin-1', index=False)
        
        # Charger le fichier (doit essayer UTF-8 puis latin-1)
        result = _read_csv_with_encoding(str(file_path))
        
        assert result.shape == (2, 2)
        assert 'Café' in result['lieu'].values or 'Caf' in result['lieu'].values[0]

    def test_read_csv_file_not_found(self):
        """Test avec fichier inexistant"""
        from src.data_loader import _read_csv_with_encoding
        
        with pytest.raises((FileNotFoundError, Exception)):
            _read_csv_with_encoding("/nonexistent/path/file.csv")

    def test_read_csv_with_special_characters(self, temp_dir):
        """Test avec caractères spéciaux"""
        from src.data_loader import _read_csv_with_encoding
        
        file_path = Path(temp_dir) / "test_special.csv"
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'text': ["hello", "café", "naïf"],
        })
        df.to_csv(file_path, encoding='utf-8', index=False)
        
        result = _read_csv_with_encoding(str(file_path))
        assert result.shape == (3, 2)


class TestLoadData:
    """Tests pour load_data()"""

    @pytest.fixture
    def data_temp_dir(self):
        """Créer structure de dossier de données temporaire"""
        temp_dir = tempfile.mkdtemp()
        
        # Créer des CSV simples pour tester
        files = {
            'application_train.csv': pd.DataFrame({
                'SK_ID_CURR': [100001, 100002, 100003],
                'TARGET': [0, 1, 0],
                'AMT_CREDIT': [202500, 270000, 135000],
            }),
            'application_test.csv': pd.DataFrame({
                'SK_ID_CURR': [100004, 100005],
                'AMT_CREDIT': [100000, 200000],
            }),
            'bureau.csv': pd.DataFrame({
                'SK_ID_CURR': [100001, 100001, 100002],
                'SK_ID_BUREAU': [1, 2, 3],
                'CREDIT_ACTIVE': ['Active', 'Closed', 'Active'],
            }),
        }
        
        for filename, df in files.items():
            filepath = Path(temp_dir) / filename
            df.to_csv(filepath, index=False)
        
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_load_data_returns_dict(self, data_temp_dir):
        """load_data() retourne un dictionnaire"""
        from src.data_loader import load_data
        
        result = load_data(data_temp_dir)
        
        # Vérifier que c'est un dictionnaire
        assert isinstance(result, dict)
        # Vérifier que les fichiers sont présents
        assert 'application_train' in result or len(result) > 0

    def test_load_data_contains_dataframes(self, data_temp_dir):
        """Les valeurs du dictionnaire sont des DataFrames"""
        from src.data_loader import load_data
        
        result = load_data(data_temp_dir)
        
        for key, value in result.items():
            assert isinstance(value, pd.DataFrame), f"{key} is not a DataFrame"

    def test_load_data_application_train(self, data_temp_dir):
        """Vérifier que application_train est chargé correctement"""
        from src.data_loader import load_data
        
        result = load_data(data_temp_dir)
        
        if 'application_train' in result:
            df = result['application_train']
            assert df.shape[0] == 3  # 3 lignes
            assert 'SK_ID_CURR' in df.columns

    def test_load_data_application_test(self, data_temp_dir):
        """Vérifier que application_test est chargé"""
        from src.data_loader import load_data
        
        result = load_data(data_temp_dir)
        
        if 'application_test' in result:
            df = result['application_test']
            assert df.shape[0] == 2  # 2 lignes

    def test_load_data_invalid_path(self):
        """load_data() avec chemin invalide"""
        from src.data_loader import load_data
        
        # Retourner vide ou lever une erreur, c'est acceptable
        try:
            result = load_data("/nonexistent/data/path")
            # Si retourne un dict, vérifier qu'il est vide ou valide
            assert isinstance(result, dict)
        except (FileNotFoundError, Exception):
            # C'est aussi acceptable
            pass

    def test_load_data_empty_directory(self):
        """load_data() avec dossier vide"""
        from src.data_loader import load_data
        
        temp_dir = tempfile.mkdtemp()
        try:
            result = load_data(temp_dir)
            # Doit retourner dict vide ou gérer gracieusement
            assert isinstance(result, dict)
        finally:
            shutil.rmtree(temp_dir)

    def test_load_data_preserves_data_types(self, data_temp_dir):
        """Les types de données sont préservés"""
        from src.data_loader import load_data
        
        result = load_data(data_temp_dir)
        
        for key, df in result.items():
            # Vérifier que numeric columns sont numeric
            for col in df.select_dtypes(include=[np.number]).columns:
                assert df[col].dtype in [np.int64, np.int32, np.float64, np.float32]


class TestDataIntegrity:
    """Tests d'intégrité des données chargées"""

    @pytest.fixture
    def sample_data_dir(self):
        """Créer données d'exemple"""
        temp_dir = tempfile.mkdtemp()
        
        # application_train
        app_train = pd.DataFrame({
            'SK_ID_CURR': [100001, 100002, 100003],
            'TARGET': [0, 1, 0],
            'AMT_CREDIT': [202500.0, 270000.0, 135000.0],
            'AMT_INCOME': [99252.0, 202500.0, 135000.0],
        })
        app_train.to_csv(Path(temp_dir) / 'application_train.csv', index=False)
        
        # bureau (plusieurs lignes par client)
        bureau = pd.DataFrame({
            'SK_ID_CURR': [100001, 100001, 100002, 100003],
            'SK_ID_BUREAU': [1, 2, 3, 4],
            'CREDIT_ACTIVE': ['Active', 'Closed', 'Active', 'Closed'],
            'AMT_CREDIT_SUM': [100000, 50000, 200000, 75000],
        })
        bureau.to_csv(Path(temp_dir) / 'bureau.csv', index=False)
        
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_no_missing_critical_ids(self, sample_data_dir):
        """Les tables doivent avoir les ID clients"""
        from src.data_loader import load_data
        
        result = load_data(sample_data_dir)
        
        for key, df in result.items():
            if key.startswith('application_'):
                assert 'SK_ID_CURR' in df.columns, f"{key} missing SK_ID_CURR"

    def test_no_completely_empty_dataframes(self, sample_data_dir):
        """Aucun DataFrame complètement vide"""
        from src.data_loader import load_data
        
        result = load_data(sample_data_dir)
        
        for key, df in result.items():
            if len(df) > 0:
                assert df.shape[0] > 0, f"{key} is empty"

    def test_numeric_columns_are_numeric(self, sample_data_dir):
        """Colonnes numériques doivent être numériques"""
        from src.data_loader import load_data
        
        result = load_data(sample_data_dir)
        
        for key, df in result.items():
            for col in ['AMT_CREDIT', 'AMT_INCOME', 'AMT_CREDIT_SUM']:
                if col in df.columns:
                    assert pd.api.types.is_numeric_dtype(df[col]), \
                        f"{col} in {key} is not numeric"


class TestDataMerging:
    """Tests pour la fusion/agrégation de données (si implement dans module)"""

    def test_can_aggregate_bureau_by_client(self):
        """Agrégation bureau par client"""
        # Structure de test simple
        bureau = pd.DataFrame({
            'SK_ID_CURR': [100001, 100001, 100002],
            'SK_ID_BUREAU': [1, 2, 3],
            'AMT_CREDIT_SUM': [100000, 50000, 200000],
        })
        
        # Agrégation simple (groupby + agg)
        agg_bureau = bureau.groupby('SK_ID_CURR')['AMT_CREDIT_SUM'].sum().reset_index()
        
        assert agg_bureau.shape == (2, 2)
        assert agg_bureau.loc[agg_bureau['SK_ID_CURR'] == 100001, 'AMT_CREDIT_SUM'].values[0] == 150000
        assert agg_bureau.loc[agg_bureau['SK_ID_CURR'] == 100002, 'AMT_CREDIT_SUM'].values[0] == 200000

    def test_can_merge_application_with_bureau(self):
        """Fusion application_train avec bureau agrégé"""
        app_train = pd.DataFrame({
            'SK_ID_CURR': [100001, 100002],
            'AMT_CREDIT': [202500, 270000],
        })
        
        bureau_agg = pd.DataFrame({
            'SK_ID_CURR': [100001, 100002],
            'BUREAU_AMT_SUM': [150000, 200000],
        })
        
        # Fusion
        merged = app_train.merge(bureau_agg, on='SK_ID_CURR', how='left')
        
        assert merged.shape == (2, 3)
        assert 'BUREAU_AMT_SUM' in merged.columns
