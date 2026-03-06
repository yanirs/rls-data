from typing import Any

import pytest
from scrapy.http import HtmlResponse

from rls.scraper import ReefLifeSurveySpider


@pytest.fixture()
def spider() -> ReefLifeSurveySpider:
    return ReefLifeSurveySpider()


def test_parse_start_url(spider: ReefLifeSurveySpider) -> None:
    sitemap_response_body = """
        <urlset>
            <url>
                <loc>https://reeflifesurvey.com/species/labroides-dimidiatus/</loc>
            </url>
            <url>
                <loc>https://images.reeflifesurvey.com/not_a_species_page</loc>
            </url>
        </urlset>
    """
    response = HtmlResponse(
        url="https://reeflifesurvey.com/sitemap-species.xml",
        body=sitemap_response_body,
        encoding="utf-8",
    )
    requests = list(spider.parse_start_url(response))
    assert len(requests) == 1
    assert requests[0].url == "https://reeflifesurvey.com/species/labroides-dimidiatus/"


@pytest.mark.parametrize(
    ("url", "body", "expected_items"),
    [
        pytest.param(
            "https://reeflifesurvey.com/species/labroides-dimidiatus/",
            "<html>"
            '<h1 class="MuiTypography-root">Labroides dimidiatus</h1>'
            '<span class="MuiTypography-root '
            'MuiTypography-subtitle1">Cleaner wrasse | Blue Diesel Wrasse</span>'
            '<div><div class="swiper"><div><img src="image1.jpg"></div></div></div>'
            "</html>",
            [
                {
                    "id_": "labroides-dimidiatus",
                    "name": "Labroides dimidiatus",
                    "common_name": "Cleaner wrasse, Blue Diesel Wrasse",
                    "url": "https://reeflifesurvey.com/species/labroides-dimidiatus/",
                    "image_urls": ["image1.jpg"],
                }
            ],
            id="all_names_and_image",
        ),
        pytest.param(
            "https://reeflifesurvey.com/species/fish2/",
            "<html>"
            '<h1 class="MuiTypography-root"></h1>'
            '<span class="MuiTypography-root MuiTypography-subtitle1"></span>'
            "</html>",
            [
                {
                    "id_": "fish2",
                    "name": "",
                    "common_name": "",
                    "url": "https://reeflifesurvey.com/species/fish2/",
                    "image_urls": [],
                }
            ],
            id="missing_names",
        ),
        pytest.param(
            "https://reeflifesurvey.com/species/fish3/",
            "<html><div>Some unexpected structure</div></html>",
            [
                {
                    "id_": "fish3",
                    "url": "https://reeflifesurvey.com/species/fish3/",
                    "common_name": "",
                    "name": "",
                    "image_urls": [],
                }
            ],
            id="unexpected_html_structure",
        ),
        pytest.param(
            "https://reeflifesurvey.com/species/fish4/",
            '<html><h1 class="MuiTypography-root">Fish Name</h1></html>',
            [
                {
                    "id_": "fish4",
                    "name": "Fish Name",
                    "common_name": "",
                    "url": "https://reeflifesurvey.com/species/fish4/",
                    "image_urls": [],
                }
            ],
            id="name_no_images",
        ),
    ],
)
def test_parse_species_page(
    spider: ReefLifeSurveySpider,
    url: str,
    body: str,
    expected_items: list[dict[str, Any]],
) -> None:
    response = HtmlResponse(url=url, body=body, encoding="utf-8")
    assert list(spider.parse_species_page(response)) == expected_items
