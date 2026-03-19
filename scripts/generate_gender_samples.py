#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
TRAIN_PATH = ROOT / "data" / "application_train.csv"
OUTPUT_MEN_PATH = ROOT / "samples" / "data_sample_men.json"
OUTPUT_WOMEN_PATH = ROOT / "samples" / "data_sample_women.json"

REQUIRED_COLS = [
    "SK_ID_CURR",
    "NAME_CONTRACT_TYPE",
    "CODE_GENDER",
    "FLAG_OWN_CAR",
    "FLAG_OWN_REALTY",
    "CNT_CHILDREN",
    "AMT_INCOME_TOTAL",
    "AMT_CREDIT",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "NAME_EDUCATION_TYPE",
    "NAME_FAMILY_STATUS",
    "NAME_HOUSING_TYPE",
    "DAYS_BIRTH",
    "DAYS_EMPLOYED",
    "OCCUPATION_TYPE",
    "CNT_FAM_MEMBERS",
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
]

NUMERIC_MATCH_COLS = [
    "CNT_CHILDREN",
    "AMT_INCOME_TOTAL",
    "AMT_CREDIT",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "DAYS_BIRTH",
    "DAYS_EMPLOYED",
    "CNT_FAM_MEMBERS",
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
]

CATEGORICAL_MATCH_COLS = [
    "NAME_CONTRACT_TYPE",
    "FLAG_OWN_CAR",
    "FLAG_OWN_REALTY",
    "NAME_EDUCATION_TYPE",
    "NAME_FAMILY_STATUS",
    "NAME_HOUSING_TYPE",
    "OCCUPATION_TYPE",
]

DEFAULT_FILL_VALUES = {
    "OCCUPATION_TYPE": "Unknown",
    "EXT_SOURCE_1": 0.5,
    "EXT_SOURCE_2": 0.5,
    "EXT_SOURCE_3": 0.5,
    "AMT_ANNUITY": 0.0,
    "AMT_GOODS_PRICE": 0.0,
}

SAMPLE_SIZE = 50
RANDOM_STATE = 42


def load_training_data() -> pd.DataFrame:
    df = pd.read_csv(TRAIN_PATH, usecols=REQUIRED_COLS)
    df = df[df["CODE_GENDER"].isin(["M", "F"])].copy()
    df = df.fillna(DEFAULT_FILL_VALUES)
    return df.reset_index(drop=True)


def compute_distance_matrix(women_df: pd.DataFrame, men_df: pd.DataFrame) -> np.ndarray:
    women_numeric = women_df[NUMERIC_MATCH_COLS].astype(float)
    men_numeric = men_df[NUMERIC_MATCH_COLS].astype(float)

    combined = pd.concat([women_numeric, men_numeric], axis=0)
    std = combined.std().replace(0, 1.0)

    women_scaled = women_numeric / std
    men_scaled = men_numeric / std

    women_values = women_scaled.to_numpy()
    men_values = men_scaled.to_numpy()

    numeric_distance = ((women_values[:, None, :] - men_values[None, :, :]) ** 2).sum(axis=2)

    women_cat = women_df[CATEGORICAL_MATCH_COLS].astype(str).to_numpy()
    men_cat = men_df[CATEGORICAL_MATCH_COLS].astype(str).to_numpy()
    categorical_mismatch = (women_cat[:, None, :] != men_cat[None, :, :]).sum(axis=2)

    return numeric_distance + (categorical_mismatch * 25.0)


def greedy_match(women_df: pd.DataFrame, men_df: pd.DataFrame, sample_size: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RANDOM_STATE)

    women_pool = women_df.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)
    men_pool = men_df.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)

    women_candidates = women_pool.head(min(len(women_pool), sample_size * 4)).copy().reset_index(drop=True)
    men_candidates = men_pool.copy().reset_index(drop=True)

    distance_matrix = compute_distance_matrix(women_candidates, men_candidates)
    used_men: set[int] = set()
    matched_pairs: list[tuple[int, int, float]] = []

    for woman_idx in rng.permutation(len(women_candidates)):
        available_men = [idx for idx in range(len(men_candidates)) if idx not in used_men]
        if not available_men or len(matched_pairs) >= sample_size:
            break

        candidate_scores = distance_matrix[woman_idx, available_men]
        best_position = int(np.argmin(candidate_scores))
        best_men_idx = available_men[best_position]
        used_men.add(best_men_idx)
        matched_pairs.append((woman_idx, best_men_idx, float(candidate_scores[best_position])))

    if len(matched_pairs) < sample_size:
        raise ValueError(f"Impossible de constituer {sample_size} paires homme/femme")

    matched_pairs.sort(key=lambda item: item[2])
    selected_pairs = matched_pairs[:sample_size]

    selected_women = women_candidates.iloc[[item[0] for item in selected_pairs]].copy().reset_index(drop=True)
    selected_men = men_candidates.iloc[[item[1] for item in selected_pairs]].copy().reset_index(drop=True)
    return selected_women, selected_men


def write_sample_json(df: pd.DataFrame, output_path: Path) -> None:
    payload = {"data": df[REQUIRED_COLS].to_dict(orient="records")}
    with output_path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2, ensure_ascii=False)


def summarize_difference(women_df: pd.DataFrame, men_df: pd.DataFrame) -> str:
    rows = []
    for column in NUMERIC_MATCH_COLS:
        women_mean = float(women_df[column].astype(float).mean())
        men_mean = float(men_df[column].astype(float).mean())
        if abs(women_mean) > 1e-9:
            gap_pct = abs(men_mean - women_mean) / abs(women_mean) * 100
        else:
            gap_pct = abs(men_mean - women_mean) * 100
        rows.append(f"- {column}: women={women_mean:.4f} | men={men_mean:.4f} | gap={gap_pct:.2f}%")

    same_contract = (women_df["NAME_CONTRACT_TYPE"].value_counts(normalize=True) - men_df["NAME_CONTRACT_TYPE"].value_counts(normalize=True)).fillna(0).abs().sum()
    rows.append(f"- ecart distribution NAME_CONTRACT_TYPE: {same_contract:.4f}")
    return "\n".join(rows)


def main() -> None:
    train_df = load_training_data()
    women_df = train_df[train_df["CODE_GENDER"] == "F"].copy()
    men_df = train_df[train_df["CODE_GENDER"] == "M"].copy()

    selected_women, selected_men = greedy_match(women_df, men_df, SAMPLE_SIZE)

    write_sample_json(selected_women, OUTPUT_WOMEN_PATH)
    write_sample_json(selected_men, OUTPUT_MEN_PATH)

    print(f"Fichier généré: {OUTPUT_WOMEN_PATH}")
    print(f"Fichier généré: {OUTPUT_MEN_PATH}")
    print(f"Taille women: {len(selected_women)} | Taille men: {len(selected_men)}")
    print("Résumé des écarts résiduels hors genre:")
    print(summarize_difference(selected_women, selected_men))


if __name__ == "__main__":
    main()