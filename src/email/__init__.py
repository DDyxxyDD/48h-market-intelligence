"""Email delivery boundary (intentionally disabled in the MVP)."""

from pathlib import Path


def deliver_briefing_locally(html_path: Path) -> str:
    """Confirm local output; this function never sends email."""
    return f"Email delivery is disabled. Briefing saved locally to {html_path}"

