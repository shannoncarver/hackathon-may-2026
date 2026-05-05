#!/usr/bin/env python3
"""verify_authorization.py

Local Python port of LINQ-ERP-v4's HarmonyAuthAuthorize C# endpoint.

Reads erp_users (twice) and erp_tenants (once) from DynamoDB and emits a JSON
envelope describing whether the (user, tenant) pair is authorized.

DECISION SEMANTICS: mirrors the C# exactly, including two surprising behaviors
that look like bugs but are part of the spec for this POC:

  B1. A superuser row that exists but is NOT 'active' prevents the user-in-tenant
      row from ever being consulted.
  B2. A MISSING tenant row does NOT override authorization. Only an INACTIVE
      tenant row triggers the override.

If/when the user asks for the "fixed" semantics, swap the decision block.

Always exits 0. AWS / network / input errors are surfaced inside the envelope as
status == "ERROR" so the calling agent can parse stdout unconditionally.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from decimal import Decimal
from typing import Any

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
except ImportError as exc:  # pragma: no cover
    print(
        json.dumps(
            {
                "authorization": {
                    "authorized": False,
                    "status": "ERROR",
                    "reason": f"boto3 is required but not installed: {exc}",
                },
                "user": None,
                "tenant": None,
                "matched_user_record": None,
            }
        )
    )
    sys.exit(0)


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _decimal_default(o: Any) -> Any:
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    if isinstance(o, set):
        return sorted(o)
    if isinstance(o, bytes):
        return o.decode("utf-8", errors="replace")
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


def _envelope(authorized, status, reason, user, tenant, matched):
    return {
        "authorization": {"authorized": authorized, "status": status, "reason": reason},
        "user": user,
        "tenant": tenant,
        "matched_user_record": matched,
    }


# Module-level toggle set by main() from the --include-sensitive CLI flag.
# When False (default), any attribute key ending in "_id" is replaced with
# "<redacted>" in the authorized envelope. Pass --include-sensitive to opt out.
_INCLUDE_SENSITIVE = False


def _redact_ids(record):
    if record is None:
        return None
    return {
        k: ("<redacted>" if isinstance(k, str) and k.lower().endswith("_id") else v)
        for k, v in record.items()
    }


def _emit(env):
    # Null user/tenant on any unauthorized outcome — diagnostic detail lives in
    # `reason` and `matched_user_record`. Avoids leaking partial records.
    if env["authorization"]["authorized"] is False:
        env = {**env, "user": None, "tenant": None}
    elif not _INCLUDE_SENSITIVE:
        env = {
            **env,
            "user": _redact_ids(env.get("user")),
            "tenant": _redact_ids(env.get("tenant")),
        }
    print(json.dumps(env, default=_decimal_default))


def _is_active(record):
    if not record:
        return False
    status = record.get("status")
    return isinstance(status, str) and status.strip().lower() == "active"


def _get_item(table, key, label):
    response = table.get_item(Key=key, ConsistentRead=False)
    item = response.get("Item")
    if item is None:
        print(f"[verify_authorization] {label}: no item for {key}", file=sys.stderr)
        return None
    print(f"[verify_authorization] {label}: hit", file=sys.stderr)
    return item


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ERP user authorization (dev only).")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--environment", required=True, choices=["dev"])
    parser.add_argument(
        "--include-sensitive",
        action="store_true",
        help="Return raw values for *_id attributes; default redacts them.",
    )
    args = parser.parse_args()

    global _INCLUDE_SENSITIVE
    _INCLUDE_SENSITIVE = bool(args.include_sensitive)

    user_email = args.user_email.strip().lower()
    tenant_id = args.tenant_id.strip().lower()

    if not EMAIL_RE.match(user_email):
        _emit(_envelope(False, "ERROR", f"Invalid email: {args.user_email!r}", None, None, None))
        return 0

    region = os.environ.get("AWS_REGION", "us-east-1")
    users_table_name = os.environ.get("ERP_USERS_TABLE_NAME", "dev_erp_users")
    tenants_table_name = os.environ.get("ERP_TENANTS_TABLE_NAME", "dev_erp_tenants")

    print(
        f"[verify_authorization] region={region} users={users_table_name} "
        f"tenants={tenants_table_name} email={user_email} tenant={tenant_id}",
        file=sys.stderr,
    )

    try:
        ddb = boto3.resource("dynamodb", region_name=region)
        users_table = ddb.Table(users_table_name)
        tenants_table = ddb.Table(tenants_table_name)

        # Three sequential GetItems. C# uses Task.WhenAll for parallel execution;
        # at three calls of ~5–20ms each, sequential is well under any latency
        # budget. To parallelize: ThreadPoolExecutor with 3 separate Table
        # instances (boto3 clients are not thread-safe).
        user_in_tenant = _get_item(
            users_table,
            {"PK": f"#USRID#{user_email}", "SK": f"#TEN#{tenant_id}"},
            label="user_in_tenant",
        )
        superuser = _get_item(
            users_table,
            {"PK": f"#USRID#{user_email}", "SK": "#TEN#superuser"},
            label="superuser",
        )
        tenant = _get_item(
            tenants_table,
            {"PK": f"#TEN#{tenant_id}", "SK": "#TEN#"},
            label="tenant",
        )
    except NoCredentialsError as exc:
        _emit(_envelope(False, "ERROR", f"AWS credentials not found: {exc}", None, None, None))
        return 0
    except (ClientError, BotoCoreError) as exc:
        _emit(_envelope(False, "ERROR", f"DynamoDB error: {exc}", None, None, None))
        return 0

    # ---- Decision logic — mirrors C# exactly --------------------------------
    # User-side decision (lines 157–193 of HarmonyAuthAuthorize.cs):
    #   if superuser row exists:
    #       authorized iff status == "active"   (B1: user-in-tenant NOT consulted)
    #   elif user-in-tenant row exists:
    #       authorized iff status == "active"
    #   else:
    #       not authorized
    if superuser is not None:
        matched = "superuser"
        user_record = superuser
        if _is_active(superuser):
            user_authorized = True
            user_status_kind = "AUTHORIZED_SUPERUSER"
        else:
            user_authorized = False
            user_status_kind = "SUPERUSER_DISABLED"
    elif user_in_tenant is not None:
        matched = "in_tenant"
        user_record = user_in_tenant
        if _is_active(user_in_tenant):
            user_authorized = True
            user_status_kind = "AUTHORIZED_USER"
        else:
            user_authorized = False
            user_status_kind = "USER_DISABLED"
    else:
        matched = None
        user_record = None
        user_authorized = False
        user_status_kind = "USER_NOT_FOUND"

    # Tenant-side override (lines 197–219):
    #   if tenant row exists and active: capture db_id, conn_str_id (no auth change)
    #   elif tenant row exists and inactive: isAuthorized = false (override)
    #   else (tenant row missing): no override (B2)
    if tenant is None:
        # B2: tenant missing does not invalidate user-side decision.
        if user_authorized:
            _emit(_envelope(
                True,
                "TENANT_MISSING_BUT_USER_AUTHORIZED",
                "Tenant row absent; C# logic still authorizes when user/superuser is active.",
                user_record,
                None,
                matched,
            ))
        else:
            _emit(_envelope(
                False,
                "TENANT_MISSING_USER_NOT_AUTHORIZED",
                f"Tenant row absent and user-side outcome is {user_status_kind}.",
                user_record,
                None,
                matched,
            ))
        return 0

    if not _is_active(tenant):
        _emit(_envelope(
            False,
            "TENANT_DISABLED",
            f"Tenant exists but status is {tenant.get('status')!r}.",
            user_record,
            tenant,
            matched,
        ))
        return 0

    # Tenant is active — surface the user-side outcome.
    if user_authorized:
        _emit(_envelope(True, user_status_kind, None, user_record, tenant, matched))
        return 0

    reason_map = {
        "USER_NOT_FOUND": (
            f"No user row at PK=#USRID#{user_email} for SK=#TEN#{tenant_id} or SK=#TEN#superuser."
        ),
        "USER_DISABLED": f"User row found but status is {(user_in_tenant or {}).get('status')!r}.",
        "SUPERUSER_DISABLED": (
            f"Superuser row found but status is {(superuser or {}).get('status')!r}; "
            "C# does not consult the user-in-tenant row when a superuser row exists."
        ),
    }
    _emit(_envelope(
        False,
        user_status_kind,
        reason_map.get(user_status_kind, "Unauthorized."),
        user_record,
        tenant,
        matched,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
