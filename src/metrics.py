# -*- coding: utf-8 -*-
"""
Module pour les metriques d'evaluation des modeles.

Auteur : Gregory CRESPIN
Date : 30/01/2026
Version : 1.0

DESCRIPTIF : Ce module calcule differentes metriques pour evaluer un modele
de classification :
- Metriques classiques : accuracy, precision, recall, F1, AUC-PR
- Metriques metier : cout total (FN et FP ponderes), seuil optimal
Le cout d'un FN (mauvais client accepte) est 10x superieur au cout d'un FP
(bon client refuse).
"""

# Importation des bibliothèques nécessaires
import numpy as np  # Pour les calculs numériques
# Importation des métriques de sklearn
from sklearn.metrics import (
    average_precision_score,  # AUC-PR (Area Under Precision-Recall Curve)
    accuracy_score,  # Précision globale (pourcentage de bonnes prédictions)
    precision_score,  # Précision (parmi les prédits positifs, combien sont vraiment positifs ?)
    recall_score,  # Rappel (parmi les vrais positifs, combien ont été détectés ?)
    f1_score,  # F1-score (moyenne harmonique de précision et rappel)
    confusion_matrix  # Matrice de confusion (TN, FP, FN, TP)
)
# Importation des fonctions de calcul de coût métier
from utils.business_cost import calculate_business_cost, find_optimal_threshold


def evaluate_model(y_true, y_pred, y_proba=None, cost_fn=10, cost_fp=1):
    """
    Evalue un modele avec plusieurs metriques.
    
    DESCRIPTIF :
    - y_true : les vraies reponses (0 ou 1)
    - y_pred : les predictions du modele (0 ou 1)
    - y_proba : les probabilites predites (optionnel, pour AUC et seuil optimal)
    
    Parameters:
    -----------
    y_true : array-like
        Vraies valeurs (0 = bon client, 1 = mauvais client)
    y_pred : array-like
        Predictions binaires
    y_proba : array-like, optional
        Probabilites predites (classe 1)
    cost_fn : float, default=10
        Cout d'un faux negatif
    cost_fp : float, default=1
        Cout d'un faux positif
    
    Returns:
    --------
    metrics : dict
        Dictionnaire avec toutes les metriques
    """
    # Créer un dictionnaire vide pour stocker toutes les métriques
    metrics = {}
    
    # Metriques classiques de classification
    # Accuracy : pourcentage de bonnes prédictions globales
    # Formule : (TP + TN) / (TP + TN + FP + FN)
    metrics['accuracy'] = accuracy_score(y_true, y_pred)
    
    # Precision : parmi les clients prédits comme "mauvais" (classe 1), combien le sont vraiment ?
    # Formule : TP / (TP + FP)
    # zero_division=0 : si division par zéro (pas de prédictions positives), retourner 0
    metrics['precision'] = precision_score(y_true, y_pred, zero_division=0)
    
    # Recall (Rappel) : parmi les vrais "mauvais" clients, combien ont été détectés ?
    # Formule : TP / (TP + FN)
    # Aussi appelé "Sensibilité" ou "True Positive Rate"
    metrics['recall'] = recall_score(y_true, y_pred, zero_division=0)
    
    # F1-score : moyenne harmonique de précision et rappel
    # Formule : 2 * (precision * recall) / (precision + recall)
    # Utile pour équilibrer précision et rappel
    metrics['f1_score'] = f1_score(y_true, y_pred, zero_division=0)
    
    # AUC-PR : adapte aux populations desequilibrees (ex. 8% classe positive)
    # AUC-PR (Area Under Precision-Recall Curve) est meilleur que AUC-ROC pour les classes déséquilibrées
    # Il mesure la qualité de la séparation entre les classes en fonction du seuil de décision
    if y_proba is not None:
        metrics['auc_pr'] = average_precision_score(y_true, y_proba)
    
    # Matrice de confusion : TN, FP, FN, TP
    # confusion_matrix() retourne une matrice 2x2
    # .ravel() transforme la matrice en tableau 1D : [TN, FP, FN, TP]
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    # Stocker chaque composante dans le dictionnaire
    # TN (True Negative) : bons clients prédits bons
    metrics['tn'] = int(tn)
    # FP (False Positive) : bons clients prédits mauvais (erreur de type I)
    metrics['fp'] = int(fp)
    # FN (False Negative) : mauvais clients prédits bons (erreur de type II) - la plus coûteuse !
    metrics['fn'] = int(fn)
    # TP (True Positive) : mauvais clients prédits mauvais
    metrics['tp'] = int(tp)
    
    # Cout metier : FN*10 + FP*1
    # Calcule le coût total en fonction des erreurs de prédiction
    # Un FN coûte 10 fois plus qu'un FP (cahier des charges)
    metrics['business_cost'] = calculate_business_cost(y_true, y_pred, cost_fn, cost_fp)
    
    # Seuil optimal, score metier, precision/recall au seuil optimal (si proba disponibles)
    # Le seuil optimal n'est pas forcément 0.5, il dépend du coût métier
    if y_proba is not None:
        # Trouver le seuil qui minimise le coût métier
        # optimal_threshold : seuil optimal (ex: 0.3 au lieu de 0.5)
        # min_cost : coût minimal obtenu avec ce seuil
        # _ : dictionnaire des coûts pour tous les seuils testés (on l'ignore avec _)
        optimal_threshold, min_cost, _ = find_optimal_threshold(
            y_true, y_proba, cost_fn, cost_fp
        )
        # Stocker le seuil optimal
        metrics['optimal_threshold'] = optimal_threshold
        # Stocker le coût minimal
        metrics['min_business_cost'] = min_cost
        # Score métier : inverse du coût (plus élevé = meilleur)
        # On utilise le signe négatif pour que maximiser le score = minimiser le coût
        metrics['business_score'] = -min_cost
        
        # Precision et recall au seuil optimal (selon cout metier)
        # Recalculer les prédictions avec le seuil optimal au lieu de 0.5
        # (y_proba >= optimal_threshold) : True si proba >= seuil, False sinon
        # .astype(int) : convertir True/False en 1/0
        y_pred_optimal = (y_proba >= optimal_threshold).astype(int)
        # Calculer la précision avec ce nouveau seuil
        metrics['precision_at_optimal'] = precision_score(y_true, y_pred_optimal, zero_division=0)
        # Calculer le rappel avec ce nouveau seuil
        metrics['recall_at_optimal'] = recall_score(y_true, y_pred_optimal, zero_division=0)
    
    # Retourner le dictionnaire avec toutes les métriques calculées
    return metrics


def print_metrics(metrics):
    """
    Affiche les metriques de maniere lisible dans la console.
    
    DESCRIPTIF : Cette fonction formate l'affichage pour faciliter la lecture
    des resultats. Les sections sont : metriques classiques, matrice de
    confusion, metriques metier.
    
    Parameters:
    -----------
    metrics : dict
        Dictionnaire de metriques (retourne par evaluate_model)
    """
    # Afficher une ligne de séparation avec 50 caractères '='
    print("=" * 50)
    print("METRIQUES D'EVALUATION")
    print("=" * 50)
    
    # Section des métriques classiques
    print("\n[METRIQUES CLASSIQUES]")
    # metrics.get('accuracy', 'N/A') : récupère 'accuracy' ou 'N/A' si absent
    # :.4f : formate le nombre avec 4 décimales (format float)
    print(f"  Accuracy:  {metrics.get('accuracy', 'N/A'):.4f}")
    print(f"  Precision: {metrics.get('precision', 'N/A'):.4f}")
    print(f"  Recall:    {metrics.get('recall', 'N/A'):.4f}")
    print(f"  F1-Score:  {metrics.get('f1_score', 'N/A'):.4f}")
    # Vérifier si AUC-PR est disponible avant de l'afficher
    if 'auc_pr' in metrics:
        print(f"  AUC-PR:    {metrics['auc_pr']:.4f}")
    
    # Section de la matrice de confusion
    print("\n[MATRICE DE CONFUSION]")
    print(f"  Vrais Negatifs (TN): {metrics.get('tn', 'N/A')}")
    print(f"  Faux Positifs (FP):  {metrics.get('fp', 'N/A')}")
    print(f"  Faux Negatifs (FN):  {metrics.get('fn', 'N/A')}")
    print(f"  Vrais Positifs (TP): {metrics.get('tp', 'N/A')}")
    
    # Section des métriques métier
    print("\n[METRIQUES METIER]")
    # Afficher le coût métier avec 2 décimales (:.2f)
    print(f"  Cout metier:        {metrics.get('business_cost', 'N/A'):.2f}")
    # Si le seuil optimal a été calculé, afficher les métriques associées
    if 'min_business_cost' in metrics:
        print(f"  Cout metier min:    {metrics['min_business_cost']:.2f}")
        # Afficher le seuil optimal avec 3 décimales (:.3f)
        print(f"  Seuil optimal:     {metrics['optimal_threshold']:.3f}")
        print(f"  Score metier:      {metrics['business_score']:.2f}")
        # Afficher précision et rappel au seuil optimal si disponibles
        if 'precision_at_optimal' in metrics:
            print(f"  Precision (seuil optimal): {metrics['precision_at_optimal']:.4f}")
        if 'recall_at_optimal' in metrics:
            print(f"  Recall (seuil optimal):   {metrics['recall_at_optimal']:.4f}")
    
    # Ligne de séparation finale
    print("=" * 50)
