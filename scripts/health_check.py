#!/usr/bin/env python3
"""GARVIS health check -- validates all services are operational."""

import asyncio
import sys

import httpx

HEALTH_CHECKS = {
    "garvis_api": {
        "url": "http://localhost:8000/api/v1/status/health",
        "required": True,
    },
    "ollama": {
        "url": "http://localhost:11434/api/tags",
        "required": True,
    },
    "garvis_schemas": {
        "url": "http://localhost:8000/api/v1/governance/schemas",
        "required": True,
    },
    "garvis_analytics": {
        "url": "http://localhost:8000/api/v1/analytics/overview",
        "required": False,
    },
}


async def check_service(name: str, url: str) -> tuple[str, bool, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return name, True, f"HTTP {response.status_code}"
            return name, False, f"HTTP {response.status_code}"
    except Exception as exc:
        return name, False, str(exc)


async def main() -> int:
    print("GARVIS Health Check")
    print("=" * 50)

    results = await asyncio.gather(
        *[
            check_service(name, config["url"])
            for name, config in HEALTH_CHECKS.items()
        ]
    )

    all_pass = True
    for name, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        color = "\033[92m" if passed else "\033[91m"
        reset = "\033[0m"
        print(f"  [{color}{status}{reset}] {name:20s} {detail}")
        if not passed and HEALTH_CHECKS[name]["required"]:
            all_pass = False

    print()
    if all_pass:
        print("\033[92mAll required services healthy\033[0m")
        return 0
    else:
        print("\033[91mSome required services unhealthy\033[0m")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
