#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dashboard Streamlit pour le monitoring du modèle de scoring credit.

C'EST QUOI STREAMLIT ?
======================
Streamlit = framework Python pour créer des dashboards web et applications interactives
sans avoir besoin de connaître HTML/CSS/JavaScript (tout en Python !).

QU'EST-CE QUE CE DASHBOARD FAIT ?
==================================
Affiche :
1. KPIs (Key Performance Indicators) = chiffres clés
   - Total de prédictions effectuées
   - Score moyen de défaut
   - Distribution des scores

2. Détection de dérive (Data Drift)
   - Compare les données actuelles aux données d'entraînement
   - Détecte les changements dans le comportement des clients
   - Identifie les features qui se sont éloignées de la normale

3. Historique des prédictions
   - Affiche les prédictions récentes sous forme de tableau
   - Graphiques de tendance

4. Alertes et recommandations
   - Informe des problèmes détectés
   - Suggestions d'actions

ARCHITECTURE :
===============
Streamlit (interface web)
         ↓
   API FastAPI
         ↓
  PostgreSQL ← logs
         ↓
   Dashboard Streamlit (ce fichier)

FLUX DE DONNÉES :
1. Client remplit formulaire Streamlit
2. Streamlit envoie requête à API FastAPI
3. API fait une prédiction
4. API enregistre les données dans PostgreSQL
5. Dashboard Streamlit affiche les données de PostgreSQL en temps réel

TECHNOLOGIES UTILISÉES :
- Streamlit = framework pour le dashboard
- Plotly = visualisations (graphiques interactifs)
- PostgreSQL = base de données
- Pandas = manipulation de données
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from math import ceil
from pathlib import Path
import json
import logging
import os

# Import des fonctions de monitoring (récupère les données de PostgreSQL)
from src.monitoring_pg import (
    load_api_logs,
    compute_prediction_stats,
    detect_data_drift,
    generate_html_dashboard
)

# ============================================================================
# CONFIGURATION DU LOGGING
# ============================================================================
logger = logging.getLogger("streamlit")

HISTORY_PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

# ============================================================================
# IMPORT DES PARAMÈTRES DU MODÈLE ET FONCTIONS UTILITAIRES
# ============================================================================
from datetime import datetime, date
import requests
import time

# Charger le seuil optimal
OPTIMAL_THRESHOLD_PATH = Path("models/optimal_threshold_xgb.json")
try:
    with open(OPTIMAL_THRESHOLD_PATH, 'r') as f:
        optimal_params = json.load(f)
    THRESHOLD = optimal_params.get('threshold', 0.5)
except:
    THRESHOLD = 0.5

# API endpoint
API_URL = "http://api:8005/predict"

# ============================================================================
# FONCTIONS DE CONVERSION DE DATE
# ============================================================================
def birth_date_to_days(birth_date_str: str) -> int:
    """Convertit une date de naissance (format YYYY-MM-DD) en jours négatifs depuis aujourd'hui."""
    if not birth_date_str:
        return -15000
    try:
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        today = date.today()
        delta_days = (birth_date - today).days
        return delta_days
    except:
        return -15000

def employment_date_to_days(employment_date_str: str) -> int:
    """Convertit une date de début d'emploi (format YYYY-MM-DD) en jours négatifs depuis aujourd'hui."""
    if not employment_date_str:
        return -500
    try:
        employment_date = datetime.strptime(employment_date_str, "%Y-%m-%d").date()
        today = date.today()
        delta_days = (employment_date - today).days
        return delta_days
    except:
        return -500

# ============================================================================
# FONCTION DE PRÉDICTION
# ============================================================================
def make_prediction_streamlit(
    sk_id_curr: int,
    name_contract_type: str,
    code_gender: str,
    flag_own_car: str,
    flag_own_realty: str,
    amt_income: float,
    amt_credit: float,
    amt_annuity: float,
    amt_goods_price: float,
    cnt_children: int,
    cnt_fam_members: float,
    days_age: int,
    days_employed: int,
    name_education_type: str,
    name_family_status: str,
    name_housing_type: str,
    occupation_type: str,
    ext_source_1: float,
    ext_source_2: float,
    ext_source_3: float
):
    """Effectue une prédiction via l'API REST."""
    try:
        # Préparer le payload pour l'API
        payload = {
            "data": {
                "SK_ID_CURR": int(sk_id_curr),
                "NAME_CONTRACT_TYPE": name_contract_type,
                "CODE_GENDER": code_gender,
                "FLAG_OWN_CAR": 1 if flag_own_car == "Y" else 0,
                "FLAG_OWN_REALTY": 1 if flag_own_realty == "Y" else 0,
                "AMT_CREDIT": float(amt_credit),
                "AMT_ANNUITY": float(amt_annuity),
                "AMT_GOODS_PRICE": float(amt_goods_price),
                "AMT_INCOME_TOTAL": float(amt_income),
                "DAYS_BIRTH": int(days_age),
                "DAYS_EMPLOYED": int(days_employed),
                "CNT_CHILDREN": int(cnt_children),
                "NAME_EDUCATION_TYPE": name_education_type,
                "NAME_FAMILY_STATUS": name_family_status,
                "NAME_HOUSING_TYPE": name_housing_type,
                "OCCUPATION_TYPE": occupation_type,
                "CNT_FAM_MEMBERS": float(cnt_fam_members),
                "EXT_SOURCE_1": float(ext_source_1),
                "EXT_SOURCE_2": float(ext_source_2),
                "EXT_SOURCE_3": float(ext_source_3)
            }
        }
        
        # Appeller l'API avec retry
        max_retries = 5
        retry_delay = 0.5
        response = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(API_URL, json=payload, timeout=10)
                response.raise_for_status()
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    raise
        
        # Extraire le score de la réponse
        result = response.json()
        score = float(result.get('score', 0))
        cpu_usage_pct = result.get('cpu_usage_pct')
        gpu_usage_pct = result.get('gpu_usage_pct')
        gpu_memory_mb = result.get('gpu_memory_mb')
        compute_device = result.get('compute_device', 'cpu')
        
        # Décision basée sur le score
        if score < THRESHOLD:
            decision = "✅ CRÉDIT ACCEPTÉ"
            decision_color = "green"
        else:
            decision = "❌ CRÉDIT REFUSÉ"
            decision_color = "red"
        
        # Explication
        score_percentage = score * 100
        risk_level = "Faible 🟢" if score < 0.3 else ("Moyen 🟠" if score < 0.6 else "Élevé 🔴")
        
        return {
            'score': score,
            'score_percentage': score_percentage,
            'decision': decision,
            'risk_level': risk_level,
            'threshold': THRESHOLD,
            'cpu_usage_pct': cpu_usage_pct,
            'gpu_usage_pct': gpu_usage_pct,
            'gpu_memory_mb': gpu_memory_mb,
            'compute_device': compute_device,
            'success': True
        }
    
    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': "Erreur de connexion : L'API n'est pas accessible."
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Erreur lors de la prédiction : {str(e)}"
        }

# ============================================================================
# CONFIGURATION DE LA PAGE STREAMLIT
# ============================================================================
# st.set_page_config = paramètres de la page web
# - page_title = titre dans l'onglet du navigateur
# - layout = "wide" = utiliser la largeur complète de l'écran
# - initial_sidebar_state = "expanded" = afficher la barre latérale par défaut
st.set_page_config(
    page_title="Credit Scoring Monitor",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# STYLE CSS PERSONNALISÉ - PALETTE DE COULEURS PROFESSIONNELLE
# ============================================================================
# CSS = Cascading Style Sheets = langage pour styliser les pages web
# Streamlit nous permet d'injecter du CSS pour personnaliser l'apparence

# PALETTE DE COULEURS :
# #0B162C = bleu très foncé (fond principal)
# #1C2942 = bleu foncé (cartes, conteneurs)
# #3B556D = bleu gris (éléments tertiaires)
# #5FC2BA = turquoise (accents, boutons, mise en avant)

st.markdown("""
    <style>
    :root {
        --primary-dark: #0B162C;
        --primary-mid: #1C2942;
        --primary-light: #3B556D;
        --accent: #5FC2BA;
    }
    
    body, .main {
        background-color: #0B162C;
        color: #FFFFFF;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0B162C 0%, #1C2942 100%);
    }
    
    [data-testid="stHeader"] {
        background: #1C2942;
        padding: 2rem 1rem;
    }
    
    [data-testid="stSidebar"] {
        background: #0B162C;
        color: #FFFFFF;
    }
    
    h1, h2, h3 {
        color: #5FC2BA;
        font-weight: 600;
        margin-top: 1.5rem;
    }
    
    .stMetric {
        background-color: #1C2942;
        padding: 1.5rem;
        border-radius: 0.75rem;
        border-left: 4px solid #5FC2BA;
    }
    
    .stMetricValue {
        color: #5FC2BA;
        font-size: 2rem;
    }
    
    .stMetricLabel {
        font-size: 0.9rem;
        color: #FFFFFF;
    }
    
    [data-testid="stMarkdownContainer"] {
        color: #FFFFFF;
    }
    
    .stDataFrame {
        background-color: #1C2942 !important;
        color: #FFFFFF !important;
    }
    
    [data-testid="stButton"] > button {
        background: linear-gradient(90deg, #5FC2BA 0%, #3B556D 100%);
        color: #0B162C;
        font-weight: 600;
        border: none;
    }
    
    [data-testid="stButton"] > button:hover {
        background: linear-gradient(90deg, #3B556D 0%, #5FC2BA 100%);
    }
    
    /* Style pour le texte du download button et tous les buttons */
    button {
        color: #0B162C !important;
    }
    
    button p, button span {
        color: #0B162C !important;
    }
    
    .stSelectbox, .stSlider, .stMultiSelect, .stCheckbox {
        color: #FFFFFF;
    }
    
    .stWarning, .stError, .stSuccess, .stInfo {
        background-color: #1C2942 !important;
        color: #FFFFFF !important;
        border-left: 4px solid #5FC2BA;
    }

    .history-header-cell {
        font-size: 0.80rem;
        font-weight: 700;
        color: #5FC2BA;
        margin-bottom: 0.2rem;
    }

    .history-row-cell {
        font-size: 0.82rem;
        line-height: 1.1;
        padding: 0.10rem 0;
        margin: 0;
    }

    .history-row-separator {
        height: 1px;
        background: rgba(95, 194, 186, 0.18);
        margin: 0.2rem 0 0.3rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# unsafe_allow_html=True = autoriser le HTML/CSS personnalisé
# (normalement Streamlit désactive cela pour des raisons de sécurité)

# ============================================================================
# HEADER - TITRE PRINCIPAL
# ============================================================================
# st.title() = affiche un titre principal (h1 en HTML)

# Récupérer les variables d'environnement pour l'instance du dashboard
environment_name = os.getenv("ENVIRONMENT_NAME", "DEV LOCAL")
environment_color = os.getenv("ENVIRONMENT_COLOR", "#FF0000")

# Afficher le titre avec la couleur de l'environnement
title_html = f"""
<h1 style="color: {environment_color}; margin-bottom: 0;">
    Dashboard de Monitoring - Scoring Credit
    <span style="font-size: 0.7em; margin-left: 1rem; background: {environment_color}; color: white; padding: 0.3rem 0.8rem; border-radius: 0.3rem;">
        {environment_name}
    </span>
</h1>
"""
st.markdown(title_html, unsafe_allow_html=True)

# st.markdown() = affiche du texte formaté (markdown = format simple)
st.markdown("Suivi en temps réel du modèle XGBoost")

# ============================================================================
# SIDEBAR - BARRE LATÉRALE AVEC NAVIGATION
# ============================================================================
# st.sidebar = tous les widgets (boutons, listes, etc.) s'affichent dans la barre latérale gauche

# Ajouter une section "Navigation" 
st.sidebar.markdown("### Navigation")

# st.sidebar.radio() = boutons radio (sélectionner une seule option)
# Permet de naviguer entre différentes pages du dashboard
page = st.sidebar.radio(
    "Sélectionnez une page",
    ["Dashboard", "Prédiction", "Drift Detection", "Historique", "À propos"]
)

# ============================================================================
# AUTO-REFRESH - RAFRAÎCHIR LA PAGE AUTOMATIQUEMENT
# ============================================================================
st.sidebar.markdown("---")  # Ligne de séparation

# Checkbox = case à cocher (vrai/faux)
# value=True = coché par défaut
auto_refresh = st.sidebar.checkbox("Auto-refresh (5s)", value=True)

# Si auto_refresh est True, rafraîchir la page toutes les 5 secondes
if auto_refresh:
    st.markdown("""
        <script>
        setTimeout(function() {
            window.location.reload();
        }, 5000);
        </script>
    """, unsafe_allow_html=True)


def render_drift_comparison(comparison: dict):
    """Affiche une comparaison de drift sur les champs d'entrée métier."""
    variables = comparison.get('variables', [])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        drift_color = "red" if comparison.get('has_drift') else "green"
        status_text = "🚨 DRIFT DÉTECTÉ" if comparison.get('has_drift') else "✅ PAS DE DRIFT"
        st.markdown(f"<h3 style='color: {drift_color};'>{status_text}</h3>", unsafe_allow_html=True)
    with col2:
        st.metric("Score de dérive", f"{comparison.get('drift_score', 0) * 100:.2f}%")
    with col3:
        st.metric("Variables comparées", comparison.get('num_features_analyzed', 0))
    with col4:
        st.metric("Prédictions analysées", comparison.get('recent_sample_size', 0))

    st.info(
        f"📊 Référence : `{comparison.get('reference_path', 'N/A')}` | "
        f"{comparison.get('details', 'Aucun détail disponible')}"
    )

    if not variables:
        st.warning("Aucune variable comparable pour cette vue.")
        return

    variables_sorted = sorted(variables, key=lambda item: item['change_pct'], reverse=True)

    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("✅ OK", len([var for var in variables if var['status_code'] == 'ok']))
    with summary_cols[1]:
        st.metric("🟡 Bas", len([var for var in variables if var['status_code'] == 'low']))
    with summary_cols[2]:
        st.metric("🟠 Moyen", len([var for var in variables if var['status_code'] == 'medium']))
    with summary_cols[3]:
        st.metric("🚨 Critique", len([var for var in variables if var['status_code'] == 'critical']))

    variables_df = pd.DataFrame([
        {
            'Statut': var['status'],
            'Variable': var['feature'],
            'Nature': var.get('comparison_type', 'N/A'),
            'Référence': var.get('reference_display', round(var['avg_reference'], 4)),
            'Récent': var.get('recent_display', round(var['avg_recent'], 4)),
            'Écart (%)': round(var['change_pct'], 2),
            'Champ source': var.get('formula', var['feature'])
        }
        for var in variables_sorted
    ])
    st.dataframe(variables_df, use_container_width=True, hide_index=True)

    top_vars = variables_sorted[:10]
    colors = [
        '#FF6B6B' if var['status_code'] == 'critical' else '#FF9F1C' if var['status_code'] == 'medium' else '#FFD700' if var['status_code'] == 'low' else '#90EE90'
        for var in top_vars
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=[var['feature'] for var in top_vars],
        x=[var['change_pct'] for var in top_vars],
        orientation='h',
        marker=dict(color=colors, line=dict(color='#5FC2BA', width=2)),
        text=[f"{var['change_pct']:.2f}%" for var in top_vars],
        textposition='auto'
    ))
    fig.update_layout(
        title="Top 10 variables avec le plus d'écart",
        xaxis_title="Écart relatif (%)",
        yaxis_title="Variable",
        height=420,
        plot_bgcolor='#1C2942',
        paper_bgcolor='#0B162C',
        xaxis=dict(gridcolor='#3B556D'),
        yaxis=dict(gridcolor='#3B556D'),
        font=dict(color='#FFFFFF'),
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)

    correspondence_df = variables_df[['Variable', 'Nature', 'Champ source']].drop_duplicates()
    with st.expander("Champs suivis", expanded=False):
        st.dataframe(correspondence_df, use_container_width=True, hide_index=True)

# ============================================================================
# PAGE 1 : DASHBOARD PRINCIPAL
# ============================================================================
if page == "Dashboard":
    try:
        # Charger les données
        logs_df = load_api_logs()
        prediction_stats = compute_prediction_stats()
        
        # S'assurer que tous les KPIs ont des valeurs par défaut
        prediction_stats.setdefault('total', 0)
        prediction_stats.setdefault('avg_score', 0.0)
        prediction_stats.setdefault('min_score', 0.0)
        prediction_stats.setdefault('max_score', 0.0)
        prediction_stats.setdefault('today_count', 0)
        prediction_stats.setdefault('avg_cpu_usage_pct', 0.0)
        prediction_stats.setdefault('avg_gpu_usage_pct', 0.0)
        prediction_stats.setdefault('avg_gpu_memory_mb', 0.0)
        
        if logs_df is not None and not logs_df.empty:
            # KPIs - Première ligne
            st.markdown("## KPIs Principales")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    label="Total Prédictions",
                    value=f"{prediction_stats['total']:,}",
                    delta=f"+{prediction_stats.get('today_count', 0)} aujourd'hui"
                )
            
            with col2:
                st.metric(
                    label="Score Moyen",
                    value=f"{prediction_stats['avg_score']:.4f}",
                    delta=None
                )
            
            with col3:
                st.metric(
                    label="Min Score",
                    value=f"{prediction_stats['min_score']:.4f}",
                )
            
            with col4:
                st.metric(
                    label="Max Score",
                    value=f"{prediction_stats['max_score']:.4f}",
                )
            
            # Graphiques - Distribution des scores
            st.markdown("## Distribution des Scores")
            col1, col2 = st.columns(2)
            
            with col1:
                # Histogram
                fig_hist = px.histogram(
                    logs_df,
                    x='score',
                    nbins=50,
                    title="Histogramme des Scores",
                    labels={'score': 'Score', 'count': 'Nombre'}
                )
                fig_hist.update_layout(
                    hovermode='x unified',
                    height=400,
                    showlegend=False,
                    plot_bgcolor='#1C2942',
                    paper_bgcolor='#0B162C',
                    xaxis=dict(gridcolor='#3B556D'),
                    yaxis=dict(gridcolor='#3B556D'),
                    font=dict(color='#FFFFFF')
                )
                st.plotly_chart(fig_hist, use_container_width=True)
            
            with col2:
                # Tendance temporelle
                logs_df_sorted = logs_df.sort_values('timestamp')
                fig_trend = px.scatter(
                    logs_df_sorted,
                    x='timestamp',
                    y='score',
                    opacity=0.6,
                    title="Tendance des Scores (Temporelle)",
                    labels={'timestamp': 'Temps', 'score': 'Score'}
                )
                fig_trend.add_hline(
                    y=prediction_stats['avg_score'],
                    line_dash="dash",
                    line_color="#5FC2BA",
                    annotation_text="Moyenne",
                    annotation_position="right"
                )
                fig_trend.update_layout(
                    height=400,
                    hovermode='x unified',
                    plot_bgcolor='#1C2942',
                    paper_bgcolor='#0B162C',
                    xaxis=dict(gridcolor='#3B556D'),
                    yaxis=dict(gridcolor='#3B556D'),
                    font=dict(color='#FFFFFF')
                )
                st.plotly_chart(fig_trend, use_container_width=True)
            
            # Latence
            st.markdown("## Performance - Latence")
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig_latency = px.box(
                    logs_df,
                    y='latency_seconds',
                    title="Distribution de la Latence (en secondes)",
                    labels={'latency_seconds': 'Latence (s)'}
                )
                fig_latency.update_layout(
                    showlegend=False,
                    height=300,
                    plot_bgcolor='#1C2942',
                    paper_bgcolor='#0B162C',
                    xaxis=dict(gridcolor='#3B556D'),
                    yaxis=dict(gridcolor='#3B556D'),
                    font=dict(color='#FFFFFF')
                )
                st.plotly_chart(fig_latency, use_container_width=True)
            
            with col2:
                avg_latency = logs_df['latency_seconds'].mean()
                st.info(f"Latence moyenne : **{avg_latency*1000:.2f} ms**")
                st.info(f"CPU moyen : **{prediction_stats.get('avg_cpu_usage_pct', 0.0):.2f}%**")
                st.info(f"GPU moyen : **{prediction_stats.get('avg_gpu_usage_pct', 0.0):.2f}%**")
                st.info(f"Mémoire GPU moyenne : **{prediction_stats.get('avg_gpu_memory_mb', 0.0):.2f} MB**")

            resource_columns = {'cpu_usage_pct', 'gpu_usage_pct'}
            if resource_columns.intersection(set(logs_df.columns)):
                st.markdown("## Performance - Ressources de Calcul")
                resource_df = logs_df.sort_values('timestamp').copy()
                resource_melt = resource_df.melt(
                    id_vars='timestamp',
                    value_vars=[col for col in ['cpu_usage_pct', 'gpu_usage_pct'] if col in resource_df.columns],
                    var_name='resource_type',
                    value_name='usage_pct'
                )
                resource_melt = resource_melt.dropna(subset=['usage_pct'])
                if not resource_melt.empty:
                    resource_melt['resource_type'] = resource_melt['resource_type'].map({
                        'cpu_usage_pct': 'CPU (%)',
                        'gpu_usage_pct': 'GPU (%)',
                    })
                    fig_resources = px.line(
                        resource_melt,
                        x='timestamp',
                        y='usage_pct',
                        color='resource_type',
                        title="Utilisation CPU/GPU pendant les prédictions",
                        labels={'usage_pct': 'Utilisation (%)', 'timestamp': 'Temps', 'resource_type': 'Ressource'}
                    )
                    fig_resources.update_layout(
                        height=320,
                        plot_bgcolor='#1C2942',
                        paper_bgcolor='#0B162C',
                        xaxis=dict(gridcolor='#3B556D'),
                        yaxis=dict(gridcolor='#3B556D'),
                        font=dict(color='#FFFFFF')
                    )
                    st.plotly_chart(fig_resources, use_container_width=True)
        
        else:
            st.warning("Aucun log disponible. Faites quelques prédictions pour voir les données.")
    
    except Exception as e:
        st.error(f"Erreur lors du chargement du dashboard : {str(e)}")

# ============================================================================
# PAGE 2 : FORMULAIRE DE PRÉDICTION
# ============================================================================
elif page == "Prédiction":
    try:
        st.markdown("## Formulaire de Saisie - Prédiction de Crédit")
        st.markdown("Remplissez les informations du client pour obtenir une prédiction de crédit.")
        
        with st.form("prediction_form"):
            # Colonne 1 : Informations Personnelles
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Informations Personnelles")
                
                sk_id_curr = st.number_input(
                    "Client ID",
                    value=100003,
                    min_value=1,
                    step=1,
                    help="Identifiant unique du client"
                )
                
                code_gender = st.radio(
                    "Genre",
                    options=["M", "F"],
                    horizontal=True
                )
                
                name_contract_type = st.radio(
                    "Type de Contrat",
                    options=["Cash loans", "Revolving loans"],
                    horizontal=False
                )
                
                flag_own_car = st.radio(
                    "Possède une Voiture",
                    options=["Y", "N"],
                    horizontal=True
                )
                
                flag_own_realty = st.radio(
                    "Possède un Bien Immobilier",
                    options=["Y", "N"],
                    horizontal=True
                )
                
                # Situation Familiale
                st.markdown("### Situation Familiale")
                
                cnt_children = st.slider(
                    "Nombre d'Enfants",
                    min_value=0,
                    max_value=10,
                    value=1
                )
                
                cnt_fam_members = st.number_input(
                    "Nombre de Membres du Foyer",
                    value=2.0,
                    min_value=1.0,
                    step=0.5
                )
                
                name_family_status = st.selectbox(
                    "Statut Familial",
                    options=[
                        "Married",
                        "Single / not married",
                        "Widow",
                        "Separated",
                        "Civil marriage"
                    ],
                    index=1
                )
                
                name_housing_type = st.selectbox(
                    "Type de Logement",
                    options=[
                        "House / apartment",
                        "With parents",
                        "Municipal apartment",
                        "Rented apartment",
                        "Office apartment",
                        "Co-op apartment"
                    ]
                )
            
            with col2:
                st.markdown("### Données Financières")
                
                amt_income = st.number_input(
                    "Revenu Annuel (EUR)",
                    value=60000.0,
                    min_value=0.0,
                    step=1000.0,
                    help="Revenu brut annuel du client"
                )
                
                amt_credit = st.number_input(
                    "Montant du Crédit (EUR)",
                    value=350000.0,
                    min_value=0.0,
                    step=10000.0,
                    help="Montant total du crédit demandé"
                )
                
                amt_annuity = st.number_input(
                    "Annuité (EUR)",
                    value=18000.0,
                    min_value=0.0,
                    step=1000.0,
                    help="Montant annuel de remboursement"
                )
                
                amt_goods_price = st.number_input(
                    "Prix des Biens (EUR)",
                    value=350000.0,
                    min_value=0.0,
                    step=10000.0,
                    help="Prix des biens à financer"
                )
                
                # Emploi & Éducation
                st.markdown("### Emploi & Éducation")
                
                name_education_type = st.selectbox(
                    "Niveau d'Éducation",
                    options=[
                        "Lower secondary",
                        "Secondary / secondary special",
                        "Incomplete higher",
                        "Higher education",
                        "Academic degree"
                    ],
                    index=1
                )
                
                occupation_type = st.selectbox(
                    "Occupation",
                    options=[
                        "Sales staff",
                        "Managers",
                        "Laborers",
                        "Core staff",
                        "Drivers",
                        "Accountants",
                        "Medicine staff",
                        "High skill tech staff",
                        "Low-skill Laborers",
                        "Unknown"
                    ]
                )
                
                # Dates
                st.markdown("### Dates")
                
                birth_date = st.date_input(
                    "Date de Naissance",
                    value=date(1984, 6, 1),
                    help="Format: YYYY-MM-DD"
                )
                
                employment_date = st.date_input(
                    "Date de Début d'Emploi",
                    value=date(2023, 8, 1),
                    help="Format: YYYY-MM-DD"
                )
            
            # Scores Externes
            st.markdown("### Scores Externes")
            col3, col4, col5 = st.columns(3)
            
            with col3:
                ext_source_1 = st.slider(
                    "EXT_SOURCE_1",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.55,
                    step=0.01
                )
            
            with col4:
                ext_source_2 = st.slider(
                    "EXT_SOURCE_2",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.50,
                    step=0.01
                )
            
            with col5:
                ext_source_3 = st.slider(
                    "EXT_SOURCE_3",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.45,
                    step=0.01
                )
            
            # Bouton de soumission
            st.markdown("---")
            submit_button = st.form_submit_button("🎯 Faire une Prédiction", use_container_width=True)
        
        # Résultats
        if submit_button:
            # Convertir les dates en jours
            days_age = birth_date_to_days(birth_date.strftime("%Y-%m-%d"))
            days_employed = employment_date_to_days(employment_date.strftime("%Y-%m-%d"))
            
            # Afficher l'état du traitement
            with st.spinner("⏳ Traitement de la prédiction en cours..."):
                result = make_prediction_streamlit(
                    sk_id_curr=sk_id_curr,
                    name_contract_type=name_contract_type,
                    code_gender=code_gender,
                    flag_own_car=flag_own_car,
                    flag_own_realty=flag_own_realty,
                    amt_income=amt_income,
                    amt_credit=amt_credit,
                    amt_annuity=amt_annuity,
                    amt_goods_price=amt_goods_price,
                    cnt_children=cnt_children,
                    cnt_fam_members=cnt_fam_members,
                    days_age=days_age,
                    days_employed=days_employed,
                    name_education_type=name_education_type,
                    name_family_status=name_family_status,
                    name_housing_type=name_housing_type,
                    occupation_type=occupation_type,
                    ext_source_1=ext_source_1,
                    ext_source_2=ext_source_2,
                    ext_source_3=ext_source_3
                )
            
            if result['success']:
                st.markdown("---")
                st.markdown("## 📊 Résultats de la Prédiction")
                
                # Afficher les metriques
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "Score de Défaut",
                        f"{result['score']:.4f}",
                        help="Probabilité de défaut (0=Bon, 1=Mauvais)"
                    )
                
                with col2:
                    st.metric(
                        "Risque",
                        result['risk_level']
                    )
                
                with col3:
                    st.metric(
                        "Décision",
                        result['decision']
                    )
                
                with col4:
                    st.metric(
                        "Seuil",
                        f"{result['threshold']:.4f}"
                    )

                resource_col1, resource_col2, resource_col3, resource_col4 = st.columns(4)
                with resource_col1:
                    st.metric(
                        "CPU prediction",
                        f"{(result.get('cpu_usage_pct') or 0):.2f}%"
                    )
                with resource_col2:
                    st.metric(
                        "GPU prediction",
                        f"{(result.get('gpu_usage_pct') or 0):.2f}%"
                    )
                with resource_col3:
                    st.metric(
                        "Mémoire GPU",
                        f"{(result.get('gpu_memory_mb') or 0):.2f} MB"
                    )
                with resource_col4:
                    st.metric(
                        "Device",
                        str(result.get('compute_device', 'cpu'))
                    )
                
                # Gauge chart
                fig = go.Figure(data=[go.Indicator(
                    mode="gauge+number+delta",
                    value=result['score_percentage'],
                    title={'text': "Score de Défaut (%)"},
                    delta={'reference': THRESHOLD * 100},
                    gauge={
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 45], 'color': "#90EE90"},
                            {'range': [45, 60], 'color': "#FFD700"},
                            {'range': [60, 100], 'color': "#FF6B6B"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': THRESHOLD * 100
                        }
                    }
                )])
                fig.update_layout(
                    paper_bgcolor="#1C2942",
                    font=dict(color="white", size=12),
                    margin=dict(l=10, r=10, t=50, b=10)
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Interprétation
                st.markdown("### 📝 Interprétation")
                interpretation = f"""
                **Score de Défaut :** {result['score']:.4f} ({result['score_percentage']:.2f}%)
                
                **Niveau de Risque :** {result['risk_level']}
                
                - Un score proche de **0** = Faible risque (client solvable)
                - Un score proche de **1** = Risque élevé (client à risque de défaut)
                
                **Seuil de Décision :** {result['threshold']:.4f}

                **CPU pendant la prédiction :** {(result.get('cpu_usage_pct') or 0):.2f}%

                **GPU pendant la prédiction :** {(result.get('gpu_usage_pct') or 0):.2f}%

                **Device utilisé :** {result.get('compute_device', 'cpu')}
                
                **Recommandation :** {result['decision']}
                
                **Note :** Cette prédiction est automatiquement enregistrée dans la base de données pour le monitoring.
                """
                st.markdown(interpretation)
                
                st.success("✅ Prédiction effectuée avec succès et enregistrée dans la base de données.")
            
            else:
                st.error(f"❌ Erreur : {result['error']}")
    
    except Exception as e:
        st.error(f"Erreur lors du traitement : {str(e)}")

# ============================================================================
# PAGE 3 : DRIFT DETECTION
# ============================================================================
elif page == "Drift Detection":
    try:
        logs_df = load_api_logs()
        drift_stats = detect_data_drift(logs_df)
        comparison = drift_stats.get('reference_comparisons', {}).get('raw_input')
        
        st.markdown("## Détection de Drift - Comparaison avec Données d'Entraînement")
        st.info(
            "📊 La comparaison est limitée aux champs d'entrée métier du formulaire et des échantillons JSON. "
            "Les valeurs affichées correspondent aux moyennes ou modalités dominantes calculées sur l'ensemble des prédictions chargées : "
            "genre, voiture, immobilier, enfants, revenus, crédit, annuité, prix des biens, éducation, statut familial, logement, "
            "âge/emploi, profession, taille du foyer et scores externes."
        )
        
        # Debug: Afficher info sur les données récentes
        if logs_df is not None and not logs_df.empty:
            st.info(f"📈 Données chargées : {len(logs_df)} lignes")

        if comparison:
            render_drift_comparison(comparison)
        else:
            st.warning(f"📊 {drift_stats.get('details', 'Analyse de dérive indisponible.')}")
        
        # Section DEBUG
        with st.expander("🔧 Diagnostic - Données Brutes (caché par défaut)", expanded=False):
            st.markdown("### Analyse des données")
            
            # Afficher stat du dataframe
            if logs_df is not None and not logs_df.empty:
                st.write(f"**Total lignes :** {len(logs_df)}")
                st.write(f"**Colonnes :** {list(logs_df.columns)}")
                
                # Afficher les 5 premières lignes input_data
                st.markdown("#### Premières entrées input_data :")
                try:
                    for idx, row in logs_df.head(5).iterrows():
                        if pd.notna(row.get('input_data')):
                            try:
                                if isinstance(row['input_data'], str):
                                    data = json.loads(row['input_data'])
                                else:
                                    data = row['input_data']
                                st.json(data)
                            except Exception as e:
                                st.error(f"Erreur parsing: {str(e)}")
                                st.write(f"Valeur brute: {row['input_data'][:200] if isinstance(row['input_data'], str) else row['input_data']}")
                except Exception as e:
                    st.error(f"Erreur d'affichage: {str(e)}")
                
                # Stats du drift_stats
                st.markdown("#### Stats de drift retournées :")
                st.json({k: v for k, v in drift_stats.items() if k != 'variables'})
            else:
                st.warning("Pas de données dans les logs")
        
        # Recommandations
        st.markdown("---")
        st.markdown("### 📋 Recommandations")
        
        if drift_stats.get('has_drift'):
            st.error("""
            ### ⚠️ DÉRIVE DÉTECTÉE - Actions Requises
            
            1. **🔍 Enquête approfondie**
               - Vérifier la source des données en production
               - Analyser les variables critiques identifiées
               - Contacter l'équipe métier pour comprendre les changements récents
            
            2. **🛠️ Actions correctives**
               - Effectuer un re-entraînement du modèle sur données récentes
               - Mettre à jour les seuils de décision si nécessaire
               - Valider les performances sur les nouvelles données
            
            3. **📊 Suivi intensifié**
               - Augmenter la fréquence de monitoring (passages à 4 fois/jour)
               - Collecter plus de données pour analyse approfondie
               - Préparer mise à jour du modèle
            """)
        else:
            st.success("""
            ### ✅ MODÈLE STABLE - Pas d'Action Immédiate
            
            - ✅ Les variables sont cohérentes avec les données d'entraînement
            - ✅ La dérive moyenne est sous contrôle
            - ✅ Aucune action immédiate requise
            - ✅ Surveillance continue recommandée (vérification journalière)
            - ✅ Prochaine vérification complète : Dans 7 jours
            """)
    
    except Exception as e:
        st.error(f"Erreur lors de la détection de drift : {str(e)}")
        logger.error(f"Drift detection error: {str(e)}")

# ============================================================================
# PAGE 4 : HISTORIQUE
# ============================================================================
elif page == "Historique":
    try:
        logs_df = load_api_logs()
        
        if logs_df is not None and not logs_df.empty:
            st.markdown("## Historique Complet des Prédictions")
            
            # Filtres
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                min_score = st.slider(
                    "Score Min",
                    0.0,
                    1.0,
                    0.0
                )
            
            with col2:
                max_score = st.slider(
                    "Score Max",
                    0.0,
                    1.0,
                    1.0
                )
            
            with col3:
                pred_type = st.multiselect(
                    "Type de prédiction",
                    logs_df['prediction_type'].unique(),
                    default=logs_df['prediction_type'].unique()
                )

            with col4:
                client_search = st.text_input(
                    "Recherche client_id",
                    value="",
                    placeholder="Ex: 100002"
                ).strip()

            client_ids = logs_df['client_id'].fillna('').astype(str)
            client_filter = client_ids.str.contains(client_search, case=False, na=False) if client_search else pd.Series(True, index=logs_df.index)
            
            # Filtrer les données
            filtered_df = logs_df[
                (logs_df['score'] >= min_score) &
                (logs_df['score'] <= max_score) &
                (logs_df['prediction_type'].isin(pred_type)) &
                client_filter
            ].sort_values('timestamp', ascending=False)
            
            st.write(f"**Total : {len(filtered_df)} prédictions**")

            if filtered_df.empty:
                st.info("Aucune prédiction ne correspond aux filtres actuels.")
            else:
                if 'history_page_size' not in st.session_state:
                    st.session_state.history_page_size = 25
                if 'history_page' not in st.session_state:
                    st.session_state.history_page = 1
                if 'history_selected_log_index' not in st.session_state:
                    st.session_state.history_selected_log_index = None

                controls_col1, controls_col2, controls_col3 = st.columns([1, 1, 2])

                with controls_col1:
                    page_size = st.selectbox(
                        "Lignes par page",
                        HISTORY_PAGE_SIZE_OPTIONS,
                        index=HISTORY_PAGE_SIZE_OPTIONS.index(st.session_state.history_page_size)
                        if st.session_state.history_page_size in HISTORY_PAGE_SIZE_OPTIONS else 1,
                        key="history_page_size_selector"
                    )
                    st.session_state.history_page_size = page_size

                total_pages = max(1, ceil(len(filtered_df) / st.session_state.history_page_size))
                if st.session_state.history_page > total_pages:
                    st.session_state.history_page = total_pages

                with controls_col2:
                    page_number = st.number_input(
                        "Page",
                        min_value=1,
                        max_value=total_pages,
                        value=st.session_state.history_page,
                        step=1,
                        key="history_page_number"
                    )
                    st.session_state.history_page = page_number

                with controls_col3:
                    st.caption(
                        "Cliquez sur Voir dans la ligne voulue pour afficher le détail."
                    )
                    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 3])
                    with nav_col1:
                        if st.button("← Précédente", use_container_width=True, disabled=st.session_state.history_page <= 1):
                            st.session_state.history_page -= 1
                            st.rerun()
                    with nav_col2:
                        if st.button("Suivante →", use_container_width=True, disabled=st.session_state.history_page >= total_pages):
                            st.session_state.history_page += 1
                            st.rerun()
                    with nav_col3:
                        start_item = (st.session_state.history_page - 1) * st.session_state.history_page_size + 1
                        end_item = min(len(filtered_df), st.session_state.history_page * st.session_state.history_page_size)
                        st.write(f"Page {st.session_state.history_page}/{total_pages} | Lignes {start_item}-{end_item}")

                page_start = (st.session_state.history_page - 1) * st.session_state.history_page_size
                page_end = page_start + st.session_state.history_page_size
                page_df = filtered_df.iloc[page_start:page_end].copy()

                header_cols = st.columns([2.0, 1.1, 1.2, 0.8, 0.9, 1.6, 0.8])
                header_cols[0].markdown("<div class='history-header-cell'>Timestamp</div>", unsafe_allow_html=True)
                header_cols[1].markdown("<div class='history-header-cell'>Client</div>", unsafe_allow_html=True)
                header_cols[2].markdown("<div class='history-header-cell'>Type</div>", unsafe_allow_html=True)
                header_cols[3].markdown("<div class='history-header-cell'>Score</div>", unsafe_allow_html=True)
                header_cols[4].markdown("<div class='history-header-cell'>Latence (s)</div>", unsafe_allow_html=True)
                header_cols[5].markdown("<div class='history-header-cell'>Ressources</div>", unsafe_allow_html=True)
                header_cols[6].markdown("<div class='history-header-cell'>Action</div>", unsafe_allow_html=True)

                for row_index, row in page_df.iterrows():
                    row_cols = st.columns([2.0, 1.1, 1.2, 0.8, 0.9, 1.6, 0.8])
                    row_cols[0].markdown(f"<div class='history-row-cell'>{row['timestamp']}</div>", unsafe_allow_html=True)
                    row_cols[1].markdown(f"<div class='history-row-cell'>{row['client_id']}</div>", unsafe_allow_html=True)
                    row_cols[2].markdown(f"<div class='history-row-cell'>{row['prediction_type']}</div>", unsafe_allow_html=True)
                    row_cols[3].markdown(f"<div class='history-row-cell'>{float(row['score']):.4f}</div>", unsafe_allow_html=True)
                    row_cols[4].markdown(f"<div class='history-row-cell'>{float(row['latency_seconds']):.4f}</div>", unsafe_allow_html=True)
                    cpu_display = f"CPU {float(row['cpu_usage_pct']):.1f}%" if pd.notna(row.get('cpu_usage_pct')) else "CPU n/a"
                    gpu_display = f"GPU {float(row['gpu_usage_pct']):.1f}%" if pd.notna(row.get('gpu_usage_pct')) else "GPU n/a"
                    device_display = row.get('compute_device') or 'cpu'
                    row_cols[5].markdown(f"<div class='history-row-cell'>{cpu_display} | {gpu_display}<br>{device_display}</div>", unsafe_allow_html=True)

                    button_label = "Ouvert" if row_index == st.session_state.history_selected_log_index else "Voir"
                    button_type = "primary" if row_index == st.session_state.history_selected_log_index else "secondary"
                    if row_cols[6].button(button_label, key=f"history_view_{row_index}", use_container_width=True, type=button_type):
                        st.session_state.history_selected_log_index = row_index
                        st.rerun()

                    st.markdown("<div class='history-row-separator'></div>", unsafe_allow_html=True)

                if st.session_state.history_selected_log_index not in filtered_df.index:
                    st.session_state.history_selected_log_index = None
            
            # ====================================================================
            # DÉTAILS DE LA SÉLECTION
            # ====================================================================
            if st.session_state.get('history_selected_log_index') in filtered_df.index:
                selected_log = filtered_df.loc[st.session_state.history_selected_log_index]
                
                st.markdown("---")
                st.markdown("### 📊 Détails de la Prédiction Sélectionnée")
                
                # ================================================================
                # SECTION 1 : DÉTAILS DE LA FICHE SAISIE (INPUT)
                # ================================================================
                with st.expander("📝 Détail de la Fiche Saisie (Features)", expanded=True):
                    try:
                        # Récupérer et parser les données d'entrée
                        if isinstance(selected_log['input_data'], str):
                            input_data = json.loads(selected_log['input_data'])
                        else:
                            input_data = selected_log['input_data']
                        
                        # Afficher les data sous forme de tableau formaté
                        input_df = pd.DataFrame({
                            'Feature': list(input_data.keys()),
                            'Valeur': list(input_data.values())
                        })
                        
                        # Colonnes à grouper par catégories
                        st.write(f"**Identifiant Client:** `{input_df[input_df['Feature']=='SK_ID_CURR']['Valeur'].values[0] if 'SK_ID_CURR' in input_data else 'N/A'}`")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Données Personnelles :**")
                            personal_features = ['CODE_GENDER', 'NAME_FAMILY_STATUS', 'NAME_HOUSING_TYPE', 'NAME_EDUCATION_TYPE', 'OCCUPATION_TYPE']
                            personal_data = {k: input_data.get(k, 'N/A') for k in personal_features if k in input_data}
                            if personal_data:
                                st.json(personal_data)
                        
                        with col2:
                            st.write("**Données Financières :**")
                            financial_features = ['AMT_INCOME_TOTAL', 'AMT_CREDIT', 'AMT_ANNUITY', 'AMT_GOODS_PRICE']
                            financial_data = {k: f"${input_data.get(k, 0):,.0f}" for k in financial_features if k in input_data}
                            if financial_data:
                                st.json(financial_data)
                        
                        col3, col4 = st.columns(2)
                        
                        with col3:
                            st.write("**Situation Professionnelle :**")
                            work_features = ['DAYS_EMPLOYED', 'DAYS_BIRTH', 'CNT_CHILDREN', 'CNT_FAM_MEMBERS', 'FLAG_OWN_CAR', 'FLAG_OWN_REALTY']
                            work_data = {k: input_data.get(k, 'N/A') for k in work_features if k in input_data}
                            if work_data:
                                st.json(work_data)
                        
                        with col4:
                            st.write("**Scores Externes :**")
                            ext_features = ['EXT_SOURCE_1', 'EXT_SOURCE_2', 'EXT_SOURCE_3', 'NAME_CONTRACT_TYPE']
                            ext_data = {k: input_data.get(k, 'N/A') for k in ext_features if k in input_data}
                            if ext_data:
                                st.json(ext_data)
                        
                        # Tableau complet
                        st.write("**Toutes les features :**")
                        st.dataframe(input_df, use_container_width=True, hide_index=True)
                    
                    except Exception as e:
                        st.error(f"Erreur lors du parsing des données d'entrée : {str(e)}")
                
                # ================================================================
                # SECTION 2 : DÉTAILS DE LA PRÉDICTION (OUTPUT)
                # ================================================================
                with st.expander("🎯 Détail de la Prédiction (Résultat)", expanded=True):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric(
                            "Score de Défaut",
                            f"{selected_log['score']:.4f}",
                            help="Probabilité que le client fasse défaut (0=Bon, 1=Mauvais)"
                        )
                    
                    with col2:
                        risk_level = "🔴 RISQUE ÉLEVÉ" if selected_log['score'] >= 0.6 else \
                                     "🟠 RISQUE MOYEN" if selected_log['score'] >= 0.45 else \
                                     "🟢 RISQUE FAIBLE"
                        st.metric(
                            "Niveau de Risque",
                            risk_level,
                            help="Catégorisation du risque"
                        )
                    
                    with col3:
                        decision = "❌ REFUSÉ" if selected_log['score'] >= 0.6 else "✅ ACCEPTÉ"
                        st.metric(
                            "Décision",
                            decision,
                            help="Recommandation de crédit"
                        )
                    
                    with col4:
                        st.metric(
                            "Latence",
                            f"{selected_log['latency_seconds']*1000:.1f} ms",
                            help="Temps de traitement"
                        )

                    infra_col1, infra_col2, infra_col3, infra_col4 = st.columns(4)
                    with infra_col1:
                        st.metric("CPU", f"{float(selected_log.get('cpu_usage_pct') or 0):.2f}%")
                    with infra_col2:
                        st.metric("GPU", f"{float(selected_log.get('gpu_usage_pct') or 0):.2f}%")
                    with infra_col3:
                        st.metric("Mémoire GPU", f"{float(selected_log.get('gpu_memory_mb') or 0):.2f} MB")
                    with infra_col4:
                        st.metric("Device", str(selected_log.get('compute_device') or 'cpu'))
                    
                    # Détails supplémentaires
                    st.write("**Informations Techniques :**")
                    col_a, col_b, col_c, col_d = st.columns(4)
                    
                    with col_a:
                        st.write(f"**Type de Prédiction :** {selected_log['prediction_type']}")
                    
                    with col_b:
                        st.write(f"**Timestamp :** {selected_log['timestamp']}")
                    
                    with col_c:
                        st.write(f"**Version Modèle :** {selected_log.get('model_version', 'N/A')}")
                    
                    with col_d:
                        st.write(f"**Compute Device :** {selected_log.get('compute_device', 'cpu')}")
                    
                    # Message d'erreur si applicable
                    if pd.notna(selected_log.get('error_message')):
                        st.error(f"**Erreur lors du traitement :** {selected_log['error_message']}")
                    
                    # Gauge chart pour le score
                    fig = go.Figure(data=[go.Indicator(
                        mode="gauge+number+delta",
                        value=selected_log['score'] * 100,
                        title={'text': "Score de Défaut (%)"},
                        delta={'reference': 50},
                        gauge={
                            'axis': {'range': [0, 100]},
                            'bar': {'color': "darkblue"},
                            'steps': [
                                {'range': [0, 45], 'color': "#90EE90"},
                                {'range': [45, 60], 'color': "#FFD700"},
                                {'range': [60, 100], 'color': "#FF6B6B"}
                            ],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': 60
                            }
                        }
                    )])
                    fig.update_layout(
                        paper_bgcolor="#1C2942",
                        font=dict(color="white", size=12),
                        margin=dict(l=10, r=10, t=50, b=10)
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            # Télécharger les données
            csv_data = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Télécharger CSV",
                data=csv_data,
                file_name="predictions_history.csv",
                mime="text/csv"
            )
        
        else:
            st.warning("Aucune donnée disponible.")
    
    except Exception as e:
        st.error(f"Erreur lors du chargement de l'historique : {str(e)}")

# ============================================================================
# PAGE 5 : À PROPOS
# ============================================================================
elif page == "À propos":
    st.markdown("""
    ## Dashboard de Monitoring
    
    ### Description
    Ce dashboard fournit une vue en temps réel du modèle de scoring credit XGBoost.
    
    ### Fonctionnalités
    - **KPIs** : Visualisation des statistiques principales
    - **Drift Detection** : Alerte automatique en cas de dérive des données
    - **Historique** : Accès à l'historique complet des prédictions
    - **Auto-refresh** : Mise à jour automatique toutes les 5 secondes
    
    ### Données sources
    - **Logs API** : `logs/api.log` (JSON, mis à jour en temps réel)
    - **Modèle** : XGBoost (optimal_threshold_xgb.json)
    
    ### Endpoints connexes
    - **API REST** : http://localhost:8005
    - **Interface Streamlit** : http://localhost:8505
    - **Dashboard Streamlit**: http://localhost:8505
    
    ### Auteur
    Gregory CRESPIN - Mars 2026
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #5FC2BA; font-size: 12px;'>
    Projet 08 - Credit Scoring - Production Dashboard | Mis à jour : {timestamp}
</div>
""".format(timestamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")), unsafe_allow_html=True)
