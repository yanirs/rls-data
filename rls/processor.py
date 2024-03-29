"""Data processing functionality."""
import json
import logging
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import cartopy
import pandas as pd
from matplotlib import pyplot as plt

from .constants import (
    CRYPTIC_FAMILIES,
    M1_CLASSES,
    M1_INVERT_CLASSES,
    M2_GENERA_EXCLUSIONS,
)
from .util import load_json, verify_empty_dir

_logger = logging.getLogger("rls.processor")


class _DataTypeCode:
    M1 = 0
    M2 = 1
    BOTH = 2


def _read_survey_data(
    survey_data_dir: Path, num_expected_survey_files: int = 4
) -> pd.DataFrame:
    """
    Read survey data from the files in survey_data_dir.

    This assumes the files were downloaded by rls.download_survey_data.
    """
    survey_file_paths = list(survey_data_dir.glob("*.csv"))
    if len(survey_file_paths) != num_expected_survey_files:
        raise ValueError(
            f"Expected {num_expected_survey_files} survey data files, "
            f"but found {len(survey_file_paths)}."
        )

    subset_dfs = []
    for data_file_path in survey_file_paths:
        subset_df = pd.read_csv(
            data_file_path,
            usecols=[
                "survey_id",
                "country",
                "ecoregion",
                "realm",
                "location",
                "site_code",
                "site_name",
                "program",
                "class",
                "family",
                "species_name",
                "latitude",
                "longitude",
                "total",
            ],
        )
        _logger.info("Read %d rows from %s", len(subset_df), data_file_path)
        subset_dfs.append(subset_df)
    survey_data = pd.concat(subset_dfs, ignore_index=True)
    survey_data.dropna(subset=["species_name"], inplace=True)
    survey_data.sort_values(["survey_id", "species_name"], inplace=True)
    survey_data["data_type_code"] = None
    survey_data.loc[
        survey_data["class"].isin(M1_CLASSES), "data_type_code"
    ] = _DataTypeCode.M1
    survey_data.loc[
        (
            survey_data["family"].isin(CRYPTIC_FAMILIES)
            & ~survey_data["species_name"].str.match(
                "^" + "|".join(M2_GENERA_EXCLUSIONS)
            )
        )
        | survey_data["class"].isin(M1_INVERT_CLASSES),
        "data_type_code",
    ] = _DataTypeCode.BOTH
    survey_data.loc[
        survey_data["data_type_code"].isna(), "data_type_code"
    ] = _DataTypeCode.M2
    return survey_data


def _write_json(out_path: Path, data: Any, data_desc: str) -> None:
    _logger.info("Writing %s to %s", data_desc, out_path)
    with out_path.open("w") as fp:
        json.dump(data, fp, indent=2)


def _create_site_summaries(survey_data: pd.DataFrame, dst_dir: Path) -> None:
    """
    Create site summaries from survey_data and write them in API JSON format to dst_dir.

    One legacy files is created, api-site-surveys.json, mapping from site code to an
    array with elements:
     - realm: str
     - ecoregion: str
     - site_name: str
     - longitude: float
     - latitude: float
     - num_surveys: int
     - species_name_to_num_surveys: dict[str, int]]

    In addition, two new format files are created:
      - sites.json: site data with keys 'rows' - array of arrays, and 'keys' -
        specifying the meaning of each array value in 'rows'
      - surveys.json: mapping from species_name (str) to site_code (str) to count (int),
        which is the number of observations of the species at the site
    """
    site_survey_counts = survey_data.groupby("site_code")["survey_id"].nunique()
    site_survey_counts.name = "num_surveys"
    site_infos = (
        survey_data[
            [
                "site_code",
                "country",
                "realm",
                "location",
                "ecoregion",
                "site_name",
                "longitude",
                "latitude",
            ]
        ]
        .drop_duplicates()
        .set_index("site_code")
        .join(site_survey_counts)
    )
    site_survey_species_counts = (
        survey_data.drop_duplicates(["survey_id", "species_name"])
        .groupby(["site_code", "species_name"])
        .size()
    )
    site_summaries = {
        site_code: [
            *list(site_info.values()),
            site_survey_species_counts.loc[site_code].to_dict(),
        ]
        for site_code, site_info in sorted(
            site_infos.drop(columns=["country", "location"]).to_dict("index").items()
        )
    }
    _write_json(
        dst_dir / "api-site-surveys.json",
        data=site_summaries,
        data_desc=f"{len(site_summaries)} legacy sites",
    )

    new_site_summaries = dict(
        keys=["site_code", *site_infos.columns.tolist()],
        rows=list(map(list, site_infos.sort_index().itertuples())),
    )
    _write_json(
        dst_dir / "sites.json",
        data=new_site_summaries,
        data_desc=f"{len(site_infos)} new sites",
    )
    new_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for (species_name, site_code), count in (
        site_survey_species_counts.reorder_levels([1, 0]).sort_index().items()
    ):
        new_counts[species_name][site_code] = count
    _write_json(
        dst_dir / "surveys.json",
        data=new_counts,
        data_desc=f"counts for {len(new_counts)} species",
    )


def _create_species_file(
    survey_data: pd.DataFrame,
    crawl_data: dict[str, dict[str, Any]],
    img_src_path: Path,
    dst_dir: Path,
) -> None:
    """
    Create species summary from the data and write it in API JSON format to dst_dir.

    The created api-species.json file is a mapping from the species_name to an array
    with elements:
     - species_name: str
     - common_name: str
     - url: str
     - data_type_code: int (0 - M1, 1 - M2, 2 - both)
     - image_urls: list[str]

    If the crawled species dicts contain an "images" key, it is assumed that the images
    were scraped to img_src_path.In this case, the resulting image_urls will be of the
    form "/img/<species_slug>-<index>.<ext>". These paths will be symlinked from
    dst_dir / "img" to the files in img_src_path.
    """
    # Sort the data by species_name and data_type_code and drop duplicates, so that
    # species that have more than one data type would get assigned 2 - both.
    species_name_to_data_type_code = (
        survey_data[["species_name", "data_type_code"]]
        .sort_values(["species_name", "data_type_code"])
        .drop_duplicates(["species_name"], keep="last")
        .set_index("species_name")["data_type_code"]
        .to_dict()
    )
    dst_img_path = dst_dir / "img"
    verify_empty_dir(dst_img_path)
    api_species = {}
    for species_name in sorted(survey_data["species_name"].unique()):
        species_dict = crawl_data.get(species_name.lower(), {})

        if "images" in species_dict:
            image_urls: list[str] = []
            for image_dict in species_dict["images"]:
                dst_img_filename = (
                    f"img/{species_dict['id_']}-{len(image_urls)}"
                    f".{image_dict['path'].split('.')[-1]}"
                )
                (dst_dir / dst_img_filename).symlink_to(
                    img_src_path / image_dict["path"]
                )
                image_urls.append(f"/{dst_img_filename}")
        else:
            image_urls = species_dict.get("image_urls", [])

        api_species[species_name] = [
            species_name,
            species_dict.get("common_name", ""),
            species_dict.get("url", None),
            species_name_to_data_type_code[species_name],
            image_urls,
        ]
    _write_json(
        dst_dir / "api-species.json",
        data=api_species,
        data_desc=f"{len(api_species)} species",
    )


def _create_summary_file(survey_data: pd.DataFrame, dst_dir: Path) -> None:
    """Create the overall summary for the homepage, using only RLS surveys."""
    rls_only_data = survey_data[survey_data["program"] == "RLS"]
    unique_names = {
        name
        for name in rls_only_data["species_name"].unique()
        if not name.startswith("Unidentified")
        and not (len(name.split()) == 2 and name.endswith("spp."))
    }
    summary = {
        "animalsobserved": int(rls_only_data["total"].sum()),
        "reefdwellingspecies": len(unique_names),
        "surveycompleted": int(rls_only_data["survey_id"].nunique()),
        "countriessurveyed": int(rls_only_data["country"].nunique()),
    }
    _write_json(dst_dir / "summary.json", data=summary, data_desc=f"summary {summary}")


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
    with crawl_json_path.open() as fp:
        crawl_data = {
            species_dict["name"].lower(): species_dict for species_dict in json.load(fp)
        }
    _logger.info("Read %d items from %s", len(crawl_data), crawl_json_path)
    if len(crawl_data) < min_expected_crawl_items:
        raise ValueError(
            f"Expected at least {min_expected_crawl_items} items, "
            f"but found {len(crawl_data)}"
        )
    img_src_path = (crawl_json_path.parent / "img").resolve()
    survey_data = _read_survey_data(survey_data_dir)
    if len(survey_data) < min_expected_survey_rows:
        raise ValueError(
            f"Expected at least {min_expected_survey_rows} survey rows, "
            f"but found {len(survey_data)}"
        )
    _logger.info("Creating site summaries.")
    _create_site_summaries(survey_data, dst_dir)
    _logger.info("Creating species file.")
    _create_species_file(survey_data, crawl_data, img_src_path, dst_dir)
    _logger.info("Creating summary file.")
    _create_summary_file(survey_data, dst_dir)


def create_static_maps(
    sites_json_path: Path,
    species_json_path: Path,
    surveys_json_path: Path,
    dst_dir: Path,
) -> None:
    """
    Generate and save a distribution map for each species.

    This function reads the sites, species, and surveys JSONs, and writes a map file for
    each species to `<dst_dir>/<species_slug>.png`.
    """
    verify_empty_dir(dst_dir)
    _logger.info("Loading JSONs.")
    species_to_site_obs = load_json(surveys_json_path)
    site_dict = load_json(sites_json_path)
    site_df = pd.DataFrame.from_records(site_dict["rows"], columns=site_dict["keys"])
    species_name_to_slug = {
        species["scientific_name"]: species["slug"]
        for species in load_json(species_json_path)
    }
    _logger.info("Creating global site map.")

    # Reuse the same figure for each central longitude to speed things up.
    central_longitude_to_ax = {
        central_longitude: plt.subplots(
            figsize=(4, 3.2),
            subplot_kw={
                "projection": cartopy.crs.PlateCarree(central_longitude),
                "frameon": False,
            },
        )[1]
        for central_longitude in (0, 180)
    }
    _create_static_map(site_df, dst_dir / "__all-sites.png", central_longitude_to_ax)

    _logger.info("Creating species-level maps.")
    area_name_counts: Counter[str] = Counter()
    for i, (species_name, species_obs) in enumerate(species_to_site_obs.items()):
        if i and not i % 500:
            _logger.info("Processed %d species distributions.", i)
        # Some species have counts, but they're not shown on the website (e.g., spp.),
        # so we only plot those that have a slug.
        if species_name in species_name_to_slug:
            area_name = _create_static_map(
                site_df[site_df["site_code"].isin(species_obs)],
                dst_dir / f"{species_name_to_slug[species_name]}.png",
                central_longitude_to_ax,
            )
            area_name_counts[area_name] += 1

    _logger.info("Area name counts: %s.", area_name_counts)
    _logger.info("Done.")


# The aspect ratio for each specific map area is 4:3, which results in a consistent look
# for the PDF. The ordering is important, as the first area that contains the full site
# distribution is used for a given species.
_SPECIFIC_MAP_AREAS = OrderedDict(
    [
        ("Australia", (0, (90, 180, -50, 17.5))),
        ("Europe", (0, (-30, 42, 10, 64))),
        ("North America", (0, (-135, -10, -3.75, 90))),
        ("Atlantic", (0, (-120, 40, -60, 60))),
        ("Indian", (0, (10, 130, -50, 40))),
        ("Pacific", (180, (-70, 118, -70, 71))),
    ]
)
_WORLD_MAP_AREA = ("World", 180, (-180, 180, -90, 90))


def _get_df_map_area(
    df: pd.DataFrame,
) -> tuple[str, int, tuple[float, float, float, float]]:
    """
    Return the first area that contains the df's sites out of _SPECIFIC_MAP_AREAS.

    _WORLD_MAP_AREA is returned if no specific area contains all the sites.

    The returned tuple is of the form (area_name, central_longitude, extent), where
    extent is a tuple of the form (min_longitude, max_longitude, min_latitude,
    max_latitude).
    """
    for area_name, (central_longitude, extent) in _SPECIFIC_MAP_AREAS.items():
        min_longitude, max_longitude, min_latitude, max_latitude = extent
        if not (
            min_latitude <= df["latitude"].min() <= max_latitude
            and min_latitude <= df["latitude"].max() <= max_latitude
        ):
            continue
        if (
            central_longitude == 0
            and (
                (min_longitude <= df["longitude"]) & (df["longitude"] <= max_longitude)
            ).all()
        ):
            return area_name, central_longitude, extent
        if (
            central_longitude == 180
            and (
                ((df["longitude"] >= -180) & (df["longitude"] <= min_longitude))
                | ((max_longitude <= df["longitude"]) & (df["longitude"] <= 180))
            ).all()
        ):
            return area_name, central_longitude, extent
    return _WORLD_MAP_AREA


def _create_static_map(
    df: pd.DataFrame,
    dst_file_path: Path,
    central_longitude_to_ax: dict[int, plt.Axes],  # type: ignore[name-defined]
) -> str:
    """
    Save a static map containing all the sites in df to dst_file_path.

    Return the name of the area that was used for the map.
    """
    area_name, central_longitude, extent = _get_df_map_area(df)
    ax = central_longitude_to_ax[central_longitude]
    # Clearing the axes to reuse the same fig (faster and avoids keeping too many
    # figs open).
    ax.cla()
    ax.add_feature(cartopy.feature.OCEAN, color="#abcad7")
    ax.scatter(
        df["longitude"],
        df["latitude"],
        color="#d95936",
        transform=cartopy.crs.PlateCarree(),
    )
    ax.set_extent(extent, crs=cartopy.crs.PlateCarree(central_longitude))
    ax.get_figure().savefig(dst_file_path, dpi=100, bbox_inches="tight", pad_inches=0)
    return area_name
