import logging
from pathlib import Path

import requests

from .util import verify_empty_dir

_logger = logging.getLogger("rls.processor")


def download_survey_data(survey_data_dir: Path):
    """Download RLS CSV data files to the given directory, creating it if it doesn't exist."""
    verify_empty_dir(survey_data_dir)
    # TODO: new links:
    # - "https://geoserver-portal.aodn.org.au/geoserver/ows?typeName=imos:ep_m2_inverts_public_data&SERVICE=WFS&outputFormat=csv&REQUEST=GetFeature&VERSION=1.0.0"
    # - "https://geoserver-portal.aodn.org.au/geoserver/ows?typeName=imos:ep_m0_off_transect_sighting_public_data&SERVICE=WFS&outputFormat=csv&REQUEST=GetFeature&VERSION=1.0.0"
    # - "https://geoserver-portal.aodn.org.au/geoserver/ows?typeName=imos:ep_m2_cryptic_fish_public_data&SERVICE=WFS&outputFormat=csv&REQUEST=GetFeature&VERSION=1.0.0"
    # - "https://geoserver-portal.aodn.org.au/geoserver/ows?typeName=imos:ep_m1_public_data&SERVICE=WFS&outputFormat=csv&REQUEST=GetFeature&VERSION=1.0.0"
    # TODO: survey_list and site_list needed?
    # TODO: limit to only the RLS program? `&CQL_FILTER=(program%20LIKE%20'RLS')`
    # TODO: parse the new files
    # for data_type in ('m0_off_transect_sighting', 'm1', 'm2_cryptic_fish', 'm2_inverts'):
    #     url = ('https://geoserver-portal.aodn.org.au/geoserver/ows?SERVICE=WFS&outputFormat=csv&REQUEST=GetFeature&'
    #            f'VERSION=1.0.0&typeName=imos:ep_{data_type}_public_data')
    #     out_path = survey_data_dir / f"{data_type.lower()}.csv"
    #     _logger.info(f'Downloading {url} to {out_path}')
    #     with open(out_path, 'w') as fp:
    #         fp.write(requests.get(url).text)

    for data_type in ("M1", "M2_INVERT", "M2_FISH"):
        url = (
            "http://geoserver-rls.imas.utas.edu.au/geoserver/wfs?SERVICE=WFS&outputFormat=csv&"
            f"REQUEST=GetFeature&VERSION=1.0.0&typeName=RLS:{data_type}_DATA"
        )
        out_path = survey_data_dir / f"{data_type.lower()}.csv"
        _logger.info(f"Downloading {url} to {out_path}")
        with open(out_path, "w") as fp:
            fp.write(requests.get(url).text)
