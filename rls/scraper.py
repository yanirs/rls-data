"""Scrapy-based scraper for the RLS website."""
import re
from collections.abc import Generator
from typing import Any

import scrapy.http
from scrapy import Request, Selector
from scrapy.spiders.crawl import CrawlSpider


class ReefLifeSurveySpider(CrawlSpider):  # type: ignore[misc]
    """Scraper for the RLS website that collects species information."""

    name = "rls"
    allowed_domains = ["reeflifesurvey.com"]
    start_urls = ["https://reeflifesurvey.com/sitemap-species.xml"]

    def parse_start_url(
        self, response: scrapy.http.Response, **_: Any
    ) -> Generator[Request, None, None]:
        """Parse the sitemap and yield requests for each species page."""
        # response.css doesn't work for some reason...
        for link in Selector(text=response.body).css("loc ::text").extract():
            if not link.startswith("https://images.reeflifesurvey"):
                yield Request(link, callback=self.parse_species_page)

    def parse_species_page(
        self, response: scrapy.http.Response
    ) -> Generator[dict[str, Any], None, None]:
        """Parse a species page and yield a dictionary of species information."""
        common_name_elements = response.css(
            "span.MuiTypography-root.MuiTypography-subtitle1 ::text"
        )
        yield dict(
            id_=response.url.split("/")[-2],
            name=re.sub(
                r"\s+",
                " ",
                "".join(response.css("h1.MuiTypography-root ::text").extract()),
            ),
            common_name=common_name_elements.extract()[0].replace(" |", ",")
            if common_name_elements
            else "",
            url=response.url,
            image_urls=[
                image_url
                for image_url in response.css(
                    "div.swiper:nth-child(1) > div:nth-child(1) ::attr(src)"
                ).extract()
                if 'defaultspecies' not in image_url
            ],
        )
