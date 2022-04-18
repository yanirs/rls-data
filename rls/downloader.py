import logging
from pathlib import Path

import requests

from .util import verify_empty_dir

_logger = logging.getLogger("rls.processor")


def download_survey_data(survey_data_dir: Path) -> None:
    """Download RLS CSV data files to the given directory, creating it if it doesn't exist."""
    verify_empty_dir(survey_data_dir)
    for data_type in ("M1", "M2_INVERT", "M2_FISH"):
        url = (
            "http://geoserver-rls.imas.utas.edu.au/geoserver/wfs?SERVICE=WFS&outputFormat=csv&"
            f"REQUEST=GetFeature&VERSION=1.0.0&typeName=RLS:{data_type}_DATA"
        )
        out_path = survey_data_dir / f"{data_type.lower()}.csv"
        _logger.info(f"Downloading {url} to {out_path}")
        with open(out_path, "w") as fp:
            fp.write(requests.get(url).text)
