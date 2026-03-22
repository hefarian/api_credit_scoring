# 📋 Exemples de Test - API `/predict`

Ce document fournit **10 exemples de requêtes JSON** pour tester l'endpoint `/predict` de l'API de scoring.


## 📊 10 Exemples de Test

### Exemple 1 : Client à Bas Risque (Revenu Élevé, Faible Crédit)

**Description** : Client avec revenu très élevé (300 000€) et crédit modéré (250 000€).

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100002,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "M",
    "FLAG_OWN_CAR": "Y",
    "FLAG_OWN_REALTY": "Y",
    "CNT_CHILDREN": 0,
    "AMT_INCOME_TOTAL": 300000,
    "AMT_CREDIT": 250000,
    "AMT_ANNUITY": 15000,
    "AMT_GOODS_PRICE": 250000,
    "NAME_EDUCATION_TYPE": "Higher education",
    "NAME_FAMILY_STATUS": "Married",
    "NAME_HOUSING_TYPE": "House / apartment",
    "DAYS_BIRTH": -10000,
    "DAYS_EMPLOYED": -3000,
    "OCCUPATION_TYPE": "Managers",
    "CNT_FAM_MEMBERS": 3,
    "EXT_SOURCE_1": 0.8,
    "EXT_SOURCE_2": 0.75,
    "EXT_SOURCE_3": 0.7
  }
}
```

**Résultat attendu** : 
- **Probabilité de défaut** : **~0.15-0.25** (bas risque)
- **Explication** : Revenu très élevé, stabilité professionnelle (3000 jours d'emploi), propriétaire, scores externes élevés → client fiable

---

### Exemple 2 : Client à Risque Modéré (Revenu Moyen, Crédit Important)

**Description** : Client avec revenu moyen (60 000€) et crédit important (350 000€). Ratio crédit/revenu élevé.

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100003,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "F",
    "FLAG_OWN_CAR": "N",
    "FLAG_OWN_REALTY": "Y",
    "CNT_CHILDREN": 1,
    "AMT_INCOME_TOTAL": 60000,
    "AMT_CREDIT": 350000,
    "AMT_ANNUITY": 18000,
    "AMT_GOODS_PRICE": 350000,
    "NAME_EDUCATION_TYPE": "Secondary / secondary special",
    "NAME_FAMILY_STATUS": "Single / not married",
    "NAME_HOUSING_TYPE": "House / apartment",
    "DAYS_BIRTH": -15000,
    "DAYS_EMPLOYED": -500,
    "OCCUPATION_TYPE": "Sales staff",
    "CNT_FAM_MEMBERS": 2,
    "EXT_SOURCE_1": 0.55,
    "EXT_SOURCE_2": 0.50,
    "EXT_SOURCE_3": 0.45
  }
}
```

**Résultat attendu** :
- **Probabilité de défaut** : **~0.45-0.55** (risque modéré)
- **Explication** : Ratio crédit/revenu = 5.83 (élevé), ancienneté faible (500 jours), scores externes modérés, situation personnelle instable (célibataire)

---

### Exemple 3 : Client à Haut Risque (Bas Revenu, Très Endetté)

**Description** : Client avec revenu faible (35 000€) et crédit très élevé (300 000€). Ratios d'endettement alarmants.

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100004,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "M",
    "FLAG_OWN_CAR": "N",
    "FLAG_OWN_REALTY": "N",
    "CNT_CHILDREN": 3,
    "AMT_INCOME_TOTAL": 35000,
    "AMT_CREDIT": 300000,
    "AMT_ANNUITY": 20000,
    "AMT_GOODS_PRICE": 300000,
    "NAME_EDUCATION_TYPE": "Lower secondary",
    "NAME_FAMILY_STATUS": "Married",
    "NAME_HOUSING_TYPE": "Rented apartment",
    "DAYS_BIRTH": -20000,
    "DAYS_EMPLOYED": -100,
    "OCCUPATION_TYPE": "Laborers",
    "CNT_FAM_MEMBERS": 5,
    "EXT_SOURCE_1": 0.35,
    "EXT_SOURCE_2": 0.30,
    "EXT_SOURCE_3": 0.25
  }
}
```

**Résultat attendu** :
- **Probabilité de défaut** : **~0.70-0.85** (haut risque)
- **Explication** : Ratio crédit/revenu = 8.57 (critique), pas de propriété, nombreux enfants, emploi très instable (100 jours), scores externes faibles

---

### Exemple 4 : Jeune Client avec Première Opportunité

**Description** : Jeune client (28 ans) avec premier emploi (6 mois), revenu modeste mais stable, petit crédit.

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100005,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "M",
    "FLAG_OWN_CAR": "Y",
    "FLAG_OWN_REALTY": "N",
    "CNT_CHILDREN": 0,
    "AMT_INCOME_TOTAL": 45000,
    "AMT_CREDIT": 80000,
    "AMT_ANNUITY": 4800,
    "AMT_GOODS_PRICE": 80000,
    "NAME_EDUCATION_TYPE": "Higher education",
    "NAME_FAMILY_STATUS": "Single / not married",
    "NAME_HOUSING_TYPE": "Rented apartment",
    "DAYS_BIRTH": -10000,
    "DAYS_EMPLOYED": -180,
    "OCCUPATION_TYPE": "IT staff",
    "CNT_FAM_MEMBERS": 1,
    "EXT_SOURCE_1": 0.60,
    "EXT_SOURCE_2": 0.58,
    "EXT_SOURCE_3": 0.55
  }
}
```

**Résultat attendu** :
- **Probabilité de défaut** : **~0.30-0.40** (risque modéré-bas)
- **Explication** : Jeune avec diplôme supérieur, crédit raisonnable (ratio 1.78), emploi stable malgré ancienneté faible, scores externes acceptables

---

### Exemple 5 : Client Expérimenté, Bien Établi

**Description** : Client mature (45 ans) avec emploi très stable (15 ans), propriétaire, revenu confortable (120 000€).

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100006,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "M",
    "FLAG_OWN_CAR": "Y",
    "FLAG_OWN_REALTY": "Y",
    "CNT_CHILDREN": 2,
    "AMT_INCOME_TOTAL": 120000,
    "AMT_CREDIT": 150000,
    "AMT_ANNUITY": 8500,
    "AMT_GOODS_PRICE": 150000,
    "NAME_EDUCATION_TYPE": "Higher education",
    "NAME_FAMILY_STATUS": "Married",
    "NAME_HOUSING_TYPE": "House / apartment",
    "DAYS_BIRTH": -16500,
    "DAYS_EMPLOYED": -5475,
    "OCCUPATION_TYPE": "Managers",
    "CNT_FAM_MEMBERS": 4,
    "EXT_SOURCE_1": 0.85,
    "EXT_SOURCE_2": 0.82,
    "EXT_SOURCE_3": 0.80
  }
}
```

**Résultat attendu** :
- **Probabilité de défaut** : **~0.10-0.20** (bas risque)
- **Explication** : Client très établi (15 ans d'ancienneté), propriétaire marié, ratio crédit/revenu faible (1.25), scores externes élevés

---

### Exemple 6 : Client avec Antécédents Problématiques

**Description** : Client avec beaucoup d'enfants (4), sans emploi stable (100 jours), scores externes très faibles.

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100007,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "F",
    "FLAG_OWN_CAR": "N",
    "FLAG_OWN_REALTY": "N",
    "CNT_CHILDREN": 4,
    "AMT_INCOME_TOTAL": 40000,
    "AMT_CREDIT": 200000,
    "AMT_ANNUITY": 15000,
    "AMT_GOODS_PRICE": 200000,
    "NAME_EDUCATION_TYPE": "Secondary / secondary special",
    "NAME_FAMILY_STATUS": "Divorced",
    "NAME_HOUSING_TYPE": "Rented apartment",
    "DAYS_BIRTH": -18000,
    "DAYS_EMPLOYED": -100,
    "OCCUPATION_TYPE": "Cleaning staff",
    "CNT_FAM_MEMBERS": 5,
    "EXT_SOURCE_1": 0.20,
    "EXT_SOURCE_2": 0.15,
    "EXT_SOURCE_3": 0.10
  }
}
```

**Résultat attendu** :
- **Probabilité de défaut** : **~0.75-0.90** (très haut risque)
- **Explication** : Ratio crédit/revenu = 5.0, situation personnelle fragile (divorcée, 4 enfants), employabilité faible, scores externes critiques

---

### Exemple 7 : Client Travailleur Indépendant

**Description** : Client travailleur indépendant depuis 3 ans, revenu variable (70 000€), sans propriété.

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100008,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "M",
    "FLAG_OWN_CAR": "Y",
    "FLAG_OWN_REALTY": "N",
    "CNT_CHILDREN": 1,
    "AMT_INCOME_TOTAL": 70000,
    "AMT_CREDIT": 140000,
    "AMT_ANNUITY": 10000,
    "AMT_GOODS_PRICE": 140000,
    "NAME_EDUCATION_TYPE": "Higher education",
    "NAME_FAMILY_STATUS": "Married",
    "NAME_HOUSING_TYPE": "Rented apartment",
    "DAYS_BIRTH": -13000,
    "DAYS_EMPLOYED": -1095,
    "OCCUPATION_TYPE": "Business owner",
    "CNT_FAM_MEMBERS": 3,
    "EXT_SOURCE_1": 0.50,
    "EXT_SOURCE_2": 0.48,
    "EXT_SOURCE_3": 0.45
  }
}
```

**Résultat attendu** :
- **Probabilité de défaut** : **~0.50-0.60** (risque modéré)
- **Explication** : Ratio crédit/revenu = 2.0 (acceptable), mais revenu indépendant moins stable, pas de propriété, ancienneté modérée (3 ans)

---

### Exemple 8 : Client Retraité

**Description** : Client retraité (65 ans), pension modeste (30 000€), petit crédit (50 000€), propriétaire.

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100009,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "F",
    "FLAG_OWN_CAR": "N",
    "FLAG_OWN_REALTY": "Y",
    "CNT_CHILDREN": 0,
    "AMT_INCOME_TOTAL": 30000,
    "AMT_CREDIT": 50000,
    "AMT_ANNUITY": 3500,
    "AMT_GOODS_PRICE": 50000,
    "NAME_EDUCATION_TYPE": "Secondary / secondary special",
    "NAME_FAMILY_STATUS": "Widowed",
    "NAME_HOUSING_TYPE": "House / apartment",
    "DAYS_BIRTH": -23725,
    "DAYS_EMPLOYED": 365000,
    "OCCUPATION_TYPE": "Pensioner",
    "CNT_FAM_MEMBERS": 1,
    "EXT_SOURCE_1": 0.65,
    "EXT_SOURCE_2": 0.62,
    "EXT_SOURCE_3": 0.60
  }
}
```

**Résultat attendu** :
- **Probabilité de défaut** : **~0.35-0.45** (risque modéré)
- **Explication** : Client retraité (stabilité relative), propriétaire, mais revenu faible et fixe, ratio crédit/revenu = 1.67, scores externes corrects

---

### Exemple 9 : Femme Entrepreneur en Croissance

**Description** : Femme entrepreneur (40 ans) depuis 2 ans, revenus en croissance (90 000€), propriétaire.

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100010,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "F",
    "FLAG_OWN_CAR": "Y",
    "FLAG_OWN_REALTY": "Y",
    "CNT_CHILDREN": 1,
    "AMT_INCOME_TOTAL": 90000,
    "AMT_CREDIT": 120000,
    "AMT_ANNUITY": 7500,
    "AMT_GOODS_PRICE": 120000,
    "NAME_EDUCATION_TYPE": "Higher education",
    "NAME_FAMILY_STATUS": "Married",
    "NAME_HOUSING_TYPE": "House / apartment",
    "DAYS_BIRTH": -14600,
    "DAYS_EMPLOYED": -730,
    "OCCUPATION_TYPE": "Business owner",
    "CNT_FAM_MEMBERS": 3,
    "EXT_SOURCE_1": 0.70,
    "EXT_SOURCE_2": 0.68,
    "EXT_SOURCE_3": 0.65
  }
}
```

**Résultat attendu** :
- **Probabilité de défaut** : **~0.25-0.35** (bas-modéré risque)
- **Explication** : Entrepreneur avec diplôme supérieur, propriétaire marié, ratio crédit/revenu = 1.33 (bon), scores externes élevés, ancienneté entrepreneuriale 2 ans

---

### Exemple 10 : Client Borderline (Cas Limite)

**Description** : Client "moyen" : revenu moyen, crédit moyen, situation stable mais sans points positifs distincts.

**Entrée JSON** :
```json
{
  "data": {
    "SK_ID_CURR": 100011,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "M",
    "FLAG_OWN_CAR": "Y",
    "FLAG_OWN_REALTY": "Y",
    "CNT_CHILDREN": 1,
    "AMT_INCOME_TOTAL": 75000,
    "AMT_CREDIT": 180000,
    "AMT_ANNUITY": 11000,
    "AMT_GOODS_PRICE": 180000,
    "NAME_EDUCATION_TYPE": "Secondary / secondary special",
    "NAME_FAMILY_STATUS": "Married",
    "NAME_HOUSING_TYPE": "House / apartment",
    "DAYS_BIRTH": -14000,
    "DAYS_EMPLOYED": -1800,
    "OCCUPATION_TYPE": "Technicians",
    "CNT_FAM_MEMBERS": 3,
    "EXT_SOURCE_1": 0.50,
    "EXT_SOURCE_2": 0.50,
    "EXT_SOURCE_3": 0.50
  }
}
```

**Résultat attendu** :
- **Probabilité de défaut** : **~0.48-0.55** (risque modéré)
- **Explication** : Profil équilibré, ratio crédit/revenu = 2.4 (acceptable), propriétaire, situation stable mais scores externes moyens → borderline

---

## 📈 Interprétation des Scores

| Probabilité | Interprétation | Action |
|-------------|----------------|--------|
| **0.0 - 0.25** | ✅ **Très bon client** | Approuver sans hésitation |
| **0.25 - 0.45** | ✅ **Bon client** | Approuver avec conditions normales |
| **0.45 - 0.60** | ⚠️ **Risque modéré** | Approuver avec garanties ou taux majoré |
| **0.60 - 0.80** | ❌ **Risque élevé** | Refuser ou demander co-signataire |
| **0.80 - 1.00** | ❌ **Très haut risque** | Refuser fortement |

---

## 🔍 Colonnes Principales Attendues

Le modèle accepte les colonnes suivantes (voir `src/preprocessing.py` pour la liste complète) :

### Identifiants
- `SK_ID_CURR` : Identifiant unique du client

### Données Démographiques
- `CODE_GENDER` : "M" ou "F"
- `DAYS_BIRTH` : Jours depuis la naissance (négatif)
- `CNT_CHILDREN` : Nombre d'enfants
- `CNT_FAM_MEMBERS` : Nombre de membres de la famille

### Données Professionnelles
- `NAME_OCCUPATION_TYPE` : Type d'occupation
- `DAYS_EMPLOYED` : Jours depuis l'emploi (négatif)

### Données Financières
- `AMT_INCOME_TOTAL` : Revenu total annuel
- `AMT_CREDIT` : Montant du crédit demandé
- `AMT_ANNUITY` : Annuité (paiement annuel)
- `AMT_GOODS_PRICE` : Prix des biens achetés

### Données Immobilières
- `FLAG_OWN_REALTY` : Propriétaire immobilier ("Y"/"N")
- `FLAG_OWN_CAR` : Propriétaire de véhicule ("Y"/"N")

### Données Externes
- `EXT_SOURCE_1`, `EXT_SOURCE_2`, `EXT_SOURCE_3` : Scores de crédit externes (0.0-1.0)

### Données Catégorielles
- `NAME_CONTRACT_TYPE` : Type de contrat
- `NAME_EDUCATION_TYPE` : Niveau d'éducation
- `NAME_FAMILY_STATUS` : Situation familiale
- `NAME_HOUSING_TYPE` : Type de logement

---

## 🎯 Points Clés pour les Tests

1. **Validation des ratios** : Le modèle calcule automatiquement des ratios (crédit/revenu, etc.)
2. **Feature engineering** : Interactions et polynômes sont créés automatiquement
3. **Normalisation** : Les valeurs numériques sont standardisées
4. **Encodage** : Les variables catégorielles sont encodées (si encoder.pkl existe)
5. **Gestion des NaN** : Les valeurs manquantes sont imputées (médiane par défaut)

---

## 📝 Notes Importantes

- ⚠️ Les `DAYS_*` doivent être **négatifs** (convention: jours depuis l'événement)
- ⚠️ Les scores externes `EXT_SOURCE_*` doivent être entre **0.0 et 1.0**
- ⚠️ Les flags `FLAG_OWN_*` acceptent **"Y"** ou **"N"** (ou 1/0)
- ⚠️ Les colonnes catégorielles acceptent les **valeurs texte** (encoder.pkl les transformera)
- ✅ Les colonnes numériques manquantes seront **imputées à la médiane**

---

## 🚨 Format de Réponse Attendu

```json
{
  "score": 0.42,
  "model_version": "1.0"
}
```

- `score` : Probabilité de défaut (0.0-1.0)
- `model_version` : Version du modèle utilisé
