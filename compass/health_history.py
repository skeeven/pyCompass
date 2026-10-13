"""Read-only, owner-scoped history of verified health report summaries."""

from compass.health_reports import METRICS


def list_saved_reports(db, user_id):
    """Return owned reports with their verified metrics, newest first."""
    with db.connect() as conn:
        cursor = conn.execute(
            """SELECT id, uploaded_at, filename, report_type, status,
                      period_start, period_end
               FROM health_reports
               WHERE user_id = ?
               ORDER BY uploaded_at DESC, period_end DESC, period_start DESC, id DESC""",
            (user_id,),
        )
        reports = [
            dict(zip(("id", "uploaded_at", "filename", "report_type", "status",
                      "period_start", "period_end"), row))
            for row in cursor.fetchall()
        ]
        metrics_cursor = conn.execute(
            """SELECT report_id, metric_name, metric_value, unit, source_label
               FROM health_report_metrics WHERE user_id = ?
               ORDER BY metric_name""",
            (user_id,),
        )
        by_report = {report["id"]: {} for report in reports}
        for report_id, key, value, unit, source in metrics_cursor.fetchall():
            if report_id not in by_report:
                continue
            if key not in METRICS:
                continue
            by_report[report_id][key] = {
                "value": value, "unit": unit, "source": source,
            }
        for report in reports:
            report["metrics"] = by_report[report["id"]]
    return reports
