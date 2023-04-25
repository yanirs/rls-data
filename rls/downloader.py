"""Survey data downloader."""
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from .util import verify_empty_dir

_logger = logging.getLogger("rls.processor")


def download_survey_data(survey_data_dir: Path) -> None:
    """Download RLS CSV data files to the given directory, creating it if needed."""
    verify_empty_dir(survey_data_dir)
    ThreadPoolExecutor(max_workers=3).map(
        _download_survey_data_file,
        [
            (
                "https://geoserver-portal.aodn.org.au/geoserver/ows?"
                "SERVICE=WFS&outputFormat=csv&REQUEST=GetFeature&"
                f"VERSION=1.0.0&typeName=imos:ep_{data_type}_public_data",
                survey_data_dir / f"{data_type}.csv",
            )
            for data_type in ("m1", "m2_cryptic_fish", "m2_inverts")
        ],
        # Five minutes should be plenty of time to download the largest file (m1).
        timeout=300,
    )


def _download_survey_data_file(url_and_out_path: tuple[str, Path]) -> None:
    """Download a single survey data file."""
    url, out_path = url_and_out_path
    _logger.info("Downloading %s to %s", url, out_path)
    with open(out_path, "w") as fp:
        fp.write(requests.get(url).text)
    _logger.info("Saved %s", out_path)
