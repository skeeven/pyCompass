"""Human-friendly formatting for saved sleep report aggregates."""

from decimal import Decimal, ROUND_HALF_UP

NIGHT_COUNTS = {"nights_over_four_hours", "nights_over_six_hours"}


def format_duration(hours):
    """Display decimal-hour storage as hours and minutes, rounded once."""
    minutes = int((Decimal(str(hours)) * 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{minutes // 60}h {minutes % 60:02d}m"


def format_report_value(key, value, denominator=None):
    """Format values for reading without changing the persisted measurement."""
    if key == "cpap_usage_hours":
        return format_duration(value)
    if key in NIGHT_COUNTS:
        count = str(int(value)) if float(value).is_integer() else f"{value:g}"
        return f"{count} of {denominator} nights" if denominator is not None else count
    if key in {"ahi", "leak_l_min"}:
        return f"{value:.2f}"
    return f"{value:.2f}"


def duplicate_import_message(saved, skipped):
    """Report duplicates as an expected import outcome, not an error."""
    if skipped and saved:
        return (
            f"{saved} new reporting period{'s' if saved != 1 else ''} saved. "
            f"{skipped} already saved; left unchanged."
        )
    if skipped:
        return (
            f"All {skipped} reporting period{'s' if skipped != 1 else ''} "
            "already saved. No changes needed."
        )
    return f"{saved} new reporting period{'s' if saved != 1 else ''} saved."
