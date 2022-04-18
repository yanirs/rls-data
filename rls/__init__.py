import logging

import defopt

from rls.downloader import download_survey_data
from rls.processor import create_api_jsons


def run_cli():
    """Run the command line interface with defopt."""
    logging.basicConfig(
        format="%(asctime)s [%(name)s.%(funcName)s:%(lineno)d] %(levelname)s: %(message)s", level=logging.INFO
    )
    defopt.run([download_survey_data, create_api_jsons])
