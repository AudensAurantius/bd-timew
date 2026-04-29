"""Argparse setup and dispatch."""

from __future__ import annotations

import argparse
from pathlib import Path

from bd_timew.util import HelpFormatter, setup_logger

__doc_summary__ = """\
bd-timew: Beads + Timewarrior bridge with project lifecycle management.

Resolves a Beads issue's labels to an external billing tuple
(client, case, svc) via a per-project sidecar (.beads/bd-timew.yaml),
then starts or stops a Timewarrior interval tagged accordingly.

Also provides project maintenance commands (cleanup, init-project,
config init), Dolt server management, and named bead-execution queues.

Resolution order for billing tuple (first match wins):
  1. Per-issue  case:<string>  label (escape hatch)
  2. First matching rule in  patterns:  (regex on space-joined label list)
  3.  default:  block in the sidecar
  4. None for any unset field — display layer renders as "(none)"
"""


def get_cli_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bd-timew",
        description=__doc_summary__,
        formatter_class=HelpFormatter,
    )
    parser.add_argument(
        "--loglevel", "-l",
        default="INFO",
        type=lambda v: v.strip().upper(),
        help="Logging verbosity (DEBUG, INFO, WARNING, ERROR).",
    )

    sub = parser.add_subparsers(
        dest="cmd", required=True,
        title="subcommands", metavar="<command>",
    )

    # -- start ---------------------------------------------------------------
    p_start = sub.add_parser(
        "start",
        help="Claim a Beads issue and start a Timewarrior interval.",
        description=(
            "Resolves the billing tuple for <issue-id>, claims it in Beads "
            "(if not already in_progress), and starts a tagged Timewarrior interval."
        ),
        formatter_class=HelpFormatter,
    )
    p_start.add_argument("issue_id", metavar="<issue-id>")

    # -- stop ----------------------------------------------------------------
    p_stop = sub.add_parser(
        "stop",
        help="Stop the current Timewarrior interval.",
        description=(
            "Stops the Timewarrior interval tagged with <issue-id> if given, "
            "otherwise stops all active intervals ('timew stop' with no args). "
            "Passing the issue ID explicitly is strongly recommended when multiple "
            "sessions may be tracking different beads concurrently."
        ),
        formatter_class=HelpFormatter,
    )
    p_stop.add_argument(
        "issue_id", metavar="<issue-id>", nargs="?", default=None,
        help="Stop only the interval tagged with this bead ID (recommended).",
    )

    # -- switch --------------------------------------------------------------
    p_switch = sub.add_parser(
        "switch",
        help="Stop current interval and start a new one on <issue-id>.",
        formatter_class=HelpFormatter,
    )
    p_switch.add_argument("issue_id", metavar="<issue-id>")
    p_switch.add_argument(
        "--from", dest="from_issue_id", metavar="<issue-id>", default=None,
        help="Stop only the interval tagged with this bead ID (recommended).",
    )

    # -- status --------------------------------------------------------------
    sub.add_parser(
        "status",
        help="Show the active interval's bead, billing tuple, and elapsed time.",
        formatter_class=HelpFormatter,
    )

    # -- resolve -------------------------------------------------------------
    p_resolve = sub.add_parser(
        "resolve",
        help="Print the resolved billing tuple without starting Timewarrior.",
        formatter_class=HelpFormatter,
    )
    p_resolve.add_argument("issue_id", metavar="<issue-id>")

    # -- cleanup -------------------------------------------------------------
    p_cleanup = sub.add_parser(
        "cleanup",
        help="Compact Dolt history and run GC; optionally commit first.",
        formatter_class=HelpFormatter,
    )
    p_cleanup.add_argument("--days", type=int, default=7,
                          help="Retain this many days of Dolt commit history.")
    p_cleanup.add_argument("--commit", action="store_true",
                          help="Run  bd dolt commit  before compacting.")
    p_cleanup.add_argument("--project-dir", type=Path, default=None,
                          help="Project root containing .beads/. Defaults to active workspace.")

    # -- init-project --------------------------------------------------------
    p_init = sub.add_parser(
        "init-project",
        help="Configure a Beads project and register it for auto-cleanup.",
        formatter_class=HelpFormatter,
    )
    p_init.add_argument("--path", type=Path, default=None)
    p_init.add_argument("--days", type=int, default=None)
    p_init.add_argument("--commit-cadence", type=str, default=None)
    p_init.add_argument("--statuses", type=str, default=None)
    p_init.add_argument("--hooks", action=argparse.BooleanOptionalAction, default=None)
    p_init.add_argument("--no-git-ops", action="store_true")
    p_init.add_argument("--install-systemd", action="store_true")
    p_init.add_argument("--check-interval", type=str, default="daily")
    p_init.add_argument("--idle-stop-hours", type=int, default=None)
    p_init.add_argument("--server", action=argparse.BooleanOptionalAction, default=None)
    p_init.add_argument("--dolt-user", type=str, default=None)
    p_init.add_argument("--pass-path", type=str, default=None)
    p_init.add_argument("--yes", "-y", action="store_true")

    # -- config init ---------------------------------------------------------
    p_config = sub.add_parser(
        "config",
        help="Manage bd-timew configuration (currently: 'config init' only).",
        formatter_class=HelpFormatter,
    )
    p_config_sub = p_config.add_subparsers(dest="config_action", required=True)
    p_config_init = p_config_sub.add_parser(
        "init",
        help="Scaffold a per-project .beads/bd-timew.yaml from the packaged template.",
        formatter_class=HelpFormatter,
    )
    p_config_init.add_argument(
        "--project-dir", type=Path, default=None,
        help="Project root containing .beads/. Defaults to active workspace.",
    )

    # -- idle-stop -----------------------------------------------------------
    p_idle = sub.add_parser(
        "idle-stop",
        help="Stop Dolt servers idle longer than a threshold.",
        formatter_class=HelpFormatter,
    )
    p_idle.add_argument("--hours", type=float, default=4.0)

    # -- run-service / servers / server-stop ---------------------------------
    sub.add_parser("run-service", help="[internal] systemd cleanup service entrypoint",
                   formatter_class=HelpFormatter)
    sub.add_parser("servers", help="List registered repos and Dolt server status.",
                   formatter_class=HelpFormatter)
    p_server_stop = sub.add_parser(
        "server-stop",
        help="Gracefully stop the Dolt server for one or all registered repos.",
        formatter_class=HelpFormatter,
    )
    p_server_stop.add_argument("--path", type=Path, default=None)

    # -- queue subcommands (flat top-level, no 'queue' prefix) ---------------
    _q_parent = argparse.ArgumentParser(add_help=False)
    _q_parent.add_argument(
        "--scope", metavar="<scope>", default=None,
        help="Queue scope name. Resolved: --scope flag → $BD_TIMEW_SCOPE → 'default'.",
    )
    _q_parent.add_argument(
        "--project-dir", type=Path, default=None,
        help="Project root containing .beads/. Defaults to active workspace.",
    )
    _q_parent.add_argument(
        "--titles", "-t", action="store_true", default=False,
        help="Show bead titles alongside IDs (fetches each bead from bd; slower).",
    )

    p_push = sub.add_parser("push", parents=[_q_parent],
                           help="Append one or more beads to the tail of a queue scope.",
                           formatter_class=HelpFormatter)
    p_push.add_argument("ids", nargs="+", metavar="<id>")

    p_unshift = sub.add_parser("unshift", parents=[_q_parent],
                              help="Prepend a bead to the head of a queue scope.",
                              formatter_class=HelpFormatter)
    p_unshift.add_argument("bead_id", metavar="<id>")

    sub.add_parser("pop", parents=[_q_parent],
                   help="Remove and print the head bead of a queue scope.",
                   formatter_class=HelpFormatter)
    sub.add_parser("peek", parents=[_q_parent],
                   help="Print the head bead of a queue scope without removing.",
                   formatter_class=HelpFormatter)
    sub.add_parser("queue", parents=[_q_parent],
                   help="List queue contents (all scopes, or one with --scope).",
                   formatter_class=HelpFormatter)
    p_remove = sub.add_parser("remove", parents=[_q_parent],
                             help="Remove one or more beads from a queue scope.",
                             formatter_class=HelpFormatter)
    p_remove.add_argument("ids", nargs="+", metavar="<id>")
    sub.add_parser("clear", parents=[_q_parent],
                   help="Empty a queue scope (--scope all clears every scope).",
                   formatter_class=HelpFormatter)

    return parser.parse_args()


def main() -> None:
    """Parse args and dispatch to the appropriate cmd_* function."""
    args = get_cli_arguments()
    setup_logger(
        args.loglevel,
        enable_file_handler=args.cmd in ("cleanup", "run-service", "idle-stop"),
    )

    # Late imports keep CLI startup snappy and avoid loading heavyweight modules
    # for unrelated subcommands.
    if args.cmd == "start":
        from bd_timew.timew import cmd_start
        cmd_start(args.issue_id)
    elif args.cmd == "stop":
        from bd_timew.timew import cmd_stop
        cmd_stop(args.issue_id)
    elif args.cmd == "switch":
        from bd_timew.timew import cmd_switch
        cmd_switch(args.issue_id, from_issue_id=args.from_issue_id)
    elif args.cmd == "status":
        from bd_timew.timew import cmd_status
        cmd_status()
    elif args.cmd == "resolve":
        from bd_timew.timew import cmd_start
        cmd_start(args.issue_id, dry_run=True)
    elif args.cmd == "cleanup":
        from bd_timew.project import cmd_cleanup
        cmd_cleanup(args.days, commit=args.commit, project_dir=args.project_dir)
    elif args.cmd == "init-project":
        from bd_timew.project import cmd_init_project
        cmd_init_project(
            path=args.path, days=args.days, commit_cadence=args.commit_cadence,
            statuses_arg=args.statuses, hooks_arg=args.hooks,
            no_git_ops=args.no_git_ops, install_systemd=args.install_systemd,
            check_interval=args.check_interval, idle_stop_hours=args.idle_stop_hours,
            server_mode=args.server, dolt_user=args.dolt_user,
            pass_path=args.pass_path, yes=args.yes,
        )
    elif args.cmd == "config":
        if args.config_action == "init":
            from bd_timew.project import cmd_config_init
            cmd_config_init(project_dir=args.project_dir)
    elif args.cmd == "idle-stop":
        from bd_timew.server import cmd_idle_stop
        cmd_idle_stop(args.hours)
    elif args.cmd == "run-service":
        from bd_timew.project import cmd_run_service
        cmd_run_service()
    elif args.cmd == "servers":
        from bd_timew.server import cmd_servers
        cmd_servers()
    elif args.cmd == "server-stop":
        from bd_timew.server import cmd_server_stop
        cmd_server_stop(args.path)
    elif args.cmd in ("push", "unshift", "pop", "peek", "queue", "remove", "clear"):
        from bd_timew.queue import cmd_queue
        if args.cmd == "push":
            ids = args.ids
        elif args.cmd == "unshift":
            ids = [args.bead_id]
        elif args.cmd == "remove":
            ids = args.ids
        else:
            ids = None
        cmd_queue(
            "list" if args.cmd == "queue" else args.cmd,
            ids=ids, scope_arg=args.scope,
            project_dir=args.project_dir, titles=args.titles,
        )
