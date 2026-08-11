def pytest_report_teststatus(report):
    if getattr(report, "wasxfail", False):
        return None
    if report.skipped:
        return "skipped", "⏭️", "⏭️ SKIPPED"
    if report.when != "call":
        return None
    if report.passed:
        return "passed", "✅", "✅ PASSED"
    if report.failed:
        return "failed", "❌", "❌ FAILED"
    return None
