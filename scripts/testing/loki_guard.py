#!/usr/bin/env python3
"""Guardrails for the local Loki Plex integration environment."""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
DEFAULT_EXPECTED_MACHINE_IDENTIFIER = "165cc0187d76937eb104da8d46437bf5443ec503"


@dataclass(frozen=True)
class LokiIdentity:
    machine_identifier: str
    version: str
    claimed: bool


def is_loopback_url(base_url: str) -> bool:
    parsed = urllib.parse.urlparse(base_url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and host in LOOPBACK_HOSTS


def build_plex_request(base_url: str, path: str, token: str | None = None) -> urllib.request.Request:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    headers = {"Accept": "application/json, application/xml"}
    if token:
        headers["X-Plex-Token"] = token
    return urllib.request.Request(url, headers=headers)


def parse_identity_xml(raw: bytes) -> LokiIdentity:
    raw = raw.strip()
    if raw.startswith(b"{"):
        data = json.loads(raw.decode("utf-8"))
        container = data.get("MediaContainer") or data
        return LokiIdentity(
            machine_identifier=str(container.get("machineIdentifier", "")),
            version=str(container.get("version", "")),
            claimed=bool(container.get("claimed")),
        )

    root = ET.fromstring(raw)
    return LokiIdentity(
        machine_identifier=root.attrib.get("machineIdentifier", ""),
        version=root.attrib.get("version", ""),
        claimed=root.attrib.get("claimed", "0") == "1",
    )


def fetch_identity(base_url: str, token: str | None = None, timeout: float = 5.0) -> LokiIdentity:
    request = build_plex_request(base_url, "/identity", token=token)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse_identity_xml(response.read())


def assert_loki_identity(
    identity: LokiIdentity,
    base_url: str,
    expected_machine_identifier: str | None = DEFAULT_EXPECTED_MACHINE_IDENTIFIER,
) -> LokiIdentity:
    if not is_loopback_url(base_url):
        raise RuntimeError(f"Refusing non-local Plex URL for Loki tests: {base_url}")
    if expected_machine_identifier and identity.machine_identifier != expected_machine_identifier:
        raise RuntimeError(
            f"Unexpected Plex machineIdentifier for Loki tests: {identity.machine_identifier!r}; expected {expected_machine_identifier!r}"
        )
    if not identity.claimed:
        raise RuntimeError("Loki Plex identity is unclaimed; refusing destructive integration tests")
    return identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("DOWNSHIFTARR_LOKI_PLEX_URL", "http://127.0.0.1:32400"))
    parser.add_argument(
        "--expected-machine-id", default=os.environ.get("DOWNSHIFTARR_LOKI_EXPECTED_MACHINE_ID", DEFAULT_EXPECTED_MACHINE_IDENTIFIER)
    )
    parser.add_argument("--token", default=os.environ.get("DOWNSHIFTARR_LOKI_PLEX_TOKEN"))
    args = parser.parse_args()

    identity = fetch_identity(args.base_url, token=args.token)
    assert_loki_identity(identity, args.base_url, args.expected_machine_id)
    print(f"Loki Plex identity verified: machineIdentifier={identity.machine_identifier} version={identity.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
