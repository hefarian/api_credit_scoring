import pandas as pd

import src.monitoring_pg as monitoring_pg


def test_compute_prediction_stats_supports_naive_timestamps():
    logs_df = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp.now().replace(microsecond=0),
                "score": 0.42,
                "latency_seconds": 0.15,
                "cpu_usage_pct": 17.5,
                "gpu_usage_pct": 0.0,
                "gpu_memory_mb": 0.0,
                "error_message": None,
            }
        ]
    )

    stats = monitoring_pg.compute_prediction_stats(logs_df)

    assert stats["total"] == 1
    assert stats["today_count"] == 1
    assert stats["avg_score"] == 0.42
    assert stats["avg_cpu_usage_pct"] == 17.5
    assert stats["avg_gpu_usage_pct"] == 0.0


def test_compute_prediction_stats_supports_timezone_aware_utc_timestamps():
    logs_df = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp.now(tz="UTC"),
                "score": 0.35,
                "latency_seconds": 0.2,
                "cpu_usage_pct": 25.0,
                "gpu_usage_pct": 12.0,
                "gpu_memory_mb": 256.0,
                "error_message": None,
            }
        ]
    )

    stats = monitoring_pg.compute_prediction_stats(logs_df)

    assert stats["total"] == 1
    assert stats["today_count"] == 1
    assert stats["avg_score"] == 0.35
    assert stats["avg_gpu_usage_pct"] == 12.0
    assert stats["avg_gpu_memory_mb"] == 256.0


def test_detect_data_drift_returns_selected_raw_input_comparison(monkeypatch):
    now = pd.Timestamp.now().replace(microsecond=0)
    logs_df = pd.DataFrame(
        [
            {
                "timestamp": now,
                "input_data": {
                    "CODE_GENDER": "F",
                    "FLAG_OWN_CAR": "Y",
                    "FLAG_OWN_REALTY": "Y",
                    "AMT_CREDIT": 100000.0,
                    "AMT_INCOME_TOTAL": 50000.0,
                    "AMT_ANNUITY": 10000.0,
                    "AMT_GOODS_PRICE": 90000.0,
                    "DAYS_BIRTH": -12000,
                    "DAYS_EMPLOYED": -2000,
                    "CNT_FAM_MEMBERS": 2.0,
                    "NAME_EDUCATION_TYPE": "Higher education",
                    "NAME_FAMILY_STATUS": "Single / not married",
                    "NAME_HOUSING_TYPE": "House / apartment",
                    "OCCUPATION_TYPE": "Managers",
                    "EXT_SOURCE_1": 0.5,
                    "EXT_SOURCE_2": 0.6,
                    "EXT_SOURCE_3": 0.7,
                },
                "score": 0.41,
                "latency_seconds": 0.12,
                "error_message": None,
            },
            {
                "timestamp": now,
                "input_data": {
                    "CODE_GENDER": "F",
                    "FLAG_OWN_CAR": "N",
                    "FLAG_OWN_REALTY": "Y",
                    "AMT_CREDIT": 120000.0,
                    "AMT_INCOME_TOTAL": 52000.0,
                    "AMT_ANNUITY": 11000.0,
                    "AMT_GOODS_PRICE": 95000.0,
                    "DAYS_BIRTH": -12500,
                    "DAYS_EMPLOYED": -2200,
                    "CNT_FAM_MEMBERS": 3.0,
                    "NAME_EDUCATION_TYPE": "Higher education",
                    "NAME_FAMILY_STATUS": "Single / not married",
                    "NAME_HOUSING_TYPE": "House / apartment",
                    "OCCUPATION_TYPE": "Managers",
                    "EXT_SOURCE_1": 0.55,
                    "EXT_SOURCE_2": 0.62,
                    "EXT_SOURCE_3": 0.68,
                },
                "score": 0.43,
                "latency_seconds": 0.11,
                "error_message": None,
            },
        ]
    )

    monkeypatch.setattr(
        monitoring_pg,
        "get_reference_frame",
        lambda reference_kind="raw": pd.DataFrame(
            [
                {
                    "CODE_GENDER": "F",
                    "FLAG_OWN_CAR": "Y",
                    "FLAG_OWN_REALTY": "Y",
                    "AMT_CREDIT": 90000.0,
                    "AMT_INCOME_TOTAL": 48000.0,
                    "AMT_ANNUITY": 9500.0,
                    "AMT_GOODS_PRICE": 85000.0,
                    "DAYS_BIRTH": -11800,
                    "DAYS_EMPLOYED": -1800,
                    "CNT_FAM_MEMBERS": 2.0,
                    "NAME_EDUCATION_TYPE": "Higher education",
                    "NAME_FAMILY_STATUS": "Single / not married",
                    "NAME_HOUSING_TYPE": "House / apartment",
                    "OCCUPATION_TYPE": "Managers",
                    "EXT_SOURCE_1": 0.48,
                    "EXT_SOURCE_2": 0.59,
                    "EXT_SOURCE_3": 0.69,
                },
                {
                    "CODE_GENDER": "M",
                    "FLAG_OWN_CAR": "Y",
                    "FLAG_OWN_REALTY": "N",
                    "AMT_CREDIT": 92000.0,
                    "AMT_INCOME_TOTAL": 50000.0,
                    "AMT_ANNUITY": 9700.0,
                    "AMT_GOODS_PRICE": 87000.0,
                    "DAYS_BIRTH": -12100,
                    "DAYS_EMPLOYED": -1700,
                    "CNT_FAM_MEMBERS": 2.0,
                    "NAME_EDUCATION_TYPE": "Secondary / secondary special",
                    "NAME_FAMILY_STATUS": "Married",
                    "NAME_HOUSING_TYPE": "With parents",
                    "OCCUPATION_TYPE": "Sales staff",
                    "EXT_SOURCE_1": 0.5,
                    "EXT_SOURCE_2": 0.58,
                    "EXT_SOURCE_3": 0.7,
                },
            ]
        ),
    )
    monkeypatch.setattr(monitoring_pg, "record_drift_detection", lambda **kwargs: True)

    drift = monitoring_pg.detect_data_drift(logs_df, threshold=0.05)

    assert drift["comparison_used"] == "raw_input"
    assert set(drift["reference_comparisons"]) == {"raw_input"}
    assert drift["reference_comparisons"]["raw_input"]["num_features_analyzed"] >= 10

    variables = drift["reference_comparisons"]["raw_input"]["variables"]
    numeric_feature = next(item for item in variables if item["feature"] == "AMT_CREDIT")
    categorical_feature = next(item for item in variables if item["feature"] == "CODE_GENDER")

    assert numeric_feature["comparison_type"] == "Numérique"
    assert "moyenne =" in numeric_feature["reference_display"]
    assert numeric_feature["status_code"] == "medium"
    assert categorical_feature["comparison_type"] == "Catégorielle"
    assert "modalité dominante =" in categorical_feature["reference_display"]
    assert categorical_feature["status_code"] == "critical"
