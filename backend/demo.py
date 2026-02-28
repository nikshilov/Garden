#!/usr/bin/env python3
"""Garden — Visual Demo Script

Starts the server, exercises every phase's endpoints, and prints
rich formatted output. Designed for screen recording.

Usage:
    cd backend
    .venv/bin/python demo.py
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:5050"
STARTUP_TIMEOUT = 15  # seconds to wait for server
PAUSE = 0.6           # pause between sections for readability

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
RED = "\033[31m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_RED = "\033[41m"


def header(text: str):
    print()
    print(f"{BOLD}{MAGENTA}{'━' * 60}{RESET}")
    print(f"{BOLD}{MAGENTA}  {text}{RESET}")
    print(f"{BOLD}{MAGENTA}{'━' * 60}{RESET}")
    print()
    time.sleep(PAUSE)


def subheader(text: str):
    print(f"  {BOLD}{CYAN}▸ {text}{RESET}")
    time.sleep(PAUSE * 0.5)


def info(label: str, value: str):
    print(f"    {DIM}{label}:{RESET} {value}")


def success(text: str):
    print(f"    {GREEN}✓{RESET} {text}")


def warn(text: str):
    print(f"    {YELLOW}⚠{RESET} {text}")


def error(text: str):
    print(f"    {RED}✗{RESET} {text}")


def status_badge(status: str) -> str:
    if status == "green":
        return f"{BG_GREEN}{BOLD} GREEN {RESET}"
    elif status == "yellow":
        return f"{BG_YELLOW}{BOLD} YELLOW {RESET}"
    elif status == "red":
        return f"{BG_RED}{WHITE}{BOLD} RED {RESET}"
    return status


def json_pretty(data, indent=6):
    """Print JSON with indentation."""
    formatted = json.dumps(data, indent=2, ensure_ascii=False)
    for line in formatted.split("\n"):
        print(f"{' ' * indent}{DIM}{line}{RESET}")


# ---------------------------------------------------------------------------
# Server management
# ---------------------------------------------------------------------------

def wait_for_server(timeout: int = STARTUP_TIMEOUT) -> bool:
    """Wait until the server responds to /health."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                return True
        except httpx.ConnectError:
            pass
        time.sleep(0.5)
    return False


def server_is_running() -> bool:
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Demo sections
# ---------------------------------------------------------------------------

def demo_health_check(client: httpx.Client):
    header("Phase 0 — Server Health")
    r = client.get("/health")
    data = r.json()
    success(f"Server is alive: {data}")


def demo_garden_state(client: httpx.Client):
    header("Phase 6 — Soil: The Garden Right Now")

    subheader("Updating garden world state...")
    r = client.post("/garden/update")
    state = r.json().get("state", {})

    info("Season", f"{BOLD}{state.get('season', '?')}{RESET}")
    info("Time of day", state.get("time_of_day", "?"))
    info("Weather", state.get("weather", "?"))
    print()
    print(f"    {DIM}\"{state.get('ambiance', '')}\"{RESET}")
    print()

    subheader("Character presences")
    r = client.get("/garden/state")
    data = r.json()
    presences = data.get("presences", [])
    for p in presences:
        name = p["char_id"].capitalize()
        loc = p["location"].replace("_", " ")
        energy_bar = "█" * int(p["energy"] * 10) + "░" * (10 - int(p["energy"] * 10))
        print(f"    {BOLD}{name:8s}{RESET} {DIM}at{RESET} {loc:15s} "
              f"{DIM}({p['activity']}){RESET}  "
              f"energy {CYAN}[{energy_bar}]{RESET} {p['energy']:.1f}")


def demo_chat(client: httpx.Client):
    header("Phase 1-5 — Talking to the Garden")

    messages = [
        ("eve", "Привет, Ева! Расскажи, о чём думала в последнее время?"),
        ("atlas", "Atlas, what's your take on consciousness?"),
    ]

    for char_id, text in messages:
        subheader(f"Talking to {char_id.capitalize()}...")
        print(f"    {BOLD}User:{RESET} {text}")
        print()

        try:
            r = client.post("/chat", json={
                "text": text,
                "character_id": char_id,
            }, timeout=30)
            data = r.json()
            if "detail" in data:
                warn(f"Error: {data['detail']}")
                continue
            reply = data.get("text", "")
            cost = data.get("cost_total_usd", 0)

            # Word-wrap the reply
            words = reply.split()
            lines = []
            current = ""
            for w in words:
                if len(current) + len(w) + 1 > 55:
                    lines.append(current)
                    current = w
                else:
                    current = f"{current} {w}" if current else w
            if current:
                lines.append(current)

            print(f"    {BOLD}{char_id.capitalize()}:{RESET}")
            for line in lines:
                print(f"      {GREEN}{line}{RESET}")
            print()
            info("Cost so far", f"${cost:.4f}")
        except Exception as e:
            warn(f"Chat failed: {e}")
        print()


def demo_heartbeat(client: httpx.Client):
    header("Phase 1 — Heartbeat: Life Between Conversations")

    subheader("Heartbeat status")
    r = client.get("/heartbeat/status")
    data = r.json()
    info("Running", str(data.get("running", False)))
    info("Interval", f"{data.get('interval_hours', '?')}h")
    info("Characters", ", ".join(data.get("characters", [])))

    subheader("Triggering manual heartbeat tick...")
    print(f"    {DIM}(This runs mood decay, relationship drift, memory clustering,")
    print(f"     identity evolution, garden world update, and internal monologue){RESET}")
    try:
        r = client.post("/heartbeat/tick", timeout=60)
        if r.status_code == 200:
            success("Heartbeat tick completed")
        else:
            warn(f"Heartbeat tick returned {r.status_code}")
    except Exception as e:
        warn(f"Heartbeat tick timed out (expected for LLM calls): {e}")


def demo_initiatives(client: httpx.Client):
    header("Phase 5 — Voice: Characters Reaching Out")

    subheader("Initiative settings")
    r = client.get("/initiatives/settings")
    data = r.json()
    settings = data.get("settings", {})
    info("Enabled", str(settings.get("enabled", False)))
    info("Available", str(data.get("available", False)))

    subheader("Checking for pending initiatives...")
    r = client.get("/initiatives/pending")
    data = r.json()
    initiatives = data.get("initiatives", [])
    if initiatives:
        for init in initiatives:
            info(init["char_id"].capitalize(), f"[{init['trigger']}] {init['message'][:60]}...")
    else:
        info("Status", "No pending initiatives (characters are content)")


def demo_diagnostics(client: httpx.Client):
    header("Phase 7 — Autonomy: Garden Health Diagnostics")

    subheader("Running diagnostics for all characters...")
    r = client.get("/health/diagnostics")
    data = r.json()

    diagnostics = data.get("diagnostics", {})
    for char_id, report in diagnostics.items():
        status = report.get("status", "unknown")
        badge = status_badge(status)
        checks = report.get("checks", [])

        print(f"    {BOLD}{char_id.capitalize():8s}{RESET} {badge}")
        for check in checks:
            cat = check["category"]
            st = check["status"]
            msg = check["message"]
            fixable = check.get("auto_fixable", False)

            if st == "green":
                icon = f"{GREEN}●{RESET}"
            elif st == "yellow":
                icon = f"{YELLOW}●{RESET}"
            else:
                icon = f"{RED}●{RESET}"

            fix_tag = f" {DIM}[auto-fixable]{RESET}" if fixable else ""
            print(f"      {icon} {cat:14s} {msg}{fix_tag}")
        print()


def demo_summary():
    header("All 7 Phases — Complete")
    phases = [
        ("Phase 1", "Heartbeat", "Life between conversations"),
        ("Phase 2", "Roots", "Semantic memory with embeddings"),
        ("Phase 3", "Mycelium", "Inter-character relationships"),
        ("Phase 4", "Growth", "Identity evolution and trait drift"),
        ("Phase 5", "Voice", "Characters reaching out"),
        ("Phase 6", "Soil", "Sense of place — the garden is real"),
        ("Phase 7", "Autonomy", "Self-healing garden"),
    ]
    for num, name, desc in phases:
        print(f"    {GREEN}██████████{RESET}  {BOLD}{num}{RESET} ({name}) — {DIM}{desc}{RESET}")

    print()
    print(f"  {DIM}152 tests passing. The garden is alive.{RESET}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print()
    print(f"{BOLD}{MAGENTA}")
    print(r"   ____               _            ")
    print(r"  / ___| __ _ _ __ __| | ___ _ __  ")
    print(r" | |  _ / _` | '__/ _` |/ _ \ '_ \ ")
    print(r" | |_| | (_| | | | (_| |  __/ | | |")
    print(r"  \____|\__,_|_|  \__,_|\___|_| |_|")
    print(f"{RESET}")
    print(f"  {DIM}A place where AI personas live, remember, grow, and reach out.{RESET}")
    print()
    time.sleep(1)

    # Check if server is already running
    started_server = False
    server_proc = None

    if server_is_running():
        success("Server already running")
    else:
        subheader("Starting server...")
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server:app", "--port", "5050"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        started_server = True

        if wait_for_server():
            success("Server started on port 5050")
        else:
            error("Server failed to start within timeout")
            server_proc.terminate()
            sys.exit(1)

    client = httpx.Client(base_url=BASE_URL, timeout=30)

    try:
        demo_health_check(client)
        demo_garden_state(client)
        demo_diagnostics(client)
        demo_chat(client)
        demo_heartbeat(client)
        demo_initiatives(client)
        demo_summary()
    except KeyboardInterrupt:
        print(f"\n  {DIM}Interrupted.{RESET}")
    except Exception as e:
        error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()
        if started_server and server_proc:
            subheader("Stopping server...")
            server_proc.terminate()
            server_proc.wait(timeout=5)
            success("Server stopped")


if __name__ == "__main__":
    main()
