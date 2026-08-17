"""Conservative pre-selection quality gates for especially noisy sections."""

from src.models import Article

HEALTHCARE_MATERIAL = [
    "fda approv", "fda reject", "phase 2", "phase ii", "phase 3", "phase iii", "pivotal", "clinical results",
    "acquisition", "acquire", "merger", "guidance", "earnings", "medicare", "reimbursement", "drug pricing",
    "patent", "litigation", "lawsuit", "safety", "recall", "commercial partnership", "billion", "million",
]
HEALTHCARE_NOISE = [
    "wellness", "healthy eating", "weight loss tips", "consumer health", "lifestyle", "best supplements",
    "home remedy", "beauty tips", "sponsored", "press release distribution", "phase 1", "phase i ",
]


def apply_healthcare_gate(articles: list[Article]) -> tuple[list[Article], list[Article]]:
    """Reject clear lifestyle/promotion noise while retaining uncertain market news for scoring."""
    accepted, rejected = [], []
    for article in articles:
        if article.section != "us_healthcare_equities":
            accepted.append(article)
            continue
        text = f"{article.title} {article.summary}".casefold()
        material = [term for term in HEALTHCARE_MATERIAL if term in text]
        noise = [term for term in HEALTHCARE_NOISE if term in text]
        article.metadata["healthcare_materiality_matches"] = material
        article.metadata["healthcare_noise_matches"] = noise
        if noise and not material:
            article.metadata["rejection_reason"] = "healthcare_noise_gate"
            rejected.append(article)
        else:
            accepted.append(article)
    return accepted, rejected
