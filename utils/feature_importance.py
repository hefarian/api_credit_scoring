# -*- coding: utf-8 -*-
"""
Module pour analyser l'importance des features (globale et locale).

Auteur : Gregory CRESPIN
Date : 30/01/2026
Version : 1.0

DESCRIPTIF : L'interpretabilite du modele est importante en credit scoring.
- Importance globale : quelles variables contribuent le plus au modele en general ?
- Importance locale (SHAP) : pour un client donne, quelles variables ont
  influence sa prediction ? Utile pour expliquer une decision a un charge d'etudes.
"""

# Importation des bibliothèques nécessaires
import numpy as np  # Pour les calculs numériques
import pandas as pd  # Pour manipuler les DataFrames
import matplotlib.pyplot as plt  # Pour créer des graphiques
import seaborn as sns  # Bibliothèque de visualisation statistique (plus jolie que matplotlib)

# Essayer d'importer SHAP (bibliothèque pour l'interprétabilité des modèles)
# SHAP permet d'expliquer les prédictions d'un modèle
try:
    import shap  # SHAP : SHapley Additive exPlanations
    SHAP_AVAILABLE = True  # Marquer que SHAP est disponible
except ImportError:
    # Si SHAP n'est pas installé, continuer sans erreur mais marquer comme non disponible
    SHAP_AVAILABLE = False
    print("SHAP non disponible. Installation: pip install shap")


def plot_global_feature_importance(model, feature_names, top_n=20, figsize=(10, 8)):
    """
    Affiche l'importance globale des features pour un modele.
    
    DESCRIPTIF : Les arbres (Random Forest, XGBoost) ont feature_importances_.
    La regression logistique a coef_. On affiche les top_n variables les
    plus importantes dans un graphique en barres.
    
    Parameters:
    -----------
    model : sklearn model
        Modele entraine avec feature_importances_ ou coef_
    feature_names : list
        Noms des features
    top_n : int, default=20
        Nombre de features a afficher
    figsize : tuple, default=(10, 8)
        Taille de la figure
    """
    # Recuperer l'importance selon le type de modele
    # hasattr() : vérifie si l'objet a un attribut donné
    
    # Pour les modèles basés sur les arbres (Random Forest, XGBoost, LightGBM)
    # Ils ont un attribut feature_importances_ qui donne l'importance de chaque feature
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    
    # Pour la régression logistique et autres modèles linéaires
    # Ils ont un attribut coef_ qui donne les coefficients (poids) de chaque feature
    # On prend la valeur absolue car un coefficient négatif peut être aussi important qu'un positif
    elif hasattr(model, 'coef_'):
        # coef_[0] : prendre la première ligne (pour classification binaire)
        # np.abs() : prendre la valeur absolue
        importances = np.abs(model.coef_[0])
    else:
        # Si le modèle n'a ni feature_importances_ ni coef_, lever une erreur
        raise ValueError("Le modele doit avoir feature_importances_ ou coef_")
    
    # Creer un DataFrame et trier par importance
    # pd.DataFrame() : créer un DataFrame avec deux colonnes
    importance_df = pd.DataFrame({
        'feature': feature_names,  # Noms des features
        'importance': importances  # Valeurs d'importance
    }).sort_values('importance', ascending=False).head(top_n)
    # sort_values('importance', ascending=False) : trier par importance décroissante
    # .head(top_n) : garder seulement les top_n premières lignes
    
    # Graphique en barres horizontales
    # plt.figure() : créer une nouvelle figure avec la taille spécifiée
    plt.figure(figsize=figsize)
    # sns.barplot() : créer un graphique en barres avec seaborn
    # data=importance_df : données à utiliser
    # y='feature' : axe Y = noms des features
    # x='importance' : axe X = valeurs d'importance
    # palette='viridis' : palette de couleurs (dégradé vert-bleu)
    sns.barplot(data=importance_df, y='feature', x='importance', palette='viridis')
    # Ajouter un titre au graphique
    plt.title(f'Top {top_n} Features - Importance Globale', fontsize=14, fontweight='bold')
    # Ajouter des labels aux axes
    plt.xlabel('Importance', fontsize=12)
    plt.ylabel('Feature', fontsize=12)
    # Ajuster l'espacement pour éviter que les labels soient coupés
    plt.tight_layout()
    # Afficher le graphique
    plt.show()
    
    # Retourner le DataFrame avec les importances triées
    return importance_df


def plot_shap_summary(model, X, feature_names=None, max_display=20):
    """
    Affiche le resume SHAP pour l'importance globale et locale.
    
    DESCRIPTIF : SHAP (SHapley Additive exPlanations) attribue a chaque
    variable sa contribution a la prediction. Les valeurs positives
    poussent vers la classe 1, les negatives vers la classe 0.
    
    Parameters:
    -----------
    model : sklearn model
        Modele entraine
    X : array-like
        Donnees d'exemple (peut etre un echantillon pour aller plus vite)
    feature_names : list, optional
        Noms des features
    max_display : int, default=20
        Nombre de features a afficher
    """
    if not SHAP_AVAILABLE:
        print("SHAP n'est pas disponible. Installation: pip install shap")
        return None
    
    # Choisir l'explainer selon le type de modele
    # TreeExplainer : pour les modèles basés sur les arbres (Random Forest, XGBoost, etc.)
    # LinearExplainer : pour les modèles linéaires (Régression logistique, etc.)
    # L'explainer est l'objet qui calcule les valeurs SHAP
    explainer = shap.TreeExplainer(model) if hasattr(model, 'feature_importances_') else shap.LinearExplainer(model, X)
    
    # Calculer les valeurs SHAP pour toutes les instances
    # shap_values : contribution de chaque feature à chaque prédiction
    shap_values = explainer.shap_values(X)
    
    # Modele binaire : prendre les valeurs pour la classe positive
    # Pour un modèle binaire, shap_values est une liste [valeurs_classe_0, valeurs_classe_1]
    # On prend généralement les valeurs pour la classe positive (indice 1)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    
    # Créer un graphique résumé SHAP
    # summary_plot() : affiche un graphique montrant l'importance globale et la distribution des valeurs SHAP
    # max_display : nombre maximum de features à afficher
    # show=False : ne pas afficher immédiatement (pour pouvoir ajuster le layout)
    shap.summary_plot(shap_values, X, feature_names=feature_names, max_display=max_display, show=False)
    # Ajuster l'espacement
    plt.tight_layout()
    # Afficher le graphique
    plt.show()
    
    # Retourner les valeurs SHAP calculées
    return shap_values


def explain_local_prediction(model, X_instance, feature_names=None, shap_values=None):
    """
    Explique une prediction locale pour un client specifique.
    
    DESCRIPTIF : Pour un client donne, on affiche quelles variables ont
    le plus influence sa prediction. Utile pour expliquer un refus ou
    une acceptation a un charge d'etudes.
    
    Parameters:
    -----------
    model : sklearn model
        Modele entraine
    X_instance : array-like
        Instance a expliquer (1 ligne)
    feature_names : list, optional
        Noms des features
    shap_values : array, optional
        Valeurs SHAP pre-calculees
    
    Returns:
    --------
    explanation_df : DataFrame
        Features et leur contribution SHAP
    """
    if not SHAP_AVAILABLE:
        print("SHAP n'est pas disponible pour l'explication locale.")
        return None
    
    # Si les valeurs SHAP ne sont pas fournies, les calculer
    if shap_values is None:
        # Choisir l'explainer selon le type de modèle
        # .reshape(1, -1) : transformer X_instance en matrice 2D (1 ligne, n colonnes)
        # Car les explainers attendent un tableau 2D même pour une seule instance
        explainer = shap.TreeExplainer(model) if hasattr(model, 'feature_importances_') else shap.LinearExplainer(model, X_instance.reshape(1, -1))
        # Calculer les valeurs SHAP pour cette instance
        shap_values = explainer.shap_values(X_instance)
        # Pour un modèle binaire, prendre les valeurs de la classe positive
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
    
    # Si les noms de features ne sont pas fournis, créer des noms génériques
    if feature_names is None:
        # Liste en compréhension : créer ['Feature_0', 'Feature_1', ...]
        feature_names = [f'Feature_{i}' for i in range(len(X_instance))]
    
    # Créer un DataFrame avec les explications
    explanation_df = pd.DataFrame({
        'feature': feature_names,  # Noms des features
        'value': X_instance,  # Valeurs réelles de l'instance
        # shap_value : contribution SHAP de chaque feature
        # Si shap_values est 2D (plusieurs instances), prendre la première ligne [0]
        # Sinon, shap_values est déjà 1D
        'shap_value': shap_values[0] if len(shap_values.shape) > 1 else shap_values
    }).sort_values('shap_value', key=abs, ascending=False)
    # sort_values() : trier par valeur absolue de shap_value décroissante
    # key=abs : utiliser la valeur absolue pour le tri (les valeurs négatives importantes aussi)
    
    # Retourner le DataFrame avec les explications triées
    return explanation_df


def plot_waterfall_explanation(explanation_df, top_n=10):
    """
    Affiche une explication waterfall pour un client.
    
    DESCRIPTIF : Graphique en barres montrant la contribution de chaque
    variable. Rouge = pousse vers mauvais client, Vert = pousse vers bon client.
    
    Parameters:
    -----------
    explanation_df : DataFrame
        DataFrame avec features et contributions SHAP
    top_n : int, default=10
        Nombre de features a afficher
    """
    # Sélectionner les top_n features les plus importantes
    top_features = explanation_df.head(top_n)
    
    # Créer une nouvelle figure pour le graphique
    plt.figure(figsize=(10, 6))
    
    # Définir les couleurs selon le signe de la contribution SHAP
    # Liste en compréhension : rouge si contribution négative, vert si positive
    # Contribution négative = pousse vers classe 0 (bon client)
    # Contribution positive = pousse vers classe 1 (mauvais client)
    colors = ['red' if x < 0 else 'green' for x in top_features['shap_value']]
    
    # Créer un graphique en barres horizontales
    # range(len(top_features)) : positions des barres sur l'axe Y
    # top_features['shap_value'] : hauteurs des barres (valeurs SHAP)
    # color=colors : couleur de chaque barre
    plt.barh(range(len(top_features)), top_features['shap_value'], color=colors)
    
    # Définir les labels de l'axe Y (noms des features)
    # range(len(top_features)) : positions
    # top_features['feature'] : labels (noms des features)
    plt.yticks(range(len(top_features)), top_features['feature'])
    
    # Ajouter un label à l'axe X
    plt.xlabel('Contribution SHAP', fontsize=12)
    # Ajouter un titre
    plt.title(f'Top {top_n} Features - Explication Locale', fontsize=14, fontweight='bold')
    
    # Ajouter une ligne verticale à x=0 pour séparer contributions positives et négatives
    # axvline() : ligne verticale
    # x=0 : position sur l'axe X
    # linestyle='--' : style de ligne pointillée
    plt.axvline(x=0, color='black', linestyle='--', linewidth=0.8)
    
    # Ajuster l'espacement
    plt.tight_layout()
    # Afficher le graphique
    plt.show()
