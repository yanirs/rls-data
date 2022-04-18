from typing import Generator

import scrapy.http
from pyasn1.type.univ import Any
from scrapy import Request, Selector
from scrapy.spiders.crawl import CrawlSpider


# TODO: document this file (flake8 should complain more)
class ReefLifeSurveySpider(CrawlSpider):  # type: ignore[misc]
    name = "rls"
    allowed_domains = ["reeflifesurvey.com"]
    start_urls = ["https://reeflifesurvey.com/sitemap-species.xml"]

    def parse_start_url(self, response: scrapy.http.Response, **_: Any) -> Generator[Request, None, None]:
        # response.css doesn't work for some reason...
        for link in Selector(text=response.body).css("loc ::text").extract():
            if not link.startswith("https://images.reeflifesurvey"):
                yield Request(link, callback=self.parse_species_page)

    def parse_species_page(self, response: scrapy.http.Response) -> Generator[dict[str, Any], None, None]:
        common_name_elements = response.css(".fishname .commonname ::text")
        yield dict(
            id_=response.url.split("/")[-2],
            name=response.css(".fishname h2 i ::text").extract()[0],
            common_name=common_name_elements.extract()[0] if common_name_elements else "",
            url=response.url,
            image_urls=response.css("#lightSlider img ::attr(src)").extract(),
        )
