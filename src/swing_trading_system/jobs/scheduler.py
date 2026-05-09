from __future__ import annotations

import time
from datetime import date

from swing_trading_system.config import get_settings
from swing_trading_system.pipeline.orchestrator import SwingOrchestrator


def main() -> None:
    settings = get_settings()
    orchestrator = SwingOrchestrator()
    while True:
        orchestrator.run_end_of_day(as_of_date=date.today(), save=True, send_alerts=True)
        time.sleep(settings.swing_monitor_interval_minutes * 60)


if __name__ == "__main__":
    main()
