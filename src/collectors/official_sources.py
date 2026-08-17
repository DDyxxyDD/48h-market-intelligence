"""Curated official/public feeds. Entries are deliberately easy to extend."""

from src.collectors.rss import collect_rss
from src.collectors.fda import collect_fda_announcements, collect_openfda

OFFICIAL_FEEDS = [
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "official_central_bank", 3.0),
    ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html", "official_central_bank", 3.0),
    ("Bank of England", "https://www.bankofengland.co.uk/rss/news", "official_central_bank", 3.0),
]


def collect_official_sources():
    return [collect_rss(*feed) for feed in OFFICIAL_FEEDS] + [collect_openfda(), collect_fda_announcements()]
