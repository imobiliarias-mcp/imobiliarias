"""Point the Dokploy compose service at a new image tag, then deploy it and wait for the result.

Reads DOKPLOY_BASE_URL, DOKPLOY_API_KEY, DOKPLOY_COMPOSE_ID and NEW_TAG from the environment.
The API key is only sent in the x-api-key header and is never printed.
"""

import json
import os
import sys
import time
import urllib.request

POLL_SECONDS = 15
POLL_ATTEMPTS = 60


def call(method: str, path: str, body: dict | None = None) -> dict:
    """Send one Dokploy API request and return its decoded JSON body."""
    base = os.environ["DOKPLOY_BASE_URL"].rstrip("/")
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{base}/api/{path}", data=data, method=method)
    request.add_header("x-api-key", os.environ["DOKPLOY_API_KEY"])
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read() or b"{}")


def merged_env(current: str, new_tag: str) -> str:
    """Replace IMAGE_TAG and keep every other variable of the service unchanged."""
    lines = [line for line in current.splitlines() if line and not line.startswith("IMAGE_TAG=")]
    return "\n".join([f"IMAGE_TAG={new_tag}", *lines])


def main() -> int:
    compose_id = os.environ["DOKPLOY_COMPOSE_ID"]
    new_tag = os.environ["NEW_TAG"]
    service = call("GET", f"compose.one?composeId={compose_id}")
    env = merged_env(service.get("env") or "", new_tag)
    call("POST", "compose.update", {"composeId": compose_id, "env": env, "pullImages": True})
    call("POST", "compose.deploy", {"composeId": compose_id})
    for _ in range(POLL_ATTEMPTS):
        time.sleep(POLL_SECONDS)
        status = call("GET", f"compose.one?composeId={compose_id}").get("composeStatus")
        print(f"composeStatus={status}", flush=True)
        if status == "done":
            print(f"deployed IMAGE_TAG={new_tag}")
            return 0
        if status == "error":
            print("Dokploy reported a failed deployment", file=sys.stderr)
            return 1
    print("timed out waiting for Dokploy deployment", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
