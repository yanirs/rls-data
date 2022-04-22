"""Survey data downloader."""
import logging
from pathlib import Path

import requests

from .util import verify_empty_dir

_logger = logging.getLogger("rls.processor")


def download_survey_data(survey_data_dir: Path) -> None:
    """Download RLS CSV data files to the given directory, creating it if it doesn't exist."""
    verify_empty_dir(survey_data_dir)
    # TODO: limit to only the RLS program? `&CQL_FILTER=(program%20LIKE%20'RLS')`
    # TODO: parallelise?
    # TODO: drop m0?
    for data_type in ("m0_off_transect_sighting", "m1", "m2_cryptic_fish", "m2_inverts"):
        url = (
            "https://geoserver-portal.aodn.org.au/geoserver/ows?SERVICE=WFS&outputFormat=csv&REQUEST=GetFeature&"
            f"VERSION=1.0.0&CQL_FILTER=(program%20LIKE%20'RLS')&typeName=imos:ep_{data_type}_public_data"
        )
        out_path = survey_data_dir / f"{data_type.lower()}.csv"
        _logger.info(f"Downloading {url} to {out_path}")
        with open(out_path, "w") as fp:
            fp.write(requests.get(url).text)
