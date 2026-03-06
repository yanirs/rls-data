import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from rls.processor import _create_species_file


@pytest.fixture()
def survey_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "species_name": ["Labroides dimidiatus", "Acanthurus nigrofuscus"],
            "data_type_code": [0, 1],
        }
    )


@pytest.fixture()
def species_json_data() -> list:
    return [
        {
            "scientific_name": "Labroides dimidiatus",
            "slug": "labroides-dimidiatus",
            "main_common_name": "Cleaner wrasse",
            "photos": [
                {
                    "medium_url": "https://images.reeflifesurvey.com/cleaner-wrasse.w400.jpg",
                }
            ],
        },
        {
            "scientific_name": "Acanthurus nigrofuscus",
            "slug": "acanthurus-nigrofuscus",
        },
    ]


def test_create_species_file_with_photos(
    survey_data: pd.DataFrame, species_json_data: list
) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        dst_dir = Path(tmp_dir)
        _create_species_file(survey_data, species_json_data, dst_dir)
        result = json.loads((dst_dir / "api-species.json").read_text())

    assert set(result.keys()) == {"Labroides dimidiatus", "Acanthurus nigrofuscus"}

    ld = result["Labroides dimidiatus"]
    assert ld[0] == "Labroides dimidiatus"
    assert ld[1] == "Cleaner wrasse"
    assert ld[2] == "https://reeflifesurvey.com/species/labroides-dimidiatus/"
    assert ld[3] == 0
    assert ld[4] == ["https://images.reeflifesurvey.com/cleaner-wrasse.w400.jpg"]

    an = result["Acanthurus nigrofuscus"]
    assert an[0] == "Acanthurus nigrofuscus"
    assert an[1] == ""
    assert an[2] == "https://reeflifesurvey.com/species/acanthurus-nigrofuscus/"
    assert an[3] == 1
    assert an[4] == []


def test_create_species_file_missing_species(survey_data: pd.DataFrame) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        dst_dir = Path(tmp_dir)
        _create_species_file(survey_data, [], dst_dir)
        result = json.loads((dst_dir / "api-species.json").read_text())

    for species_name in ("Labroides dimidiatus", "Acanthurus nigrofuscus"):
        entry = result[species_name]
        assert entry[0] == species_name
        assert entry[1] == ""
        assert entry[2] is None
        assert entry[4] == []
