#!/usr/bin/env python3
"""search_cloudwatch_logs.py — read-only CloudWatch Logs across LINQ AWS accounts.

Six verbs, all read-only:

  groups    — list log groups (DescribeLogGroups)
  streams   — list streams in a group (DescribeLogStreams)
  search    — pattern search across a group (FilterLogEvents)
  insights  — Logs Insights query (StartQuery + GetQueryResults)
  tail      — live-follow a stream (NDJSON, polls GetLogEvents)
  get       — one-shot slice of a known stream (GetLogEvents)

Credential plumbing mirrors skills/verify-user-authorization/scripts/verify_authorization.py
exactly: named profile derived from `linq-<product>-<env>`, `--aws-profile` override,
`--i-understand-this-is-prod` prod guardrail, sts:GetCallerIdentity audit banner,
three-phase error split (ProfileNotFound / credential / downstream).

Always exits 0. Errors land in the JSON envelope on stdout so calling agents can
parse unconditionally. Diagnostic banner goes to stderr. The `tail` verb is the
sole exception: it emits NDJSON (one JSON object per line) so it can be piped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    import boto3
    from botocore.exceptions import (
        BotoCoreError,
        ClientError,
        NoCredentialsError,
        ProfileNotFound,
    )
except ImportError as exc:  # pragma: no cover
    print(json.dumps({
        "result": {"status": "ERROR", "verb": None, "reason": f"boto3 is required but not installed: {exc}"},
        "data": None,
    }))
    sys.exit(0)


# ---- envelope helpers --------------------------------------------------------

def _ok(verb: str, data: Any) -> dict:
    return {"result": {"status": "OK", "verb": verb, "reason": None}, "data": data}


def _err(verb: Optional[str], reason: str) -> dict:
    return {"result": {"status": "ERROR", "verb": verb, "reason": reason}, "data": None}


def _emit(envelope: dict) -> None:
    print(json.dumps(envelope, default=str))


def _emit_line(obj: dict) -> None:
    """NDJSON emitter for `tail` — one object per line, flushed."""
    print(json.dumps(obj, default=str), flush=True)


# ---- time-range parsing ------------------------------------------------------

_REL_RE = re.compile(r"^(\d+)(s|m|h|d)$")


def _parse_time(value: Optional[str], label: str) -> Optional[int]:
    """Parse a --since / --until value to epoch milliseconds.

    Accepts:
      - relative: "1h", "30m", "15s", "2d"
      - ISO 8601: "2026-05-07T14:00:00Z" or "2026-05-07T14:00:00+00:00"
      - epoch seconds (digits only): "1715091600"

    Returns None if value is None.
    """
    if value is None:
        return None
    m = _REL_RE.match(value)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = {
            "s": timedelta(seconds=n),
            "m": timedelta(minutes=n),
            "h": timedelta(hours=n),
            "d": timedelta(days=n),
        }[unit]
        return int((datetime.now(timezone.utc) - delta).timestamp() * 1000)
    if value.isdigit():
        return int(value) * 1000
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        pass
    raise ValueError(
        f"Could not parse {label} value {value!r}. "
        f"Use a relative duration ('1h', '30m', '15s', '2d'), an ISO-8601 timestamp, or epoch seconds."
    )


# ---- session construction ----------------------------------------------------

def _resolve_profile(args: argparse.Namespace) -> str:
    """Profile resolution order (first match wins):
       1. --aws-profile <name>     (explicit operator override; "" → ambient chain)
       2. LINQ_<PRODUCT>_AWS_PROFILE env var (workflow-level override)
       3. LINQ_AWS_USE_AMBIENT_CHAIN=1 → ambient chain
       4. derived → "linq-<product>-<env>"
    """
    if args.aws_profile is not None:
        return args.aws_profile  # may be "" → ambient chain
    product_env_var = f"LINQ_{args.product.upper().replace('-', '_')}_AWS_PROFILE"
    if os.environ.get(product_env_var):
        return os.environ[product_env_var]
    if os.environ.get("LINQ_AWS_USE_AMBIENT_CHAIN") == "1":
        return ""
    return f"linq-{args.product}-{args.environment}"


def _build_session_or_emit(args: argparse.Namespace, verb: str):
    """Phase 1+2: session + STS identity check. Emits ERROR envelope and returns
    None on failure; returns (session, ident, profile, region) on success."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    profile = _resolve_profile(args)

    try:
        session_kwargs = {"profile_name": profile} if profile else {}
        session = boto3.Session(**session_kwargs)
    except ProfileNotFound as exc:
        _emit(_err(verb, (
            f"AWS profile {profile!r} not found in ~/.aws/config. "
            f"Add a [profile {profile}] block (see SKILL.md 'AWS profiles' section) "
            f"or pass --aws-profile '' to use boto3's default credential chain. "
            f"Underlying: {exc}"
        )))
        return None

    try:
        sts = session.client("sts", region_name=region)
        ident = sts.get_caller_identity()
    except (NoCredentialsError, ClientError, BotoCoreError) as exc:
        _emit(_err(verb, (
            f"Could not resolve AWS identity (profile={profile or '<ambient>'!r}). "
            f"Run: aws sso login --sso-session linq. Underlying: {exc}"
        )))
        return None

    return session, ident, profile, region


def _audit_banner(verb: str, args: argparse.Namespace, profile: str, ident: dict, **extras: Any) -> None:
    """Per-invocation audit log to stderr. First thing operators see in their terminal."""
    parts = [
        f"env={args.environment}",
        f"product={args.product}",
        f"action={verb}",
        f"profile={profile or '<ambient>'}",
        f"account={ident['Account']}",
        f"arn={ident['Arn']}",
    ]
    for k, v in extras.items():
        parts.append(f"{k}={v}")
    print("[search-cloudwatch-logs] " + " ".join(parts), file=sys.stderr)


# ---- error helpers -----------------------------------------------------------

def _access_denied_message(operation: str, profile: str, account: str) -> str:
    return (
        f"AccessDenied calling {operation}. Your SSO profile {profile or '<ambient>'!r} "
        f"does not have CloudWatch Logs read permissions in account {account}. "
        f"Ask whoever owns your AWS access to grant logs:Filter*, logs:Get*, "
        f"logs:Describe*, and logs:StartQuery on this account (read-only)."
    )


def _handle_client_error(verb: str, exc: ClientError, operation: str, profile: str, account: str) -> None:
    code = exc.response.get("Error", {}).get("Code", "")
    if code in ("AccessDeniedException", "UnauthorizedOperation", "AccessDenied"):
        _emit(_err(verb, _access_denied_message(operation, profile, account)))
    elif code == "ResourceNotFoundException":
        _emit(_err(verb, f"Resource not found: {exc.response.get('Error', {}).get('Message', str(exc))}"))
    else:
        _emit(_err(verb, f"CloudWatch error from {operation}: {exc}"))


# ---- verb: groups ------------------------------------------------------------

def cmd_groups(args: argparse.Namespace) -> None:
    verb = "groups"
    built = _build_session_or_emit(args, verb)
    if not built:
        return
    session, ident, profile, region = built

    _audit_banner(verb, args, profile, ident,
                  name_prefix=args.name_prefix or "<none>",
                  limit=args.limit)

    try:
        logs = session.client("logs", region_name=region)
        kwargs: dict = {}
        if args.name_prefix:
            kwargs["logGroupNamePrefix"] = args.name_prefix

        groups: list = []
        paginator = logs.get_paginator("describe_log_groups")
        for page in paginator.paginate(**kwargs):
            for g in page.get("logGroups", []):
                groups.append({
                    "name": g["logGroupName"],
                    "arn": g.get("arn"),
                    "stored_bytes": g.get("storedBytes"),
                    "retention_days": g.get("retentionInDays"),
                    "creation_time": g.get("creationTime"),
                })
                if len(groups) >= args.limit:
                    break
            if len(groups) >= args.limit:
                break
    except ClientError as exc:
        _handle_client_error(verb, exc, "logs:DescribeLogGroups", profile, ident["Account"])
        return
    except BotoCoreError as exc:
        _emit(_err(verb, f"CloudWatch error: {exc}"))
        return

    _emit(_ok(verb, {"groups": groups, "count": len(groups)}))


# ---- verb: streams -----------------------------------------------------------

def cmd_streams(args: argparse.Namespace) -> None:
    verb = "streams"
    built = _build_session_or_emit(args, verb)
    if not built:
        return
    session, ident, profile, region = built

    _audit_banner(verb, args, profile, ident,
                  log_group=args.log_group,
                  name_prefix=args.name_prefix or "<none>",
                  limit=args.limit)

    try:
        logs = session.client("logs", region_name=region)
        kwargs: dict = {"logGroupName": args.log_group}
        if args.name_prefix:
            # The DescribeLogStreams API rejects orderBy when a prefix is supplied.
            kwargs["logStreamNamePrefix"] = args.name_prefix
        else:
            kwargs["orderBy"] = "LastEventTime"
            kwargs["descending"] = True

        streams: list = []
        paginator = logs.get_paginator("describe_log_streams")
        for page in paginator.paginate(**kwargs):
            for s in page.get("logStreams", []):
                streams.append({
                    "name": s["logStreamName"],
                    "first_event_time": s.get("firstEventTimestamp"),
                    "last_event_time": s.get("lastEventTimestamp"),
                    "stored_bytes": s.get("storedBytes"),
                })
                if len(streams) >= args.limit:
                    break
            if len(streams) >= args.limit:
                break
    except ClientError as exc:
        _handle_client_error(verb, exc, "logs:DescribeLogStreams", profile, ident["Account"])
        return
    except BotoCoreError as exc:
        _emit(_err(verb, f"CloudWatch error: {exc}"))
        return

    _emit(_ok(verb, {"streams": streams, "count": len(streams), "log_group": args.log_group}))


# ---- verb: search ------------------------------------------------------------

def cmd_search(args: argparse.Namespace) -> None:
    verb = "search"
    built = _build_session_or_emit(args, verb)
    if not built:
        return
    session, ident, profile, region = built

    try:
        start_ms = _parse_time(args.since, "--since")
        end_ms = _parse_time(args.until, "--until")
    except ValueError as exc:
        _emit(_err(verb, str(exc)))
        return

    _audit_banner(verb, args, profile, ident,
                  log_group=args.log_group,
                  pattern=repr(args.pattern) if args.pattern else "<none>",
                  since=args.since,
                  until=args.until or "now",
                  limit=args.limit)

    events: list = []
    try:
        logs = session.client("logs", region_name=region)
        kwargs: dict = {
            "logGroupName": args.log_group,
            "startTime": start_ms,
        }
        if end_ms is not None:
            kwargs["endTime"] = end_ms
        if args.pattern:
            kwargs["filterPattern"] = args.pattern
        if args.stream_prefix:
            kwargs["logStreamNamePrefix"] = args.stream_prefix

        paginator = logs.get_paginator("filter_log_events")
        for page in paginator.paginate(**kwargs):
            for e in page.get("events", []):
                events.append({
                    "timestamp": e["timestamp"],
                    "ingestion_time": e.get("ingestionTime"),
                    "stream": e.get("logStreamName"),
                    "message": e["message"],
                    "event_id": e.get("eventId"),
                })
                if len(events) >= args.limit:
                    break
            if len(events) >= args.limit:
                break
    except ClientError as exc:
        _handle_client_error(verb, exc, "logs:FilterLogEvents", profile, ident["Account"])
        return
    except BotoCoreError as exc:
        _emit(_err(verb, f"CloudWatch error: {exc}"))
        return

    if args.format == "text":
        for e in events:
            ts = datetime.fromtimestamp(e["timestamp"] / 1000, tz=timezone.utc).isoformat()
            print(f"{ts} [{e['stream']}] {e['message'].rstrip()}")
        print(f"[search-cloudwatch-logs] returned {len(events)} events", file=sys.stderr)
    else:
        _emit(_ok(verb, {
            "events": events,
            "count": len(events),
            "log_group": args.log_group,
            "pattern": args.pattern,
            "start_ms": start_ms,
            "end_ms": end_ms,
        }))


# ---- verb: insights ----------------------------------------------------------

def cmd_insights(args: argparse.Namespace) -> None:
    verb = "insights"
    built = _build_session_or_emit(args, verb)
    if not built:
        return
    session, ident, profile, region = built

    try:
        start_ms = _parse_time(args.since, "--since") or 0
        end_ms = _parse_time(args.until, "--until") or int(time.time() * 1000)
    except ValueError as exc:
        _emit(_err(verb, str(exc)))
        return

    _audit_banner(verb, args, profile, ident,
                  log_groups=",".join(args.log_group),
                  since=args.since,
                  until=args.until or "now",
                  query_timeout=args.query_timeout,
                  limit=args.limit)

    logs = session.client("logs", region_name=region)

    try:
        resp = logs.start_query(
            logGroupNames=args.log_group,
            startTime=start_ms // 1000,
            endTime=end_ms // 1000,
            queryString=args.query,
            limit=min(args.limit, 10000),
        )
        query_id = resp["queryId"]
    except ClientError as exc:
        _handle_client_error(verb, exc, "logs:StartQuery", profile, ident["Account"])
        return
    except BotoCoreError as exc:
        _emit(_err(verb, f"CloudWatch error starting Insights query: {exc}"))
        return

    deadline = time.time() + args.query_timeout
    res: dict = {}
    status = "Unknown"
    try:
        while True:
            res = logs.get_query_results(queryId=query_id)
            status = res.get("status", "Unknown")
            if status in ("Complete", "Failed", "Cancelled", "Timeout"):
                break
            if time.time() >= deadline:
                try:
                    logs.stop_query(queryId=query_id)
                except (ClientError, BotoCoreError):
                    pass
                _emit(_err(verb,
                           f"Insights query did not complete within {args.query_timeout}s. "
                           f"queryId={query_id}. Re-run with a longer --query-timeout or narrower --since."))
                return
            time.sleep(1)
    except ClientError as exc:
        _handle_client_error(verb, exc, "logs:GetQueryResults", profile, ident["Account"])
        return
    except BotoCoreError as exc:
        _emit(_err(verb, f"CloudWatch error polling Insights query: {exc}"))
        return

    if status != "Complete":
        _emit(_err(verb, f"Insights query ended with status {status!r}. queryId={query_id}"))
        return

    rows: list = []
    for fields in res.get("results", []):
        # @ptr is a CloudWatch internal pointer; suppress from output.
        rows.append({f["field"]: f["value"] for f in fields if f.get("field") != "@ptr"})

    stats = res.get("statistics", {}) or {}
    _emit(_ok(verb, {
        "query_id": query_id,
        "rows": rows,
        "count": len(rows),
        "statistics": {
            "records_matched": stats.get("recordsMatched"),
            "records_scanned": stats.get("recordsScanned"),
            "bytes_scanned": stats.get("bytesScanned"),
        },
        "log_groups": args.log_group,
        "query": args.query,
        "start_ms": start_ms,
        "end_ms": end_ms,
    }))


# ---- verb: tail --------------------------------------------------------------

def cmd_tail(args: argparse.Namespace) -> None:
    verb = "tail"
    built = _build_session_or_emit(args, verb)
    if not built:
        return
    session, ident, profile, region = built

    _audit_banner(verb, args, profile, ident,
                  log_group=args.log_group,
                  stream=args.stream,
                  duration=args.duration,
                  poll_interval=args.poll_interval)

    logs = session.client("logs", region_name=region)
    start_ms = int(time.time() * 1000)
    deadline = time.time() + args.duration
    next_token: Optional[str] = None

    try:
        while time.time() < deadline:
            kwargs: dict = {
                "logGroupName": args.log_group,
                "logStreamName": args.stream,
                "startFromHead": True,
            }
            if next_token:
                kwargs["nextToken"] = next_token
            else:
                kwargs["startTime"] = start_ms

            resp = logs.get_log_events(**kwargs)
            for e in resp.get("events", []):
                _emit_line({
                    "timestamp": e["timestamp"],
                    "ingestion_time": e.get("ingestionTime"),
                    "stream": args.stream,
                    "message": e["message"],
                })
            new_token = resp.get("nextForwardToken")
            if new_token == next_token:
                # No new events since last poll — sleep, then retry from same token.
                time.sleep(args.poll_interval)
            next_token = new_token
    except KeyboardInterrupt:
        print("[search-cloudwatch-logs] tail interrupted", file=sys.stderr)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("AccessDeniedException", "UnauthorizedOperation", "AccessDenied"):
            _emit_line(_err(verb, _access_denied_message("logs:GetLogEvents", profile, ident["Account"])))
        elif code == "ResourceNotFoundException":
            _emit_line(_err(verb, f"Log group or stream not found: {exc.response.get('Error', {}).get('Message', str(exc))}"))
        else:
            _emit_line(_err(verb, f"CloudWatch error: {exc}"))
    except BotoCoreError as exc:
        _emit_line(_err(verb, f"CloudWatch error: {exc}"))


# ---- verb: get ---------------------------------------------------------------

def cmd_get(args: argparse.Namespace) -> None:
    verb = "get"
    built = _build_session_or_emit(args, verb)
    if not built:
        return
    session, ident, profile, region = built

    try:
        start_ms = _parse_time(args.since, "--since")
        end_ms = _parse_time(args.until, "--until")
    except ValueError as exc:
        _emit(_err(verb, str(exc)))
        return

    _audit_banner(verb, args, profile, ident,
                  log_group=args.log_group,
                  stream=args.stream,
                  since=args.since,
                  until=args.until or "now",
                  limit=args.limit)

    events: list = []
    try:
        logs = session.client("logs", region_name=region)
        kwargs: dict = {
            "logGroupName": args.log_group,
            "logStreamName": args.stream,
            "startTime": start_ms,
            "startFromHead": True,
        }
        if end_ms is not None:
            kwargs["endTime"] = end_ms

        last_token: Optional[str] = None
        while True:
            resp = logs.get_log_events(**kwargs)
            for e in resp.get("events", []):
                events.append({
                    "timestamp": e["timestamp"],
                    "ingestion_time": e.get("ingestionTime"),
                    "stream": args.stream,
                    "message": e["message"],
                })
                if len(events) >= args.limit:
                    break
            if len(events) >= args.limit:
                break
            tok = resp.get("nextForwardToken")
            if not tok or tok == last_token:
                break
            last_token = tok
            kwargs.pop("startTime", None)
            kwargs.pop("startFromHead", None)
            kwargs["nextToken"] = tok
    except ClientError as exc:
        _handle_client_error(verb, exc, "logs:GetLogEvents", profile, ident["Account"])
        return
    except BotoCoreError as exc:
        _emit(_err(verb, f"CloudWatch error: {exc}"))
        return

    if args.format == "text":
        for e in events:
            ts = datetime.fromtimestamp(e["timestamp"] / 1000, tz=timezone.utc).isoformat()
            print(f"{ts} {e['message'].rstrip()}")
        print(f"[search-cloudwatch-logs] returned {len(events)} events", file=sys.stderr)
    else:
        _emit(_ok(verb, {
            "events": events,
            "count": len(events),
            "log_group": args.log_group,
            "stream": args.stream,
            "start_ms": start_ms,
            "end_ms": end_ms,
        }))


# ---- argparse wiring ---------------------------------------------------------

def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--product", required=True,
                   help="Product slug (e.g. erp, forms, compass). Drives profile linq-<product>-<env>.")
    p.add_argument("--environment", required=True, choices=["dev", "prod"])
    p.add_argument("--i-understand-this-is-prod", action="store_true",
                   help="Required when --environment=prod. Confirms explicit prod intent.")
    p.add_argument("--aws-profile", default=None,
                   help="Override the derived profile. Pass empty string for ambient credential chain.")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="search-cloudwatch-logs",
        description="Read-only CloudWatch Logs search across LINQ AWS accounts.",
    )
    sub = parser.add_subparsers(dest="verb", required=True)

    p = sub.add_parser("groups", help="List log groups (DescribeLogGroups).")
    _add_common(p)
    p.add_argument("--name-prefix", default=None, help="Filter to log groups whose name starts with this prefix.")
    p.add_argument("--limit", type=int, default=50, help="Cap result count (default 50).")
    p.set_defaults(func=cmd_groups)

    p = sub.add_parser("streams", help="List streams in a log group (DescribeLogStreams).")
    _add_common(p)
    p.add_argument("--log-group", required=True)
    p.add_argument("--name-prefix", default=None, help="Filter to streams whose name starts with this prefix.")
    p.add_argument("--limit", type=int, default=50, help="Cap result count (default 50).")
    p.set_defaults(func=cmd_streams)

    p = sub.add_parser("search", help="Pattern search across a log group (FilterLogEvents).")
    _add_common(p)
    p.add_argument("--log-group", required=True)
    p.add_argument("--pattern", default=None,
                   help="CloudWatch filter-pattern syntax (NOT regex). Omit to return all events in range.")
    p.add_argument("--stream-prefix", default=None, help="Restrict to streams matching this prefix.")
    p.add_argument("--since", required=True,
                   help="Start of window: '1h', '30m', '15s', '2d', ISO 8601, or epoch seconds.")
    p.add_argument("--until", default=None, help="End of window (default: now). Same formats as --since.")
    p.add_argument("--limit", type=int, default=1000, help="Cap event count (default 1000).")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("insights", help="Run a Logs Insights query (StartQuery + GetQueryResults).")
    _add_common(p)
    p.add_argument("--log-group", required=True, action="append",
                   help="Log group to query. Repeat the flag for multi-group queries.")
    p.add_argument("--query", required=True, help="CloudWatch Logs Insights query string.")
    p.add_argument("--since", required=True, help="Start of window: same formats as `search`.")
    p.add_argument("--until", default=None, help="End of window (default: now).")
    p.add_argument("--limit", type=int, default=1000, help="Row cap (default 1000, API max 10000).")
    p.add_argument("--query-timeout", type=int, default=60,
                   help="Seconds to wait for query completion before stopping it (default 60).")
    p.set_defaults(func=cmd_insights)

    p = sub.add_parser("tail", help="Live-follow a stream (NDJSON to stdout).")
    _add_common(p)
    p.add_argument("--log-group", required=True)
    p.add_argument("--stream", required=True)
    p.add_argument("--duration", type=int, default=300,
                   help="Max seconds to follow (default 300). Bounded so the script exits even unattended.")
    p.add_argument("--poll-interval", type=int, default=5,
                   help="Seconds between empty polls (default 5).")
    p.set_defaults(func=cmd_tail)

    p = sub.add_parser("get", help="One-shot slice of a known stream (GetLogEvents).")
    _add_common(p)
    p.add_argument("--log-group", required=True)
    p.add_argument("--stream", required=True)
    p.add_argument("--since", required=True, help="Start of window: same formats as `search`.")
    p.add_argument("--until", default=None, help="End of window (default: now).")
    p.add_argument("--limit", type=int, default=1000, help="Cap event count (default 1000).")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=cmd_get)

    args = parser.parse_args()

    # Prod guardrail (fires before any AWS call). Mirrors verify_authorization.py.
    if args.environment == "prod" and not args.i_understand_this_is_prod:
        _emit(_err(args.verb,
                   "Refusing prod run without --i-understand-this-is-prod. "
                   "Re-run with the flag if you intended to query production."))
        return 0

    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
