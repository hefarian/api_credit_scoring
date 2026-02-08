# -*- coding: utf-8 -*-
"""
Module pour calculer le cout metier personnalise.

Auteur : Gregory CRESPIN
Date : 30/01/2026
Version : 1.0

DESCRIPTIF : En credit scoring, toutes les erreurs n'ont pas le meme cout :
- Faux Negatif (FN) : on accepte un mauvais client -> perte d'argent (credit non rembourse)
- Faux Positif (FP) : on refuse un bon client -> manque a gagner (marge perdue)
Le cahier des charges precise que le cout d'un FN est 10x superieur au cout d'un FP.
On doit donc optimiser le seuil de decision (pas forcement 0.5) pour minimiser ce cout.
"""

# Importation des bibliothèques nécessaires
import numpy as np  # Pour les calculs numériques
from sklearn.metrics import confusion_matrix  # Pour calculer la matrice de confusion (TN, FP, FN, TP)


def calculate_business_cost(y_true, y_pred, cost_fn=10, cost_fp=1):
    """
    Calcule le cout metier total base sur les erreurs de prediction.
    
    DESCRIPTIF : Formule = FN * cost_fn + FP * cost_fp
    Par defaut : FN coute 10, FP coute 1.
    
    Parameters:
    -----------
    y_true : array-like
        Vraies valeurs (0 = bon client, 1 = mauvais client)
    y_pred : array-like
        Predictions (0 = bon client, 1 = mauvais client)
    cost_fn : float, default=10
        Cout d'un faux negatif (mauvais client predit bon)
    cost_fp : float, default=1
        Cout d'un faux positif (bon client predit mauvais)
    
    Returns:
    --------
    total_cost : float
        Cout metier total
    """
    # Calculer la matrice de confusion
    # confusion_matrix() retourne une matrice 2x2 : [[TN, FP], [FN, TP]]
    # .ravel() transforme la matrice en tableau 1D : [TN, FP, FN, TP]
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    
    # Calculer le coût total métier
    # Formule : coût = (nombre de FN × coût d'un FN) + (nombre de FP × coût d'un FP)
    # Par défaut : FN coûte 10, FP coûte 1
    total_cost = (fn * cost_fn) + (fp * cost_fp)
    
    # Retourner le coût total
    return total_cost


def calculate_business_cost_from_proba(y_true, y_proba, threshold=0.5, cost_fn=10, cost_fp=1):
    """
    Calcule le cout metier a partir des probabilites et d'un seuil.
    
    DESCRIPTIF : On convertit les proba en predictions binaires avec le seuil :
    si proba >= seuil -> prediction 1 (mauvais client), sinon 0 (bon client).
    
    Parameters:
    -----------
    y_true : array-like
        Vraies valeurs
    y_proba : array-like
        Probabilites predites (probabilite d'etre mauvais client)
    threshold : float, default=0.5
        Seuil de classification
    cost_fn : float, default=10
        Cout d'un faux negatif
    cost_fp : float, default=1
        Cout d'un faux positif
    
    Returns:
    --------
    total_cost : float
        Cout metier total
    """
    # Convertir les probabilités en prédictions binaires avec le seuil donné
    # (y_proba >= threshold) : True si proba >= seuil, False sinon
    # .astype(int) : convertir True/False en 1/0 (1 = mauvais client, 0 = bon client)
    y_pred = (y_proba >= threshold).astype(int)
    # Calculer le coût métier avec ces nouvelles prédictions
    return calculate_business_cost(y_true, y_pred, cost_fn, cost_fp)


def find_optimal_threshold(y_true, y_proba, cost_fn=10, cost_fp=1, thresholds=None):
    """
    Trouve le seuil optimal qui minimise le cout metier.
    
    DESCRIPTIF : On teste differents seuils (0.1, 0.11, 0.12, ... 0.9) et on
    garde celui qui donne le cout le plus bas. Un seuil plus bas = plus de
    clients refuses (moins de FN mais plus de FP). Un seuil plus haut =
    plus de clients acceptes (moins de FP mais plus de FN).
    
    Parameters:
    -----------
    y_true : array-like
        Vraies valeurs
    y_proba : array-like
        Probabilites predites
    cost_fn : float, default=10
        Cout d'un faux negatif
    cost_fp : float, default=1
        Cout d'un faux positif
    thresholds : array-like, optional
        Liste de seuils a tester. Si None, teste de 0.1 a 0.9 par pas de 0.01
    
    Returns:
    --------
    optimal_threshold : float
        Seuil optimal
    min_cost : float
        Cout minimal obtenu
    costs : dict
        Dictionnaire {seuil: cout} pour tous les seuils testes
    """
    # Si aucun seuil n'est fourni, créer une liste de seuils à tester
    # np.arange(0.1, 0.9, 0.01) : crée un tableau [0.1, 0.11, 0.12, ..., 0.89]
    # On teste donc des seuils de 0.1 à 0.9 par pas de 0.01
    if thresholds is None:
        thresholds = np.arange(0.1, 0.9, 0.01)
    
    # Créer un dictionnaire vide pour stocker les coûts pour chaque seuil
    costs = {}
    # Parcourir chaque seuil et calculer le coût associé
    for threshold in thresholds:
        # Calculer le coût métier avec ce seuil
        cost = calculate_business_cost_from_proba(y_true, y_proba, threshold, cost_fn, cost_fp)
        # Stocker le coût dans le dictionnaire avec le seuil comme clé
        costs[threshold] = cost
    
    # Trouver le seuil qui donne le coût minimal
    # min(costs, key=costs.get) : trouve la clé (seuil) avec la valeur (coût) minimale
    # key=costs.get : utilise la valeur du dictionnaire (le coût) pour comparer
    optimal_threshold = min(costs, key=costs.get)
    # Récupérer le coût minimal associé
    min_cost = costs[optimal_threshold]
    
    # Retourner le seuil optimal, le coût minimal, et le dictionnaire complet des coûts
    return optimal_threshold, min_cost, costs


def business_score(y_true, y_proba, cost_fn=10, cost_fp=1):
    """
    Calcule le score metier (inverse du cout) pour faciliter la comparaison.
    
    DESCRIPTIF : Un score plus eleve = meilleur. On utilise -cout pour que
    "maximiser le score" = "minimiser le cout".
    
    Parameters:
    -----------
    y_true : array-like
        Vraies valeurs
    y_proba : array-like
        Probabilites predites
    cost_fn : float, default=10
        Cout d'un faux negatif
    cost_fp : float, default=1
        Cout d'un faux positif
    
    Returns:
    --------
    score : float
        Score metier (plus eleve = meilleur)
    optimal_threshold : float
        Seuil optimal utilise
    """
    # Trouver le seuil optimal et le coût minimal
    # _ : on ignore le dictionnaire des coûts (3ème valeur retournée)
    optimal_threshold, min_cost, _ = find_optimal_threshold(y_true, y_proba, cost_fn, cost_fp)
    
    # Calculer le score métier (inverse du coût)
    # On utilise le signe négatif pour que maximiser le score = minimiser le coût
    # Plus le score est élevé, meilleur est le modèle
    score = -min_cost
    
    # Retourner le score et le seuil optimal utilisé
    return score, optimal_threshold
