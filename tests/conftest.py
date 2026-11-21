"""Keep source-file audits explicit when CI has only committed, distributable data."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data/raw"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.getenv("JU_RENT_CI_NO_RAW") != "1" and any(RAW_CSV.glob("*.csv")):
        return
    dependent = {
        "test_commute_budget.py": {"test_split_manifests_survive_rental_analysis"},
        "test_judge_guards.py": {"test_multifamily_names_match_raw_building_names"},
        "test_field_coverage.py": {"test_generated_coverage_accounts_for_all_public_rows"},
        "test_rtms_api.py": {
            "test_converter_matches_csv_columns_amounts_blank_contract_and_d011_area",
            "test_n040_verified_offline_gate_and_complex_attribution",
        },
    }
    fixture_dependent = {
        "test_contract_engine.py": {"prepared"},
        "test_evidence_hardening.py": {"counts", "dorm_output"},
        "test_rationale_evidence.py": {"counts"},
    }
    for item in items:
        module = Path(str(item.path)).name
        requires_raw = (
            module == "test_migrated_rentals.py"
            or (module == "test_data_expansion.py" and item.originalname != "test_period_flags")
            or item.originalname in dependent.get(module, set())
            or bool(set(item.fixturenames) & fixture_dependent.get(module, set()))
        )
        if requires_raw:
            item.add_marker(pytest.mark.skip(reason="원본 CSV 감사: CI에는 data/raw를 배포하지 않음"))
