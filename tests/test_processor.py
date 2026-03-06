import json
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from rls.processor import _create_species_file


@pytest.fixture
def survey_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "species_name": ["Labroides dimidiatus", "Acanthurus nigrofuscus"],
            "data_type_code": [0, 1],
        }
    )


@pytest.fixture
def species_json_data() -> list[dict[str, Any]]:
    return [
        {
            "scientific_name": "Labroides dimidiatus",
            "slug": "labroides-dimidiatus",
            "main_common_name": "Cleaner wrasse",
            "photos": [
                {
                    "large_url": "https://images.reeflifesurvey.com/cleaner-wrasse.w1000.jpg",
                }
            ],
        },
        {
            "scientific_name": "Acanthurus nigrofuscus",
            "slug": "acanthurus-nigrofuscus",
        },
    ]


def test_create_species_file_with_photos(
    survey_data: pd.DataFrame, species_json_data: list[dict[str, Any]]
) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        dst_dir = Path(tmp_dir)
        _create_species_file(survey_data, species_json_data, dst_dir)
        result = json.loads((dst_dir / "api-species.json").read_text())

    assert set(result.keys()) == {"Labroides dimidiatus", "Acanthurus nigrofuscus"}
    assert result["Labroides dimidiatus"] == [
        "Labroides dimidiatus",
        "Cleaner wrasse",
        "https://reeflifesurvey.com/species/labroides-dimidiatus/",
        0,
        ["https://images.reeflifesurvey.com/cleaner-wrasse.w1000.jpg"],
    ]
    assert result["Acanthurus nigrofuscus"] == [
        "Acanthurus nigrofuscus",
        "",
        "https://reeflifesurvey.com/species/acanthurus-nigrofuscus/",
        1,
        [],
    ]


def test_create_species_file_missing_species(survey_data: pd.DataFrame) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        dst_dir = Path(tmp_dir)
        _create_species_file(survey_data, [], dst_dir)
        result = json.loads((dst_dir / "api-species.json").read_text())

    assert result["Labroides dimidiatus"] == ["Labroides dimidiatus", "", None, 0, []]
    assert result["Acanthurus nigrofuscus"] == [
        "Acanthurus nigrofuscus",
        "",
        None,
        1,
        [],
    ]
