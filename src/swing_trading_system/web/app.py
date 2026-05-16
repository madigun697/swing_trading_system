"""FastAPI application for Swing runtime health and v1 UI."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from swing_trading_system import __version__
from swing_trading_system.backtest.engine import BacktestEngine
from swing_trading_system.backtest.models import BacktestConfig
from swing_trading_system.backtest.repository import BacktestRepository
from swing_trading_system.config import Settings
from swing_trading_system.repositories.shared_market import SharedMarketRepository

WEB_DIR = Path(__file__).parent
TEMPLATE_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def create_app(
    repository: SharedMarketRepository | None = None,
    backtest_repository: BacktestRepository | None = None,
) -> FastAPI:
    app = FastAPI(title="Swing Trading System", version=__version__)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.state.shared_market_repository = repository or SharedMarketRepository()
    app.state.backtest_repository = backtest_repository or BacktestRepository()
    app.state.settings = Settings()

    from swing_trading_system.logger import setup_logger
    logger = setup_logger(__name__)
    logger.info("Swing Trading System web application starting up")

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        readiness = app.state.shared_market_repository.check_readiness()
        payload = {
            "status": "ok" if readiness.ok else "unavailable",
            **readiness.to_dict(),
        }
        return JSONResponse(payload, status_code=200 if readiness.ok else 503)

    @app.get("/")
    async def index(request: Request):
        readiness = app.state.shared_market_repository.check_readiness()
        latest_trade_date = None
        signal_count = 0
        recent_runs = []
        ui_warnings: list[str] = []
        try:
            latest_trade_date = (
                app.state.shared_market_repository.fetch_latest_trade_date()
            )
        except Exception as exc:  # pragma: no cover - defensive dashboard fallback.
            ui_warnings.append(f"latest trade date unavailable: {type(exc).__name__}")
        try:
            backtest_repo = app.state.backtest_repository
            signal_count = backtest_repo.count_signals()
            recent_runs = backtest_repo.list_recent_runs(limit=5)
        except Exception as exc:
            ui_warnings.append(f"backtest summary unavailable: {type(exc).__name__}")
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "active_page": "dashboard",
                "readiness": readiness,
                "latest_trade_date": latest_trade_date,
                "signal_count": signal_count,
                "recent_runs": recent_runs,
                "ui_warnings": ui_warnings,
            },
        )

    @app.get("/signals")
    async def signals(request: Request):
        rows = []
        ui_warnings: list[str] = []
        try:
            rows = app.state.backtest_repository.fetch_signals(limit=100)
        except Exception as exc:
            ui_warnings.append(f"signals unavailable: {type(exc).__name__}")
        return templates.TemplateResponse(
            request,
            "signals.html",
            {
                "active_page": "signals",
                "signals": rows,
                "display_signals": _display_signals(rows),
                "ui_warnings": ui_warnings,
            },
        )

    @app.get("/backtests")
    async def backtests(request: Request):
        recent_runs = []
        ui_warnings: list[str] = []
        try:
            recent_runs = app.state.backtest_repository.list_recent_runs(limit=20)
        except Exception as exc:
            ui_warnings.append(f"backtest runs unavailable: {type(exc).__name__}")
        return templates.TemplateResponse(
            request,
            "backtests.html",
            {
                "active_page": "backtests",
                "recent_runs": recent_runs,
                "ui_warnings": ui_warnings,
            },
        )

    @app.get("/backtests/run")
    async def backtest_run_form(request: Request):
        return templates.TemplateResponse(
            request,
            "backtest_run.html",
            _backtest_run_context(request, _default_run_form(app.state.settings)),
        )

    @app.post("/backtests/run")
    async def run_backtest_from_form(request: Request):
        form_values = _default_run_form(app.state.settings)
        form_values.update(await _read_urlencoded_form(request))
        errors = _validate_run_form(form_values)
        if errors:
            return templates.TemplateResponse(
                request,
                "backtest_run.html",
                _backtest_run_context(request, form_values, errors=errors),
                status_code=422,
            )
        try:
            config = _config_from_form(form_values)
            start_date = (
                date.fromisoformat(form_values["start_date"])
                if form_values.get("start_date")
                else None
            )
            end_date = (
                date.fromisoformat(form_values["end_date"])
                if form_values.get("end_date")
                else None
            )
            symbols = _parse_symbols(str(form_values.get("symbols") or ""))
            strategy = _selected_strategy_filter(form_values)
            repository = app.state.backtest_repository
            signals = repository.fetch_signals(
                start_date=start_date,
                end_date=end_date,
                strategy=strategy,
                symbols=symbols,
            )
            prices = repository.fetch_prices_for_signals(
                signals,
                end_date=None,
                max_hold_days=config.max_hold_days,
                benchmark_symbol=config.benchmark_symbol,
            )
            result = BacktestEngine().run(
                signals=signals, prices_by_symbol=prices, config=config
            )
            repository.save_result(result)
        except Exception as exc:
            return templates.TemplateResponse(
                request,
                "backtest_run.html",
                _backtest_run_context(
                    request,
                    form_values,
                    ui_warnings=[f"backtest run unavailable: {type(exc).__name__}"],
                ),
                status_code=503,
            )
        return RedirectResponse(
            url=str(request.url_for("backtest_detail", run_id=result.run_id)),
            status_code=303,
        )

    @app.get("/backtests/{run_id}")
    async def backtest_detail(request: Request, run_id: str):
        trades = []
        equity_curve = []
        summary: dict[str, object] = {}
        ui_warnings: list[str] = []
        try:
            trades = app.state.backtest_repository.fetch_run_trades(run_id)
            equity_curve = app.state.backtest_repository.fetch_run_equity_curve(run_id)
            summary = app.state.backtest_repository.fetch_run_summary(run_id)
        except Exception as exc:
            ui_warnings.append(f"backtest detail unavailable: {type(exc).__name__}")
        total_pnl = (
            _safe_float(summary.get("total_pnl"))
            if summary
            else sum(_safe_float(row.get("pnl")) for row in trades)
        )
        report_summary = _build_report_summary(run_id, trades, equity_curve, summary)
        return templates.TemplateResponse(
            request,
            "backtest_detail.html",
            {
                "active_page": "backtests",
                "run_id": run_id,
                "trades": trades,
                "equity_curve": equity_curve,
                "total_pnl": round(total_pnl, 6),
                "summary": summary,
                "report_summary": report_summary,
                "display_trades": _display_trades(trades),
                "display_equity_curve": _display_equity_curve(equity_curve),
                "ui_warnings": ui_warnings,
            },
        )

    return app


def _build_report_summary(
    run_id: str,
    trades: list[dict[str, object]],
    equity_curve: list[dict[str, object]],
    summary: dict[str, object],
) -> dict[str, object]:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
    duplicate_counts: dict[tuple[object, ...], int] = {}
    exit_reasons: dict[str, int] = {}
    for trade in trades:
        details = trade.get("details") if isinstance(trade.get("details"), dict) else {}
        signal = (
            details.get("signal") if isinstance(details.get("signal"), dict) else {}
        )
        key = (
            trade.get("symbol"),
            signal.get("strategy") or details.get("strategy"),
            signal.get("signal_date"),
            signal.get("entry_price"),
            signal.get("stop_price"),
            signal.get("target_price"),
        )
        duplicate_counts[key] = duplicate_counts.get(key, 0) + 1
        reason = str(details.get("exit_reason") or "unknown")
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    duplicates = [
        {"key": str(key), "count": count}
        for key, count in duplicate_counts.items()
        if count > 1
    ]
    return {
        "run_id": run_id,
        "trade_count": summary.get("trade_count", len(trades)),
        "start_date": summary.get("start_date"),
        "end_date": summary.get("end_date"),
        "initial_equity": summary.get("initial_equity") or config.get("initial_equity"),
        "final_equity": summary.get("final_equity")
        or (equity_curve[-1].get("equity") if equity_curve else None),
        "total_pnl": summary.get("total_pnl") or metrics.get("total_pnl"),
        "total_return": summary.get("total_return") or metrics.get("total_return"),
        "max_drawdown": summary.get("max_drawdown") or metrics.get("max_drawdown"),
        "win_rate": summary.get("win_rate") or metrics.get("win_rate"),
        "profit_factor": summary.get("profit_factor") or metrics.get("profit_factor"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "cagr": metrics.get("cagr"),
        "calmar_ratio": metrics.get("calmar_ratio"),
        "benchmark_symbol": config.get("benchmark_symbol")
        or metrics.get("benchmark_symbol")
        or "SPY",
        "benchmark_return": metrics.get("benchmark_return"),
        "benchmark_mdd": metrics.get("benchmark_mdd"),
        "benchmark_cagr": metrics.get("benchmark_cagr"),
        "excess_return": metrics.get("excess_return"),
        "max_consecutive_wins": metrics.get("max_consecutive_wins"),
        "max_consecutive_losses": metrics.get("max_consecutive_losses"),
        "average_hold_days": metrics.get("average_hold_days"),
        "expectancy_per_dollar": metrics.get("expectancy_per_dollar"),
        "rejection_count": summary.get("rejection_count")
        or metrics.get("rejection_count", 0),
        "symbol_contribution": metrics.get("symbol_contribution", {}),
        "strategy_contribution": metrics.get("strategy_contribution", {}),
        "regime_slice_metrics": _slice_metrics(trades, _trade_market_regime),
        "exit_reasons": exit_reasons,
        "monthly_slice_metrics": _slice_metrics(
            trades, lambda trade: str(trade.get("entry_date"))[:7]
        ),
        "strategy_slice_metrics": _slice_metrics(trades, _trade_strategy),
        "exit_slice_metrics": _slice_metrics(trades, _trade_exit_reason),
        "sector_slice_metrics": _slice_metrics(trades, _trade_sector),
        "duplicates": duplicates,
        "config": config,
        "market_regime_enabled": any(
            _trade_market_regime(trade) != "unknown" for trade in trades
        ),
        "market_regime_count": sum(
            1 for trade in trades if _trade_market_regime(trade) != "unknown"
        ),
        "chart": _build_equity_chart(equity_curve),
    }


def _slice_metrics(trades: list[dict[str, object]], key_fn) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, float]] = {}
    for trade in trades:
        key = key_fn(trade) or "unknown"
        row = grouped.setdefault(
            str(key), {"trade_count": 0.0, "total_pnl": 0.0, "wins": 0.0}
        )
        pnl = _safe_float(trade.get("pnl"))
        row["trade_count"] += 1
        row["total_pnl"] += pnl
        row["wins"] += 1 if pnl > 0 else 0
    return [
        {
            "name": name,
            "trade_count": int(values["trade_count"]),
            "total_pnl": round(values["total_pnl"], 6),
            "win_rate": (values["wins"] / values["trade_count"])
            if values["trade_count"]
            else 0.0,
            "average_pnl": (values["total_pnl"] / values["trade_count"])
            if values["trade_count"]
            else 0.0,
        }
        for name, values in sorted(grouped.items(), key=lambda item: item[0])
    ]


def _trade_strategy(trade: dict[str, object]) -> str:
    details = trade.get("details") if isinstance(trade.get("details"), dict) else {}
    signal = details.get("signal") if isinstance(details.get("signal"), dict) else {}
    return str(details.get("strategy") or signal.get("strategy") or "unknown")


def _trade_exit_reason(trade: dict[str, object]) -> str:
    details = trade.get("details") if isinstance(trade.get("details"), dict) else {}
    return str(details.get("exit_reason") or "unknown")


def _trade_sector(trade: dict[str, object]) -> str:
    details = trade.get("details") if isinstance(trade.get("details"), dict) else {}
    signal = details.get("signal") if isinstance(details.get("signal"), dict) else {}
    signal_details = (
        signal.get("details") if isinstance(signal.get("details"), dict) else {}
    )
    features = (
        signal_details.get("features")
        if isinstance(signal_details.get("features"), dict)
        else {}
    )
    return str(features.get("sector") or "unknown")


def _trade_market_regime(trade: dict[str, object]) -> str:
    details = trade.get("details") if isinstance(trade.get("details"), dict) else {}
    signal = details.get("signal") if isinstance(details.get("signal"), dict) else {}
    signal_details = (
        signal.get("details") if isinstance(signal.get("details"), dict) else {}
    )
    direct_regime = _regime_payload(signal_details.get("market_regime"))
    feature_regime = _regime_payload(
        (signal_details.get("features") or {}).get("market_regime")
        if isinstance(signal_details.get("features"), dict)
        else None
    )
    regime = direct_regime or feature_regime
    return str(regime.get("regime_id") or "unknown")


def _default_run_form(settings: Settings) -> dict[str, str]:
    aggressive_defaults = BacktestConfig()
    return {
        "risk_profile": f"market_regime_{settings.swing_regime_profile}",
        "start_date": "2025-01-02",
        "end_date": "2026-05-01",
        "strategy": "__market_regime__",
        "symbols": "",
        "initial_equity": str(settings.swing_account_equity),
        "fee_bps": str(settings.swing_fee_bps),
        "slippage_bps": str(settings.swing_slippage_bps),
        "max_hold_days": str(aggressive_defaults.max_hold_days),
        "max_positions": str(aggressive_defaults.max_positions),
        "max_position_pct": str(aggressive_defaults.max_position_pct),
        "max_gross_exposure_pct": str(aggressive_defaults.max_gross_exposure_pct),
        "pullback_size_multiplier": str(aggressive_defaults.pullback_size_multiplier),
        "benchmark_symbol": aggressive_defaults.benchmark_symbol,
        "target_scale_out_pct": str(aggressive_defaults.target_scale_out_pct),
        "trailing_ma_days": str(aggressive_defaults.trailing_ma_days),
        "enable_trailing_stop": "true"
        if aggressive_defaults.enable_trailing_stop
        else "",
    }


async def _read_urlencoded_form(request: Request) -> dict[str, str]:
    raw_body = (await request.body()).decode("utf-8")
    parsed = parse_qs(raw_body, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _validate_run_form(form_values: dict[str, str]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for field in ("start_date", "end_date"):
        value = form_values.get(field)
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                errors[field] = "YYYY-MM-DD 형식으로 입력해 주세요."
    if (
        form_values.get("start_date")
        and form_values.get("end_date")
        and "start_date" not in errors
        and "end_date" not in errors
    ):
        if date.fromisoformat(form_values["start_date"]) > date.fromisoformat(
            form_values["end_date"]
        ):
            errors["end_date"] = "종료일은 시작일 이후여야 합니다."
    positive_fields = {
        "initial_equity": "초기 자본",
        "max_hold_days": "최대 보유일",
        "max_positions": "동시 보유 종목 수",
        "max_position_pct": "종목당 최대 비중",
        "max_gross_exposure_pct": "총 노출 한도",
        "pullback_size_multiplier": "Pullback 수량 배율",
        "benchmark_symbol": "벤치마크",
        "target_scale_out_pct": "목표가 부분익절 비중",
        "trailing_ma_days": "Trailing MA 일수",
    }
    for field, label in positive_fields.items():
        value = str(form_values.get(field) or "").strip()
        if not value:
            errors[field] = f"{label} 값을 입력해 주세요."
            continue
        if field == "benchmark_symbol":
            continue
        try:
            number = float(value)
        except ValueError:
            errors[field] = f"{label}은 숫자로 입력해 주세요."
            continue
        if number <= 0:
            errors[field] = f"{label}은 0보다 커야 합니다."
    return errors


def _config_from_form(form_values: dict[str, str]) -> BacktestConfig:
    return BacktestConfig(
        initial_equity=float(form_values["initial_equity"]),
        fee_bps=float(form_values.get("fee_bps") or 0),
        slippage_bps=float(form_values.get("slippage_bps") or 0),
        max_hold_days=int(float(form_values["max_hold_days"])),
        max_positions=int(float(form_values["max_positions"])),
        max_gross_exposure_pct=float(form_values["max_gross_exposure_pct"]),
        max_position_pct=float(form_values["max_position_pct"]),
        pullback_size_multiplier=float(form_values["pullback_size_multiplier"]),
        benchmark_symbol=str(form_values["benchmark_symbol"]).upper(),
        enable_trailing_stop=bool(form_values.get("enable_trailing_stop")),
        target_scale_out_pct=float(form_values["target_scale_out_pct"]),
        trailing_ma_days=int(float(form_values["trailing_ma_days"])),
    )


def _backtest_run_context(
    request: Request,
    form_values: dict[str, str],
    errors: dict[str, str] | None = None,
    ui_warnings: list[str] | None = None,
) -> dict[str, object]:
    return {
        "request": request,
        "active_page": "backtests",
        "form_values": form_values,
        "errors": errors or {},
        "ui_warnings": ui_warnings or [],
        "strategy_options": _strategy_options(),
        "selected_strategy_label": _strategy_option_label(
            str(form_values.get("strategy") or "")
        ),
        "regime_profile": request.app.state.settings.swing_regime_profile,
        "vix_benchmark_name": request.app.state.settings.swing_vix_benchmark_name,
        "require_vix": request.app.state.settings.swing_require_vix,
    }


def _parse_symbols(value: str) -> list[str] | None:
    symbols = [item.strip().upper() for item in value.split(",") if item.strip()]
    return symbols or None


def _strategy_options() -> list[dict[str, str]]:
    return [
        {
            "value": "__market_regime__",
            "label": "Market Regime Switching",
        },
        {"value": "", "label": "전체 저장 signal"},
        {"value": "breakout", "label": "Breakout"},
        {"value": "pullback", "label": "Pullback"},
        {"value": "quality_momentum", "label": "Quality Momentum"},
        {"value": "breakout+pullback", "label": "Breakout + Pullback"},
        {
            "value": "breakout+quality_momentum",
            "label": "Breakout + Quality Momentum",
        },
        {
            "value": "pullback+quality_momentum",
            "label": "Pullback + Quality Momentum",
        },
    ]


def _strategy_option_label(value: str) -> str:
    for option in _strategy_options():
        if option["value"] == value:
            return option["label"]
    return "Custom"


def _selected_strategy_filter(form_values: dict[str, str]) -> str | None:
    strategy = str(form_values.get("strategy") or "")
    if strategy == "__market_regime__":
        return None
    return strategy or None


def _regime_payload(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _display_signals(signals: list[object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for signal in signals:
        details = (
            getattr(signal, "details", None)
            if hasattr(signal, "details")
            else (signal.get("details") if isinstance(signal, dict) else {})
        )
        details = details if isinstance(details, dict) else {}
        features = (
            details.get("features") if isinstance(details.get("features"), dict) else {}
        )
        regime = _regime_payload(details.get("market_regime")) or _regime_payload(
            features.get("market_regime")
        )
        rows.append(
            {
                "id": getattr(signal, "id", None)
                if hasattr(signal, "id")
                else signal.get("id"),
                "symbol": getattr(signal, "symbol", None)
                if hasattr(signal, "symbol")
                else signal.get("symbol"),
                "strategy": getattr(signal, "strategy", None)
                if hasattr(signal, "strategy")
                else signal.get("strategy"),
                "signal_date": getattr(signal, "signal_date", None)
                if hasattr(signal, "signal_date")
                else signal.get("signal_date"),
                "entry_price": getattr(signal, "entry_price", None)
                if hasattr(signal, "entry_price")
                else signal.get("entry_price"),
                "stop_price": getattr(signal, "stop_price", None)
                if hasattr(signal, "stop_price")
                else signal.get("stop_price"),
                "target_price": getattr(signal, "target_price", None)
                if hasattr(signal, "target_price")
                else signal.get("target_price"),
                "score": getattr(signal, "score", None)
                if hasattr(signal, "score")
                else signal.get("score"),
                "regime_id": regime.get("regime_id") or "unknown",
                "regime_reason": regime.get("reason") or "-",
            }
        )
    return rows


def _display_trades(trades: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for trade in trades:
        details = trade.get("details") if isinstance(trade.get("details"), dict) else {}
        entry_notional = _safe_float(details.get("entry_notional")) or _safe_float(
            trade.get("entry_price")
        ) * _safe_float(trade.get("quantity"))
        pnl = _safe_float(trade.get("pnl"))
        return_pct = pnl / entry_notional if entry_notional else 0.0
        rows.append(
            {
                "symbol": trade.get("symbol"),
                "strategy": details.get("strategy")
                or _signal_value(details, "strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "hold_days": _date_diff(
                    trade.get("entry_date"), trade.get("exit_date")
                ),
                "entry_price": trade.get("entry_price"),
                "exit_price": trade.get("exit_price"),
                "quantity": trade.get("quantity"),
                "pnl": pnl,
                "return_pct": return_pct,
                "market_regime": _trade_market_regime(trade),
                "exit_reason": details.get("exit_reason") or "unknown",
                "legs": details.get("exit_legs") or [],
            }
        )
    return rows


def _display_equity_curve(
    equity_curve: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows = []
    for point in equity_curve:
        details = point.get("details") if isinstance(point.get("details"), dict) else {}
        rows.append(
            {
                "equity_date": point.get("equity_date"),
                "equity": point.get("equity"),
                "daily_pnl": details.get("daily_pnl"),
                "drawdown": point.get("drawdown"),
                "benchmark_equity": details.get("benchmark_equity"),
                "benchmark_drawdown": details.get("benchmark_drawdown"),
                "open_trade_count": details.get("open_trade_count"),
            }
        )
    return rows


def _build_equity_chart(equity_curve: list[dict[str, object]]) -> dict[str, str]:
    if not equity_curve:
        return {"strategy_points": "", "benchmark_points": ""}
    width = 720
    height = 220
    pad = 18
    strategy_values = [_safe_float(point.get("equity")) for point in equity_curve]
    benchmark_values = [
        _safe_float((point.get("details") or {}).get("benchmark_equity"))
        if isinstance(point.get("details"), dict)
        else 0.0
        for point in equity_curve
    ]
    values = [value for value in strategy_values + benchmark_values if value > 0]
    if not values:
        return {"strategy_points": "", "benchmark_points": ""}
    low = min(values)
    high = max(values)

    def points_for(series: list[float]) -> str:
        points = []
        for index, value in enumerate(series):
            if value <= 0:
                continue
            x = pad + ((width - pad * 2) * index / max(len(series) - 1, 1))
            ratio = 0.5 if high == low else (value - low) / (high - low)
            y = height - pad - ((height - pad * 2) * ratio)
            points.append(f"{x:.2f},{y:.2f}")
        return " ".join(points)

    return {
        "strategy_points": points_for(strategy_values),
        "benchmark_points": points_for(benchmark_values),
    }


def _signal_value(details: dict[str, object], key: str) -> object:
    signal = details.get("signal")
    if isinstance(signal, dict):
        return signal.get(key)
    return None


def _date_diff(start: object, end: object) -> int | None:
    start_date = _coerce_date(start)
    end_date = _coerce_date(end)
    if start_date is None or end_date is None:
        return None
    return (end_date - start_date).days


def _coerce_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


app = create_app()
