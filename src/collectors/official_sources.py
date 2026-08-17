"""Curated official/public feeds. Entries are deliberately easy to extend."""

from src.collectors.rss import collect_rss

OFFICIAL_FEEDS = [
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "official_central_bank", 3.0),
    ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html", "official_central_bank", 3.0),
    ("Bank of England", "https://www.bankofengland.co.uk/rss/news", "official_central_bank", 3.0),
    ("U.S. FDA Press Announcements", "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml", "official_regulator", 3.0),
    ("U.S. FDA MedWatch", "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch/rss.xml", "official_regulator", 3.0),
]


def collect_official_sources():
    return [collect_rss(*feed) for feed in OFFICIAL_FEEDS]

