"""Data processing functionality."""
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .constants import CORRUPTED_SITE_NAME_CORRECTIONS, CRYPTIC_FAMILIES, M1_INVERT_CLASSES, M2_GENERA_EXCLUSIONS
from .util import verify_empty_dir

_logger = logging.getLogger("rls.processor")


class _DataTypeCode:
    M1 = 0
    M2 = 1
    BOTH = 2


def _read_survey_data(survey_data_dir: Path) -> tuple[pd.DataFrame, dict[int, str]]:
    """Read the RLS survey data from the files in survey_data_dir (as downloaded by rls.download_survey_data)."""
    survey_file_paths = list(survey_data_dir.glob("*.csv"))
    if len(survey_file_paths) != 3:
        raise ValueError(f"Expected 3 survey data files, but found {len(survey_file_paths)}.")

    subset_dfs = []
    for data_file_path in survey_file_paths:
        subset_df = pd.read_csv(
            data_file_path,
            usecols=[
                "survey_id",
                "ecoregion",
                "realm",
                "site_code",
                "site_name",
                "class",
                "family",
                "species_name",
                "latitude",
                "longitude",
            ],
        )
        _logger.info("Read %d rows from %s", len(subset_df), data_file_path)
        if data_file_path.name.startswith("m2_invert"):
            subset_df["data_type_code"] = _DataTypeCode.M2
        else:
            subset_df["data_type_code"] = _DataTypeCode.M1
        subset_dfs.append(subset_df)
    survey_data = pd.concat(subset_dfs, ignore_index=True)
    survey_data.dropna(subset=["species_name"], inplace=True)
    survey_data.sort_values(["survey_id", "species_name"], inplace=True)
    species_id_to_name = dict(enumerate(survey_data["species_name"].unique()))
    survey_data["species_id"] = survey_data["species_name"].map({v: k for k, v in species_id_to_name.items()})
    survey_data.loc[
        (
            survey_data["family"].isin(CRYPTIC_FAMILIES)
            & ~survey_data["species_name"].str.match("^" + "|".join(M2_GENERA_EXCLUSIONS))
        )
        | survey_data["class"].isin(M1_INVERT_CLASSES),
        "data_type_code",
    ] = _DataTypeCode.BOTH
    survey_data["site_name"].replace(CORRUPTED_SITE_NAME_CORRECTIONS, inplace=True)
    return survey_data, species_id_to_name


def _write_jsons(dst_dir: Path, name_prefix: str, data: Any, data_desc: str) -> None:
    """Write the same data twice: As a pretty-printed JSON and a minified JSON."""
    suffix_to_json_kwargs: dict[str, dict[str, Any]] = {
        ".json": dict(indent=2),
        ".min.json": dict(separators=(",", ":")),
    }
    for suffix, json_kwargs in suffix_to_json_kwargs.items():
        out_path = dst_dir / f"{name_prefix}{suffix}"
        _logger.info("Writing %s to %s", data_desc, out_path)
        with open(out_path, "w") as fp:
            json.dump(data, fp, **json_kwargs)


def _create_site_summaries(survey_data: pd.DataFrame, dst_dir: Path) -> None:
    """
    Create the site summaries from survey_data and write them in API JSON format to dst_dir.

    Two files will be created, api-site-surveys.json and api-site-surveys.min.json, where the latter is the same JSON
    as the former but without pretty-printing whitespace. The content of the files is the same mapping from site code
    to [realm: str, ecoregion: str, site_name: str, longitude: float, latitude: float, num_surveys: int,
    species_id_to_num_surveys: dict[int, int]]
    """
    site_survey_counts = survey_data.groupby("site_code")["survey_id"].nunique()
    site_survey_counts.name = "num_surveys"
    site_infos = (
        survey_data[["site_code", "realm", "ecoregion", "site_name", "longitude", "latitude"]]
        .drop_duplicates()
        .set_index("site_code")
        .join(site_survey_counts)
    )
    site_survey_species_counts = (
        survey_data.drop_duplicates(["survey_id", "species_id"]).groupby(["site_code", "species_id"]).size()
    )
    site_summaries = {
        site_code: list(site_info.values()) + [site_survey_species_counts.loc[site_code].to_dict()]
        for site_code, site_info in sorted(site_infos.to_dict("index").items())
    }
    _write_jsons(dst_dir, name_prefix="api-site-surveys", data=site_summaries, data_desc=f"{len(site_summaries)} sites")


def _create_species_file(
    survey_data: pd.DataFrame,
    species_id_to_name: dict[int, str],
    crawl_data: dict[str, dict[str, Any]],
    img_src_path: Path,
    dst_dir: Path,
) -> None:
    """
    Create the species summary from the given data and write them in API JSON format to dst_dir.

    Two files will be created, api-species.json and api-species.min.json, where the latter is the same JSON as the
    former but without pretty-printing whitespace. The content of the files is the same mapping from the numeric species
    ID to [species_name: str, common_name: str, url: str, data_type_code: int (0 - M1, 1 - M2, 2 - both),
    image_urls: list[str]]

    If the crawled species dicts contain an "images" key, it is assumed that the images were scraped to img_src_path.
    In this case, the resulting image_urls will be of the form "/img/<species_slug>-<index>.<ext>". These paths will be
    symlinked from dst_dir / "img" to the files in img_src_path.
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
    dst_img_path = dst_dir / "img"
    verify_empty_dir(dst_img_path)
    api_species = {}
    for species_id, species_name in species_id_to_name.items():
        species_dict = crawl_data.get(species_name, {})

        if "images" in species_dict:
            image_urls: list[str] = []
            for image_dict in species_dict["images"]:
                dst_img_filename = f"img/{species_dict['id_']}-{len(image_urls)}.{image_dict['path'].split('.')[-1]}"
                (dst_dir / dst_img_filename).symlink_to(img_src_path / image_dict["path"])
                image_urls.append(f"/{dst_img_filename}")
        else:
            image_urls = species_dict.get("image_urls", [])

        api_species[species_id] = [
            species_name,
            species_dict.get("common_name", ""),
            species_dict.get("url", None),
            species_id_to_data_type_code[species_id],
            image_urls,
        ]
    _write_jsons(dst_dir, name_prefix="api-species", data=api_species, data_desc=f"{len(api_species)} species")


def create_api_jsons(
    crawl_json_path: Path,
    survey_data_dir: Path,
    dst_dir: Path,
    min_expected_crawl_items: int = 4_900,
    min_expected_survey_rows: int = 810_000,
) -> None:
    """Convert the crawl output to the API JSONs used by the RLS tools."""
    verify_empty_dir(dst_dir)
    (dst_dir / "img").mkdir()
    _logger.info("Reading data.")
    with open(crawl_json_path) as fp:
        crawl_data = {species_dict["name"]: species_dict for species_dict in json.load(fp)}
    _logger.info("Read %d items from %s", len(crawl_data), crawl_json_path)
    if len(crawl_data) < min_expected_crawl_items:
        raise ValueError(f"Expected at least {min_expected_crawl_items} items, but found {len(crawl_data)}")
    img_src_path = (crawl_json_path.parent / "img").resolve()
    survey_data, species_id_to_name = _read_survey_data(survey_data_dir)
    if len(survey_data) < min_expected_survey_rows:
        raise ValueError(f"Expected at least {min_expected_survey_rows} survey rows, but found {len(survey_data)}")
    _logger.info("Creating site summaries.")
    _create_site_summaries(survey_data, dst_dir)
    _logger.info("Creating species file.")
    _create_species_file(survey_data, species_id_to_name, crawl_data, img_src_path, dst_dir)
