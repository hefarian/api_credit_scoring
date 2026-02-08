# -*- coding: utf-8 -*-
"""
Module pour charger et fusionner les donnees du projet Scoring Credit.

Auteur : Gregory CRESPIN
Date : 30/01/2026
Version : 1.0

DESCRIPTIF : Ce module s'occupe de charger tous les fichiers CSV du projet
et de les fusionner en une seule table. Chaque table annexe (bureau,
previous_application, etc.) est d'abord "agregee" par client : on calcule
des statistiques (moyenne, somme, etc.) pour chaque client, puis on joint
ces statistiques a la table principale.
"""

# Importation des bibliothèques nécessaires
import pandas as pd  # pandas : bibliothèque pour manipuler des tableaux de données (DataFrames)
import numpy as np  # numpy : bibliothèque pour les calculs numériques et les tableaux
from pathlib import Path  # Path : classe pour gérer les chemins de fichiers de manière portable


def _read_csv_with_encoding(file_path, encodings=('utf-8', 'latin-1', 'cp1252')):
    """
    Charge un fichier CSV en essayant plusieurs encodages.
    
    DESCRIPTIF : Certains fichiers CSV peuvent avoir des caracteres speciaux
    (accents, symboles) qui ne sont pas en UTF-8. Cette fonction essaie
    plusieurs encodages jusqu'a trouver celui qui fonctionne.
    
    L'encodage est la façon dont les caractères sont stockés dans le fichier.
    - UTF-8 : standard moderne, supporte tous les caractères
    - latin-1 : ancien standard européen
    - cp1252 : encodage Windows
    """
    # Parcourir chaque encodage dans la liste
    for encoding in encodings:
        try:
            # Essayer de lire le fichier avec cet encodage
            # pd.read_csv() lit un fichier CSV et le convertit en DataFrame pandas
            return pd.read_csv(file_path, encoding=encoding)
        except UnicodeDecodeError:
            # Si l'encodage ne fonctionne pas, passer au suivant
            # continue passe à l'itération suivante de la boucle
            continue
    # Si aucun encodage n'a fonctionné, lever une erreur
    raise UnicodeDecodeError(
        None, b'', 0, 1,
        f"Impossible de decoder le fichier avec les encodages: {encodings}"
    )


def load_data(data_path='data'):
    """
    Charge tous les fichiers de donnees du projet.
    
    DESCRIPTIF : Cette fonction parcourt le dossier data/ et charge chaque
    fichier CSV. Les donnees sont stockees dans un dictionnaire : la cle
    est le nom du fichier sans extension (ex: 'application_train').
    
    Parameters:
    -----------
    data_path : str, default='data'
        Chemin vers le dossier contenant les donnees
    
    Returns:
    --------
    data_dict : dict
        Dictionnaire {nom_fichier: DataFrame}
    """
    # Convertir le chemin en objet Path pour faciliter les manipulations
    data_path = Path(data_path)
    # Créer un dictionnaire vide pour stocker les données chargées
    # Un dictionnaire est une structure de données {clé: valeur}
    data_dict = {}
    
    # Liste des fichiers a charger (noms exacts des CSV du projet)
    # Cette liste contient tous les fichiers CSV qu'on veut charger
    files = [
        'application_train.csv',  # Table principale d'entraînement
        'application_test.csv',  # Table principale de test
        'bureau.csv',  # Historique des crédits auprès d'autres institutions
        'bureau_balance.csv',  # Évolution des crédits bureau
        'previous_application.csv',  # Demandes de crédit précédentes
        'POS_CASH_balance.csv',  # Historique des prêts POS/CASH
        'credit_card_balance.csv',  # Historique des cartes de crédit
        'installments_payments.csv',  # Historique des paiements d'échéances
        'HomeCredit_columns_description.csv'  # Description des colonnes (métadonnées)
    ]
    
    # Parcourir chaque fichier de la liste
    for file in files:
        # Construire le chemin complet du fichier en combinant le dossier et le nom du fichier
        # L'opérateur / permet de joindre des chemins de manière portable
        file_path = data_path / file
        # Vérifier si le fichier existe avant de le charger
        if file_path.exists():
            # Afficher un message pour indiquer qu'on charge le fichier
            print(f"Chargement de {file}...")
            # Utiliser le nom sans extension comme cle du dictionnaire
            # replace('.csv', '') enlève l'extension .csv du nom
            key = file.replace('.csv', '')
            # Charger le fichier CSV avec gestion de l'encodage et le stocker dans le dictionnaire
            data_dict[key] = _read_csv_with_encoding(file_path)
            # Afficher la taille du DataFrame chargé (nombre de lignes, nombre de colonnes)
            # shape retourne un tuple (lignes, colonnes)
            print(f"  Shape: {data_dict[key].shape}")
        else:
            # Si le fichier n'existe pas, afficher un avertissement
            print(f"[ATTENTION] Fichier {file} non trouve")
    
    # Retourner le dictionnaire contenant tous les DataFrames chargés
    return data_dict


def merge_all_data(data_dict):
    """
    Fusionne toutes les tables avec la table principale application_train.
    
    DESCRIPTIF : La table principale contient 1 ligne par client (SK_ID_CURR).
    Les tables annexes contiennent plusieurs lignes par client (ex: plusieurs
    credits). On "agrege" ces tables : pour chaque client, on calcule des
    statistiques (nombre de credits, sommes, moyennes...). Puis on joint
    ces statistiques a la table principale avec un merge LEFT (pour garder
    tous les clients meme ceux sans donnees annexes).
    
    Parameters:
    -----------
    data_dict : dict
        Dictionnaire contenant tous les DataFrames charges
    
    Returns:
    --------
    df_train : DataFrame
        Donnees fusionnees pour l'entrainement
    df_test : DataFrame
        Donnees fusionnees pour le test
    """
    # Copier les tables principales (train et test)
    # .copy() crée une copie indépendante pour éviter de modifier les données originales
    df_train = data_dict['application_train'].copy()
    df_test = data_dict['application_test'].copy()
    
    # Cle de jointure : identifiant unique du client
    # Cette colonne permet de relier les différentes tables entre elles
    main_key = 'SK_ID_CURR'
    
    def safe_merge(left, right, on_key):
        """
        Fusionne deux tables en evitant les conflits de noms de colonnes.
        Si la table de droite a des colonnes qui existent deja a gauche,
        on les exclut pour eviter les doublons.
        
        left : DataFrame de gauche (table principale)
        right : DataFrame de droite (table à fusionner)
        on_key : nom de la colonne utilisée pour la jointure
        """
        # Liste en compréhension : garder seulement les colonnes de droite qui :
        # - sont la clé de jointure (on_key), OU
        # - n'existent pas déjà dans la table de gauche
        # Cela évite d'avoir des colonnes dupliquées après la fusion
        cols_to_use = [c for c in right.columns if c == on_key or c not in left.columns]
        # Sélectionner uniquement les colonnes à utiliser dans la table de droite
        right_filtered = right[cols_to_use]
        # Fusionner les deux tables avec un LEFT JOIN
        # LEFT JOIN : garde toutes les lignes de gauche, même si pas de correspondance à droite
        return left.merge(right_filtered, on=on_key, how='left')
    
    # Fusionner chaque table annexe une par une
    # On vérifie d'abord si la table existe dans le dictionnaire avant de la fusionner
    
    if 'bureau' in data_dict:
        print("Fusion avec bureau...")
        # Agréger les données bureau (calculer des statistiques par client)
        bureau_agg = aggregate_bureau(data_dict['bureau'])
        # Fusionner avec les tables train et test
        df_train = safe_merge(df_train, bureau_agg, main_key)
        df_test = safe_merge(df_test, bureau_agg, main_key)
    
    if 'previous_application' in data_dict:
        print("Fusion avec previous_application...")
        # Agréger les demandes précédentes
        prev_agg = aggregate_previous_application(data_dict['previous_application'])
        # Fusionner avec les tables train et test
        df_train = safe_merge(df_train, prev_agg, main_key)
        df_test = safe_merge(df_test, prev_agg, main_key)
    
    if 'POS_CASH_balance' in data_dict:
        print("Fusion avec POS_CASH_balance...")
        # Agréger les données POS/CASH
        pos_agg = aggregate_pos_cash(data_dict['POS_CASH_balance'])
        # Fusionner avec les tables train et test
        df_train = safe_merge(df_train, pos_agg, main_key)
        df_test = safe_merge(df_test, pos_agg, main_key)
    
    if 'credit_card_balance' in data_dict:
        print("Fusion avec credit_card_balance...")
        # Agréger les données de cartes de crédit
        cc_agg = aggregate_credit_card(data_dict['credit_card_balance'])
        # Fusionner avec les tables train et test
        df_train = safe_merge(df_train, cc_agg, main_key)
        df_test = safe_merge(df_test, cc_agg, main_key)
    
    if 'installments_payments' in data_dict:
        print("Fusion avec installments_payments...")
        # Agréger les paiements d'échéances
        inst_agg = aggregate_installments(data_dict['installments_payments'])
        # Fusionner avec les tables train et test
        df_train = safe_merge(df_train, inst_agg, main_key)
        df_test = safe_merge(df_test, inst_agg, main_key)
    
    # Afficher un message de confirmation et les dimensions finales
    print("\n[OK] Fusion terminee")
    # shape retourne (nombre de lignes, nombre de colonnes)
    print(f"Train shape: {df_train.shape}")
    print(f"Test shape: {df_test.shape}")
    
    # Retourner les deux DataFrames fusionnés
    return df_train, df_test


def aggregate_bureau(df):
    """
    Agrege les donnees bureau par client.
    
    DESCRIPTIF : La table bureau contient l'historique des credits aupres
    d'autres institutions. Pour chaque client, on calcule : nombre de
    credits, duree min/max/moyenne, montants totaux, etc.
    Les colonnes sont prefixees par 'bureau_' pour eviter les conflits.
    """
    # Dictionnaire définissant quelles statistiques calculer pour chaque colonne
    # Format : {nom_colonne: [liste des fonctions d'agrégation]}
    # Exemple : 'DAYS_CREDIT': ['min', 'max', 'mean'] calcule le min, max et la moyenne
    agg_dict = {
        'SK_ID_BUREAU': ['count'],  # Nombre de crédits bureau par client
        'DAYS_CREDIT': ['min', 'max', 'mean'],  # Durée min/max/moyenne des crédits
        'CREDIT_DAY_OVERDUE': ['max', 'mean'],  # Jours de retard max/moyen
        'AMT_CREDIT_MAX_OVERDUE': ['max', 'mean'],  # Montant max/moyen en retard
        'AMT_CREDIT_SUM': ['sum', 'mean', 'max'],  # Somme/moyenne/max des montants de crédit
        'AMT_CREDIT_SUM_DEBT': ['sum', 'mean'],  # Somme/moyenne des dettes
        'AMT_CREDIT_SUM_OVERDUE': ['sum', 'mean'],  # Somme/moyenne des montants en retard
        'AMT_ANNUITY': ['sum', 'mean']  # Somme/moyenne des annuités
    }
    
    # Ne garder que les colonnes qui existent dans le DataFrame
    # select_dtypes(include=[np.number]) sélectionne uniquement les colonnes numériques
    # .columns.tolist() convertit l'index des colonnes en liste Python
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    # Filtrer le dictionnaire pour ne garder que les colonnes qui existent vraiment
    # Compréhension de dictionnaire : {clé: valeur for clé, valeur in ... if condition}
    available_cols = {k: v for k, v in agg_dict.items() if k in numeric_cols}
    
    # Si aucune colonne n'est disponible, retourner un DataFrame vide
    if not available_cols:
        return pd.DataFrame()
    
    # Groupby + agg : calcule les stats pour chaque client
    # groupby('SK_ID_CURR') groupe les lignes par identifiant client
    # .agg(available_cols) applique les fonctions d'agrégation définies dans available_cols
    agg = df.groupby('SK_ID_CURR').agg(available_cols)
    # Renommer les colonnes avec le prefixe bureau_
    # Les colonnes après groupby.agg() ont un format multi-niveau, on les aplatit
    # '_'.join(col) joint les éléments du tuple avec des underscores
    # Exemple : ('DAYS_CREDIT', 'mean') devient 'DAYS_CREDIT_mean'
    agg.columns = ['bureau_' + '_'.join(col).strip() for col in agg.columns.values]
    # reset_index() transforme SK_ID_CURR d'index en colonne normale
    # inplace=True modifie directement le DataFrame sans créer de copie
    agg.reset_index(inplace=True)
    
    # Retourner le DataFrame agrégé
    return agg


def aggregate_previous_application(df):
    """
    Agrege les demandes de credit precedentes par client.
    Prefixe des colonnes : prev_
    
    Cette fonction calcule des statistiques sur les demandes de crédit précédentes
    pour chaque client (nombre de demandes, montants moyens, etc.)
    """
    # Dictionnaire définissant les statistiques à calculer
    agg_dict = {
        'SK_ID_PREV': ['count'],  # Nombre de demandes précédentes
        'AMT_ANNUITY': ['sum', 'mean', 'min', 'max'],  # Statistiques sur les annuités
        'AMT_APPLICATION': ['sum', 'mean', 'min', 'max'],  # Statistiques sur les montants demandés
        'AMT_CREDIT': ['sum', 'mean', 'min', 'max'],  # Statistiques sur les montants de crédit
        'DAYS_DECISION': ['min', 'max', 'mean'],  # Durées min/max/moyenne de décision
        'CNT_PAYMENT': ['mean', 'sum']  # Nombre moyen et total de paiements
    }
    
    # Sélectionner uniquement les colonnes numériques du DataFrame
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    # Filtrer pour ne garder que les colonnes qui existent dans le DataFrame
    available_cols = {k: v for k, v in agg_dict.items() if k in numeric_cols}
    
    # Si aucune colonne disponible, retourner un DataFrame vide
    if not available_cols:
        return pd.DataFrame()
    
    # Grouper par client et calculer les statistiques
    agg = df.groupby('SK_ID_CURR').agg(available_cols)
    # Renommer les colonnes avec le préfixe 'prev_'
    agg.columns = ['prev_' + '_'.join(col).strip() for col in agg.columns.values]
    # Remettre SK_ID_CURR comme colonne normale (pas comme index)
    agg.reset_index(inplace=True)
    
    # Retourner le DataFrame agrégé
    return agg


def aggregate_pos_cash(df):
    """
    Agrege les donnees POS/CASH par client.
    Prefixe des colonnes : pos_
    
    POS/CASH = Point of Sale / Cash loans (prêts à la consommation)
    """
    # Dictionnaire définissant les statistiques à calculer
    agg_dict = {
        'SK_ID_PREV': ['count'],  # Nombre de prêts POS/CASH
        'MONTHS_BALANCE': ['min', 'max', 'mean'],  # Mois de solde (min/max/moyenne)
        'CNT_INSTALMENT': ['mean', 'sum'],  # Nombre d'échéances (moyenne et total)
        'CNT_INSTALMENT_FUTURE': ['mean', 'sum'],  # Échéances futures (moyenne et total)
        'SK_DPD': ['max', 'mean'],  # Days Past Due (jours de retard) - max et moyenne
        'SK_DPD_DEF': ['max', 'mean']  # Days Past Due définitif - max et moyenne
    }
    
    # Sélectionner uniquement les colonnes numériques
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    # Filtrer pour ne garder que les colonnes existantes
    available_cols = {k: v for k, v in agg_dict.items() if k in numeric_cols}
    
    # Si aucune colonne disponible, retourner un DataFrame vide
    if not available_cols:
        return pd.DataFrame()
    
    # Grouper par client et calculer les statistiques
    agg = df.groupby('SK_ID_CURR').agg(available_cols)
    # Renommer avec le préfixe 'pos_'
    agg.columns = ['pos_' + '_'.join(col).strip() for col in agg.columns.values]
    # Remettre SK_ID_CURR comme colonne normale
    agg.reset_index(inplace=True)
    
    return agg


def aggregate_credit_card(df):
    """
    Agrege les donnees cartes de credit par client.
    Prefixe des colonnes : cc_ (credit card)
    """
    # Dictionnaire définissant les statistiques à calculer
    agg_dict = {
        'SK_ID_PREV': ['count'],  # Nombre de cartes de crédit
        'MONTHS_BALANCE': ['min', 'max', 'mean'],  # Mois de solde
        'AMT_BALANCE': ['sum', 'mean', 'max'],  # Solde (somme, moyenne, maximum)
        'AMT_CREDIT_LIMIT_ACTUAL': ['sum', 'mean', 'max'],  # Limite de crédit réelle
        'AMT_DRAWINGS_ATM_CURRENT': ['sum', 'mean'],  # Retraits DAB (somme et moyenne)
        'AMT_DRAWINGS_CURRENT': ['sum', 'mean'],  # Retraits totaux (somme et moyenne)
        'AMT_PAYMENT_CURRENT': ['sum', 'mean'],  # Paiements actuels (somme et moyenne)
        'CNT_DRAWINGS_ATM_CURRENT': ['sum', 'mean'],  # Nombre de retraits DAB
        'CNT_DRAWINGS_CURRENT': ['sum', 'mean']  # Nombre total de retraits
    }
    
    # Sélectionner uniquement les colonnes numériques
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    # Filtrer pour ne garder que les colonnes existantes
    available_cols = {k: v for k, v in agg_dict.items() if k in numeric_cols}
    
    # Si aucune colonne disponible, retourner un DataFrame vide
    if not available_cols:
        return pd.DataFrame()
    
    # Grouper par client et calculer les statistiques
    agg = df.groupby('SK_ID_CURR').agg(available_cols)
    # Renommer avec le préfixe 'cc_'
    agg.columns = ['cc_' + '_'.join(col).strip() for col in agg.columns.values]
    # Remettre SK_ID_CURR comme colonne normale
    agg.reset_index(inplace=True)
    
    return agg


def aggregate_installments(df):
    """
    Agrege les paiements d'echeances par client.
    Calcule aussi des ratios (pourcentage paye, retard).
    Prefixe des colonnes : inst_
    """
    # Créer une copie pour ne pas modifier le DataFrame original
    # En Python, les objets sont passés par référence, donc modifier df modifierait aussi l'original
    df = df.copy()
    
    # Dictionnaire initial des statistiques à calculer
    agg_dict = {
        'SK_ID_PREV': ['count'],  # Nombre de prêts avec échéances
        'NUM_INSTALMENT_VERSION': ['nunique'],  # Nombre unique de versions d'échéances
        'NUM_INSTALMENT_NUMBER': ['max', 'mean'],  # Numéro d'échéance (max et moyenne)
        'DAYS_INSTALMENT': ['min', 'max', 'mean'],  # Jours d'échéance (min/max/moyenne)
        'DAYS_ENTRY_PAYMENT': ['min', 'max', 'mean'],  # Jours d'entrée de paiement
        'AMT_INSTALMENT': ['sum', 'mean', 'min', 'max'],  # Montant d'échéance dû
        'AMT_PAYMENT': ['sum', 'mean', 'min', 'max']  # Montant payé
    }
    
    # Creer des variables derivees : ratio de paiement et retard
    # PAYMENT_PERC : pourcentage du montant dû qui a été payé (ratio de paiement)
    # On divise le montant payé par le montant dû
    df['PAYMENT_PERC'] = df['AMT_PAYMENT'] / df['AMT_INSTALMENT']
    # PAYMENT_DIFF : différence entre ce qui était dû et ce qui a été payé
    # Une valeur positive = retard, négative = paiement anticipé
    df['PAYMENT_DIFF'] = df['AMT_INSTALMENT'] - df['AMT_PAYMENT']
    # DPD : Days Past Due (jours de retard)
    # Différence entre le jour d'entrée du paiement et le jour d'échéance
    # Positif = retard, négatif = paiement anticipé
    df['DPD'] = df['DAYS_ENTRY_PAYMENT'] - df['DAYS_INSTALMENT']
    
    # Ajouter les nouvelles variables au dictionnaire d'agrégation
    agg_dict.update({
        'PAYMENT_PERC': ['mean', 'min'],  # Pourcentage moyen et minimum de paiement
        'PAYMENT_DIFF': ['sum', 'mean'],  # Différence totale et moyenne
        'DPD': ['max', 'mean']  # Retard maximum et moyen
    })
    
    # Sélectionner uniquement les colonnes numériques
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    # Filtrer pour ne garder que les colonnes existantes
    available_cols = {k: v for k, v in agg_dict.items() if k in numeric_cols}
    
    # Si aucune colonne disponible, retourner un DataFrame vide
    if not available_cols:
        return pd.DataFrame()
    
    # Grouper par client et calculer les statistiques
    agg = df.groupby('SK_ID_CURR').agg(available_cols)
    # Renommer avec le préfixe 'inst_' (installments = échéances)
    agg.columns = ['inst_' + '_'.join(col).strip() for col in agg.columns.values]
    # Remettre SK_ID_CURR comme colonne normale
    agg.reset_index(inplace=True)
    
    return agg
