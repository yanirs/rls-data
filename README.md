# Reef Life Survey data processor

Processing functionality to produce JSONs and other data files for
[Reef Life Survey tools](https://yanirseroussi.com/tags/reef-life-survey/).

## Setup

Develop locally:

    $ poetry install
    $ poetry run pre-commit install

Or in a VirtualBox (with continuous rsyncing of changes):

    $ vagrant up && vagrant rysnc-auto

## Command line interface

Run `rls-data` for available commands:

    $ poetry run rls-data --help

See `.github/workflows/update-data.yml` for the update flow example.

Images can be downloaded to `data/img/` by changing the `scrapy` call to include
`--set ITEM_PIPELINES='{"scrapy.pipelines.images.ImagesPipeline": 1}' --set IMAGES_STORE=data/img`.
