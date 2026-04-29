"""Dolt server lifecycle — list, stop, idle-stop subcommands."""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

from bd_timew.util import load_activity_state, root_log


def _bd_dolt_in(project_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bd", "dolt", *args],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )


def _server_log_mtime(project_dir: Path) -> dt.datetime | None:
    """Return the mtime of the dolt server log as a UTC datetime, or None."""
    log_path = project_dir / ".beads" / "dolt-server.log"
    if not log_path.exists():
        return None
    mtime = log_path.stat().st_mtime
    return dt.datetime.fromtimestamp(mtime, tz=dt.timezone.utc)


def _last_activity(project_path: str, project_dir: Path) -> dt.datetime | None:
    """Return the most recent activity timestamp from all available signals."""
    candidates: list[dt.datetime] = []

    # Signal 1: bd-timew start/stop events
    state = load_activity_state()
    ts_str = state.get(project_path)
    if ts_str:
        try:
            candidates.append(
                dt.datetime.fromisoformat(ts_str).replace(tzinfo=dt.timezone.utc)
            )
        except ValueError:
            pass

    # Signal 2: dolt server log mtime (every connection updates it)
    log_mtime = _server_log_mtime(project_dir)
    if log_mtime:
        candidates.append(log_mtime)

    return max(candidates) if candidates else None


def cmd_servers() -> None:
    """List registered repos and their Dolt server status."""
    from bd_timew.project import load_repos_config  # late import: avoid cycle

    config = load_repos_config()
    repos = config.get("repos", [])
    if not repos:
        from bd_timew.util import REPOS_CONFIG
        root_log.info("No repos registered in %s", REPOS_CONFIG)
        return

    for repo in repos:
        path = repo.get("path")
        if not path:
            continue
        project_dir = Path(path)
        if not project_dir.is_dir():
            root_log.warning("%s  [directory not found]", path)
            continue

        result = _bd_dolt_in(project_dir, "status")
        combined = (result.stdout + result.stderr).lower()

        if result.returncode == 0:
            status_line = result.stdout.strip() or "running"
            root_log.info("%s  [%s]", path, status_line)
        elif "not supported in embedded mode" in combined:
            root_log.info("%s  [embedded mode — no server]", path)
        elif "not running" in combined or "no server" in combined:
            root_log.info("%s  [stopped]", path)
        else:
            detail = result.stderr.strip() or result.stdout.strip()
            root_log.info("%s  [unknown: %s]", path, detail)


def cmd_server_stop(path: Path | None) -> None:
    """Stop Dolt servers for one or all registered repos."""
    from bd_timew.project import load_repos_config

    config = load_repos_config()
    repos = config.get("repos", [])

    if path is not None:
        targets = [str(path.resolve())]
    else:
        targets = [r.get("path") for r in repos if r.get("path")]

    if not targets:
        root_log.info("No repos to stop (repos.yaml is empty or --path not found)")
        return

    for proj_path in targets:
        project_dir = Path(proj_path)
        if not project_dir.is_dir():
            root_log.warning("Skipping %s — directory not found", proj_path)
            continue

        result = _bd_dolt_in(project_dir, "stop")
        combined = (result.stdout + result.stderr).lower()

        if result.returncode == 0:
            root_log.info("%s  stopped (%s)", proj_path, result.stdout.strip() or "ok")
        elif "not supported in embedded mode" in combined:
            root_log.info("%s  [embedded mode — nothing to stop]", proj_path)
        elif "not running" in combined or "no server" in combined:
            root_log.info("%s  [server was not running]", proj_path)
        else:
            root_log.error(
                "%s  stop failed: %s",
                proj_path, result.stderr.strip() or result.stdout.strip(),
            )


def cmd_idle_stop(hours: float) -> None:
    """Stop Dolt servers idle longer than the threshold; ``hours=0`` reports only."""
    from bd_timew.project import load_repos_config

    config = load_repos_config()
    now = dt.datetime.now(dt.timezone.utc)
    threshold = dt.timedelta(hours=hours)

    for repo in config.get("repos", []):
        path = repo.get("path")
        if not path:
            continue
        project_dir = Path(path)
        if not project_dir.is_dir():
            continue

        # Only act on server-mode repos
        server_cfg = repo.get("server", {})
        if not server_cfg.get("enabled", False):
            continue

        last = _last_activity(path, project_dir)
        if last is None:
            root_log.info("%s  [no activity recorded — skipping]", path)
            continue

        idle_for = now - last
        idle_hours_str = f"{idle_for.total_seconds() / 3600:.1f}h"

        if hours == 0:
            root_log.info("%s  [idle %s]", path, idle_hours_str)
            continue

        if idle_for >= threshold:
            root_log.info("%s  [idle %s — stopping server]", path, idle_hours_str)
            result = subprocess.run(
                ["bd", "dolt", "stop"],
                cwd=project_dir,
                capture_output=True,
                text=True,
            )
            combined = (result.stdout + result.stderr).lower()
            if result.returncode == 0:
                root_log.info("%s  server stopped", path)
            elif "not running" in combined:
                root_log.info("%s  server was already stopped", path)
            else:
                root_log.error(
                    "%s  stop failed: %s",
                    path, result.stderr.strip() or result.stdout.strip(),
                )
        else:
            root_log.info("%s  [idle %s — within threshold]", path, idle_hours_str)
