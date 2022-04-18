# TODO: black and isort, etc. (in pre-commit + action check?)
import json
import logging
from pathlib import Path

import pandas as pd

from .constants import CRYPTIC_FAMILIES, M1_INVERT_CLASSES, M2_GENERA_EXCLUSIONS
from .util import verify_empty_dir

_logger = logging.getLogger("rls.processor")


class _DataTypeCode:
    M1 = 0
    M2 = 1
    BOTH = 2


def _read_survey_data(survey_data_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Read the RLS survey data from the files in survey_data_dir (as downloaded by rls.download_survey_data)."""
    survey_file_paths = list(survey_data_dir.glob("*.csv"))
    if len(survey_file_paths) != 3:
        raise ValueError(f"Expected 3 survey data files, but found {len(survey_file_paths)}.")

    subset_dfs = []
    for data_file_path in survey_file_paths:
        subset_df = pd.read_csv(
            data_file_path,
            header=0,
            names=[
                "fid",
                "key",
                "survey_id",
                "country",
                "ecoregion",
                "realm",
                "site_code",
                "site",
                "site_lat",
                "site_long",
                "survey_date",
                "depth",
                "species_phylum",
                "species_class",
                "species_family",
                "species_taxon",
                "block",
                "total",
                "diver",
                "geom",
            ],
            usecols=[
                "survey_id",
                "country",
                "ecoregion",
                "realm",
                "site_code",
                "site",
                "survey_date",
                "depth",
                "species_phylum",
                "species_class",
                "species_family",
                "species_taxon",
                "block",
                "total",
                "geom",
                "survey_date",
                "diver",
            ],
        )
        _logger.info("Read %d rows from %s", len(subset_df), data_file_path)
        if data_file_path.name.startswith("m2_invert"):
            subset_df["data_type_code"] = _DataTypeCode.M2
        else:
            subset_df["data_type_code"] = _DataTypeCode.M1
        subset_dfs.append(subset_df)
    survey_data = pd.concat(subset_dfs, ignore_index=True)
    survey_data.dropna(subset=["species_taxon"], inplace=True)
    species_id_to_name = dict(enumerate(sorted(survey_data["species_taxon"].unique())))
    survey_data["species_id"] = survey_data["species_taxon"].map({v: k for k, v in species_id_to_name.items()})
    survey_data.loc[
        (
            survey_data["species_family"].isin(CRYPTIC_FAMILIES)
            & ~survey_data["species_taxon"].str.match("^" + "|".join(M2_GENERA_EXCLUSIONS))
        )
        | survey_data["species_class"].isin(M1_INVERT_CLASSES),
        "data_type_code",
    ] = _DataTypeCode.BOTH
    return survey_data, species_id_to_name


def _write_jsons(dst_dir, name_prefix, data, data_desc):
    """Write the same data twice: As a pretty-printed JSON and a minified JSON."""
    for suffix, json_kwargs in [(".json", dict(indent=2)), (".min.json", dict(separators=(",", ":")))]:
        out_path = dst_dir / f"{name_prefix}{suffix}"
        _logger.info("Writing %s to %s", data_desc, out_path)
        with open(out_path, "w") as fp:
            json.dump(data, fp, **json_kwargs)


def _create_site_summaries(survey_data: pd.DataFrame, dst_dir: Path):
    """
    Create the site summaries from survey_data and write them in API JSON format to dst_dir.

    Two files will be created, api-site-surveys.json and api-site-surveys.min.json, where the latter is the same JSON
    as the former but without pretty-printing whitespace. The content of the files is the same mapping from site code
    to [realm: str, ecoregion: str, site_name: str, lon: float, lat: float, num_surveys: int,
    species_id_to_num_surveys: dict[int, int]]
    """
    site_survey_counts = survey_data.groupby("site_code")["survey_id"].nunique()
    site_survey_counts.name = "num_surveys"
    site_infos = (
        survey_data[["site_code", "realm", "ecoregion", "site", "geom"]].drop_duplicates().set_index("site_code")
    )
    site_coords = site_infos["geom"].str.replace(r"(POINT )|\(|\)", "", regex=True).str.split(expand=True).astype(float)
    site_coords.columns = ["lon", "lat"]
    site_infos = site_infos.join([site_coords, site_survey_counts]).drop(columns="geom")
    site_survey_species_counts = (
        survey_data.drop_duplicates(["survey_id", "species_id"]).groupby(["site_code", "species_id"]).size()
    )
    site_summaries = {
        site_code: list(site_info.values()) + [site_survey_species_counts.loc[site_code].to_dict()]
        for site_code, site_info in site_infos.to_dict("index").items()
    }
    _write_jsons(dst_dir, name_prefix="api-site-surveys", data=site_summaries, data_desc=f"{len(site_summaries)} sites")


def _create_species_file(survey_data, species_id_to_name, crawl_data, dst_dir):
    """
    Create the species summary from the given data and write them in API JSON format to dst_dir.

    Two files will be created, api-species.json and api-species.min.json, where the latter is the same JSON as the
    former but without pretty-printing whitespace. The content of the files is the same mapping from the numeric species
    ID to [species_name: str, common_name: str, url: str, data_type_code: int (0 - M1, 1 - M2, 2 - both),
    image_urls: list[str]]
    """
    # Sort the data by species_id and data_type_code and drop duplicates, so that species that have more than one data
    # type would get assigned 2 - both.
    species_id_to_data_type_code = (
        survey_data[["species_id", "data_type_code"]]
        .sort_values(["species_id", "data_type_code"])
        .drop_duplicates(["species_id"], keep="last")
        .set_index("species_id")["data_type_code"]
        .to_dict()
    )
    api_species = {}
    for species_id, species_name in species_id_to_name.items():
        species_dict = crawl_data.get(species_name, {})
        api_species[species_id] = [
            species_name,
            species_dict.get("common_name", ""),
            species_dict.get("url", None),
            species_id_to_data_type_code[species_id],
            species_dict.get("image_urls", []),
        ]
    _write_jsons(dst_dir, name_prefix="api-species", data=api_species, data_desc=f"{len(api_species)} species")


# TODO: update expectations based on new server files
def create_api_jsons(
    crawl_json_path: Path,
    survey_data_dir: Path,
    dst_dir: Path,
    min_expected_crawl_items: int = 4_900,
    min_expected_survey_rows: int = 810_000,
):
    """Convert the crawl output to the API JSONs used by the RLS tools."""
    verify_empty_dir(dst_dir)
    _logger.info("Reading data.")
    with open(crawl_json_path) as fp:
        crawl_data = {species_dict["name"]: species_dict for species_dict in json.load(fp)}
    _logger.info("Read %d items from %s", len(crawl_data), crawl_json_path)
    if len(crawl_data) < min_expected_crawl_items:
        raise ValueError(f"Expected at least {min_expected_crawl_items} items, but found {len(crawl_data)}")
    survey_data, species_id_to_name = _read_survey_data(survey_data_dir)
    if len(survey_data) < min_expected_survey_rows:
        raise ValueError(f"Expected at least {min_expected_survey_rows} survey rows, but found {len(survey_data)}")
    _logger.info("Creating site summaries.")
    _create_site_summaries(survey_data, dst_dir)
    _logger.info("Creating species file.")
    _create_species_file(survey_data, species_id_to_name, crawl_data, dst_dir)
