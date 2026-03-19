# -*- coding: utf-8 -*-
"""
Module pour le preprocessing (normalisation) des donnees.

Auteur : Gregory CRESPIN
Date : 30/01/2026
Version : 1.0

DESCRIPTIF : Avant d'entrainer certains modeles (comme la regression logistique
ou le MLP), il est recommande de normaliser les variables. La normalisation
met toutes les variables a la meme echelle (moyenne 0, ecart-type 1 pour
StandardScaler) pour eviter que les variables avec de grandes valeurs
dominent l'apprentissage.
"""

# Importation des bibliothèques nécessaires
import pandas as pd  # Pour manipuler les DataFrames
import numpy as np  # Pour les calculs numériques
# StandardScaler : normalise les données (moyenne=0, écart-type=1)
# MinMaxScaler : normalise les données entre 0 et 1
from sklearn.preprocessing import StandardScaler, MinMaxScaler
# SimpleImputer : pour remplacer les valeurs manquantes (non utilisé ici mais importé pour référence)
from sklearn.impute import SimpleImputer


def scale_features(X_train, X_test=None, method='standard'):
    """
    Normalise les features (variables explicatives).
    
    DESCRIPTIF :
    - StandardScaler : centre les donnees (moyenne=0) et reduit (ecart-type=1).
      Utile pour la plupart des modeles.
    - MinMaxScaler : met les valeurs entre 0 et 1. Utile pour les reseaux de neurones.
    
    IMPORTANT : On fit le scaler sur le train uniquement, puis on transform
    le train ET le test. Sinon on "triche" en utilisant des infos du test.
    
    Parameters:
    -----------
    X_train : DataFrame
        Donnees d'entrainement
    X_test : DataFrame, optional
        Donnees de test (seront transformees avec le meme scaler)
    method : str, default='standard'
        'standard' = StandardScaler, 'minmax' = MinMaxScaler
    
    Returns:
    --------
    X_train_scaled : DataFrame
        Donnees d'entrainement normalisees
    X_test_scaled : DataFrame or None
        Donnees de test normalisees (si X_test fourni)
    scaler : objet
        Scaler entraine (pour reutiliser plus tard)
    """
    # Choisir le type de scaler selon la méthode demandée
    if method == 'standard':
        # StandardScaler : soustrait la moyenne et divise par l'écart-type
        # Résultat : moyenne = 0, écart-type = 1
        scaler = StandardScaler()
    elif method == 'minmax':
        # MinMaxScaler : met toutes les valeurs entre 0 et 1
        # Formule : (x - min) / (max - min)
        scaler = MinMaxScaler()
    else:
        # Si la méthode n'est pas reconnue, lever une erreur
        raise ValueError("method doit etre 'standard' ou 'minmax'")
    
    # Verifier si il y a des NaN dans les donnees
    # sklearn StandardScaler et MinMaxScaler n'acceptent pas les NaN
    if X_train.isnull().any().any():
        # S'il y a des NaN, lever une erreur (c'est au caller de les traiter)
        raise ValueError("Les donnees contiennent des NaN. Veuillez les traiter avant normalisation.")
    
    # fit_transform sur le train : apprend les parametres ET transforme
    # fit_transform() fait deux choses :
    # 1. fit() : calcule la moyenne et l'écart-type (ou min/max) sur les données d'entraînement
    # 2. transform() : applique la transformation aux données
    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train),  # Applique la normalisation
        columns=X_train.columns,  # Garde les mêmes noms de colonnes
        index=X_train.index  # Garde les mêmes index (identifiants de lignes)
    )
    
    # Si des données de test sont fournies, les transformer aussi
    if X_test is not None:
        # transform sur le test : utilise les parametres appris sur le train
        # IMPORTANT : on utilise seulement transform(), pas fit_transform()
        # Car on doit utiliser les mêmes paramètres (moyenne, écart-type) que pour le train
        # Sinon on "triche" en utilisant des informations du test
        X_test_scaled = pd.DataFrame(
            scaler.transform(X_test),  # Applique la transformation avec les paramètres du train
            columns=X_test.columns,  # Garde les mêmes noms de colonnes
            index=X_test.index  # Garde les mêmes index
        )
        # Retourner les données normalisées et le scaler (pour réutilisation ultérieure)
        return X_train_scaled, X_test_scaled, scaler
    
    # Si pas de données de test, retourner seulement le train et le scaler
    return X_train_scaled, scaler
