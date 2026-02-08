# -*- coding: utf-8 -*-
"""
Module pour le feature engineering (creation de nouvelles variables).

Auteur : Gregory CRESPIN
Date : 30/01/2026
Version : 1.0

DESCRIPTIF : Le feature engineering consiste a creer de nouvelles variables
a partir des variables existantes. Par exemple, un ratio credit/revenu
peut etre plus informatif que le credit et le revenu separes. Ces nouvelles
variables aident souvent le modele a mieux predire.
"""

# Importation des bibliothèques nécessaires
import pandas as pd  # Pour manipuler les DataFrames
import numpy as np  # Pour les calculs numériques


def create_ratio_features(df):
    """
    Cree des features de type ratio a partir des variables existantes.
    
    DESCRIPTIF : Les ratios sont des indicateurs courants en credit scoring :
    - CREDIT_INCOME_PERC : quelle part du revenu represente le credit ?
    - ANNUITY_CREDIT_PERC : quelle part du credit representent les annuites ?
    On ajoute +1 aux denominateurs pour eviter les divisions par zero.
    
    Parameters:
    -----------
    df : DataFrame
        DataFrame avec les features existantes
    
    Returns:
    --------
    df : DataFrame
        DataFrame avec les nouvelles features ajoutees
    """
    # Créer une copie pour ne pas modifier le DataFrame original
    df = df.copy()
    
    # Ratios financiers
    # Ces ratios sont très informatifs en crédit scoring car ils mesurent la capacité de remboursement
    
    # CREDIT_INCOME_PERC : quel pourcentage du revenu représente le crédit demandé ?
    # Un ratio élevé = risque élevé (le client s'endette beaucoup par rapport à ses revenus)
    if 'AMT_CREDIT' in df.columns and 'AMT_INCOME_TOTAL' in df.columns:
        # On ajoute +1 au dénominateur pour éviter la division par zéro si revenu = 0
        df['CREDIT_INCOME_PERC'] = df['AMT_CREDIT'] / (df['AMT_INCOME_TOTAL'] + 1)
    
    # ANNUITY_CREDIT_PERC : quel pourcentage du crédit représentent les annuités ?
    # Mesure le poids des remboursements mensuels
    if 'AMT_ANNUITY' in df.columns and 'AMT_CREDIT' in df.columns:
        df['ANNUITY_CREDIT_PERC'] = df['AMT_ANNUITY'] / (df['AMT_CREDIT'] + 1)
    
    # GOODS_CREDIT_PERC : ratio prix des biens / montant du crédit
    # Si le crédit est supérieur au prix des biens, il y a peut-être d'autres frais
    if 'AMT_GOODS_PRICE' in df.columns and 'AMT_CREDIT' in df.columns:
        df['GOODS_CREDIT_PERC'] = df['AMT_GOODS_PRICE'] / (df['AMT_CREDIT'] + 1)
    
    # ANNUITY_INCOME_PERC : quel pourcentage du revenu représentent les annuités ?
    # Ratio très important : si les remboursements mensuels sont trop élevés par rapport au revenu, risque élevé
    if 'AMT_ANNUITY' in df.columns and 'AMT_INCOME_TOTAL' in df.columns:
        df['ANNUITY_INCOME_PERC'] = df['AMT_ANNUITY'] / (df['AMT_INCOME_TOTAL'] + 1)
    
    # Features temporelles : convertir les jours en annees
    # Les dates sont stockées en nombre de jours avant aujourd'hui (valeurs négatives)
    
    # AGE_YEARS : âge du client en années
    if 'DAYS_BIRTH' in df.columns:
        # On multiplie par -1 car les jours sont négatifs (dans le passé)
        # On divise par 365.25 pour convertir en années (0.25 pour tenir compte des années bissextiles)
        df['AGE_YEARS'] = -df['DAYS_BIRTH'] / 365.25
    
    # EMPLOYED_YEARS : nombre d'années d'emploi
    if 'DAYS_EMPLOYED' in df.columns:
        df['EMPLOYED_YEARS'] = -df['DAYS_EMPLOYED'] / 365.25
        # clip(lower=0) : s'assurer qu'il n'y a pas de valeurs négatives
        # (certaines valeurs aberrantes peuvent être positives, ce qui signifierait "emploi dans le futur")
        df['EMPLOYED_YEARS'] = df['EMPLOYED_YEARS'].clip(lower=0)
    
    # Features combinees : scores externes (EXT_SOURCE = score d'autres organismes)
    # Les scores externes sont des scores de crédit calculés par d'autres institutions
    # On crée des statistiques agrégées de ces scores
    
    # Liste en compréhension : trouver toutes les colonnes contenant 'EXT_SOURCE'
    ext_source_cols = [col for col in df.columns if 'EXT_SOURCE' in col]
    if len(ext_source_cols) > 0:
        # mean(axis=1) : moyenne par ligne (pour chaque client)
        df['EXT_SOURCES_MEAN'] = df[ext_source_cols].mean(axis=1)
        # std(axis=1) : écart-type par ligne (variabilité des scores)
        df['EXT_SOURCES_STD'] = df[ext_source_cols].std(axis=1)
        # max(axis=1) : meilleur score externe
        df['EXT_SOURCES_MAX'] = df[ext_source_cols].max(axis=1)
        # min(axis=1) : pire score externe
        df['EXT_SOURCES_MIN'] = df[ext_source_cols].min(axis=1)
    
    # Nombre de documents fournis par le client
    # Plus un client fournit de documents, plus il est sérieux (en général)
    
    # Trouver toutes les colonnes contenant 'FLAG_DOCUMENT'
    doc_cols = [col for col in df.columns if 'FLAG_DOCUMENT' in col]
    if len(doc_cols) > 0:
        # sum(axis=1) : somme par ligne (nombre total de documents fournis)
        # Les FLAG sont généralement 0 ou 1, donc la somme donne le nombre de documents
        df['DOCUMENT_COUNT'] = df[doc_cols].sum(axis=1)
    
    # Retourner le DataFrame avec les nouvelles colonnes ajoutées
    return df


def create_interaction_features(df):
    """
    Cree des features d'interaction entre variables.
    
    DESCRIPTIF : Une interaction combine deux variables. Exemple : revenu par
    personne = revenu total / nombre de personnes dans le foyer. Un revenu
    de 3000 euros pour 1 personne n'a pas le meme sens que pour 5 personnes.
    
    Parameters:
    -----------
    df : DataFrame
        DataFrame avec les features
    
    Returns:
    --------
    df : DataFrame
        DataFrame avec les nouvelles features d'interaction
    """
    # Créer une copie pour ne pas modifier le DataFrame original
    df = df.copy()
    
    # INCOME_PER_PERSON : revenu par personne dans le foyer
    # Un revenu de 3000€ pour 1 personne n'a pas le même sens que pour 5 personnes
    # Cette variable permet de mieux évaluer le niveau de vie réel
    if 'AMT_INCOME_TOTAL' in df.columns and 'CNT_FAM_MEMBERS' in df.columns:
        # On ajoute +1 pour éviter la division par zéro si CNT_FAM_MEMBERS = 0
        df['INCOME_PER_PERSON'] = df['AMT_INCOME_TOTAL'] / (df['CNT_FAM_MEMBERS'] + 1)
    
    # CREDIT_PER_PERSON : crédit par personne dans le foyer
    # Permet de voir si le crédit est raisonnable par rapport à la taille du foyer
    if 'AMT_CREDIT' in df.columns and 'CNT_FAM_MEMBERS' in df.columns:
        df['CREDIT_PER_PERSON'] = df['AMT_CREDIT'] / (df['CNT_FAM_MEMBERS'] + 1)
    
    # Retourner le DataFrame avec les nouvelles colonnes d'interaction
    return df
