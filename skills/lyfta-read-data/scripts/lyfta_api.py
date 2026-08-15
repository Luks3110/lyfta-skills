#!/usr/bin/env python3
"""Read-only CLI for the personal Lyfta Developer API."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://my.lyfta.app"
USER_AGENT = "lyfta-read-data-skill/1.0"


class LyftaError(Exception):
    """Safe user-facing error with no request headers or credentials."""


def bounded_int(label: str, minimum: int, maximum: int | None = None):
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{label} must be an integer") from exc
        if number < minimum or (maximum is not None and number > maximum):
            suffix = f" and <= {maximum}" if maximum is not None else ""
            raise argparse.ArgumentTypeError(f"{label} must be >= {minimum}{suffix}")
        return number

    return parse


def api_key() -> str:
    key = os.environ.get("LYFTA_API_KEY", "").strip()
    if not key:
        raise LyftaError("LYFTA_API_KEY is not set")
    return key


def decode_body(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LyftaError("Lyfta returned a non-JSON response") from exc


def error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        for field in ("message", "error"):
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def ensure_api_success(payload: Any) -> Any:
    if isinstance(payload, dict) and payload.get("status") is False:
        raise LyftaError(error_message(payload, "Lyfta reported an unsuccessful request"))
    return payload


def get_json(path: str, params: dict[str, Any]) -> Any:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return ensure_api_success(decode_body(response.read()))
    except HTTPError as exc:
        try:
            payload = decode_body(exc.read())
        except LyftaError:
            payload = None
        message = error_message(payload, f"Lyfta API request failed with HTTP {exc.code}")
        if exc.code == 429:
            retry_after = exc.headers.get("Retry-After")
            if retry_after:
                message = f"{message} (retry after {retry_after} seconds)"
        raise LyftaError(message) from exc
    except URLError as exc:
        raise LyftaError(f"Could not reach Lyfta: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LyftaError("Lyfta request timed out") from exc


def load_mappings() -> dict[str, dict[str, str]]:
    mapping_path = Path(__file__).resolve().parent.parent / "references" / "id-mappings.json"
    try:
        with mapping_path.open(encoding="utf-8") as handle:
            mappings = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise LyftaError("Could not load the bundled Lyfta ID mappings") from exc
    return mappings


def parse_ids(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    value = raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = [raw]
    if not isinstance(value, list):
        value = [value]
    return [str(item) for item in value]


def decode_exercise(exercise: dict[str, Any], mappings: dict[str, dict[str, str]]) -> None:
    fields = {
        "equipment_id": ("equipment", "equipment"),
        "body_part_id": ("body_parts", "body_parts"),
        "Target_muscles_id": ("target_muscles", "muscles"),
        "Synergist_muscles_id": ("synergist_muscles", "muscles"),
    }
    for source, (destination, mapping_name) in fields.items():
        ids = parse_ids(exercise.get(source))
        table = mappings[mapping_name]
        exercise[destination] = [table.get(item, f"Unknown ID {item}") for item in ids]


def decode_exercise_ids(payload: Any) -> Any:
    result = copy.deepcopy(payload)
    if not isinstance(result, dict):
        return result

    candidates: Any = None
    if isinstance(result.get("exercises"), list):
        candidates = result["exercises"]
    data = result.get("data")
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        candidates = data["results"]
    if not isinstance(candidates, list):
        return result

    mappings = load_mappings()
    for candidate in candidates:
        if isinstance(candidate, dict):
            decode_exercise(candidate, mappings)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch personal Lyfta data. Reads the API key from LYFTA_API_KEY."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    workouts = subparsers.add_parser("workouts", help="Fetch detailed workouts")
    workouts.add_argument("--limit", type=bounded_int("limit", 1, 100), default=10)
    workouts.add_argument("--page", type=bounded_int("page", 1), default=1)

    summary = subparsers.add_parser("workout-summary", help="Fetch workout summaries")
    summary.add_argument("--limit", type=bounded_int("limit", 1, 1000), default=100)
    summary.add_argument("--page", type=bounded_int("page", 1), default=1)

    exercises = subparsers.add_parser("exercises", help="Fetch performed exercises")
    exercises.add_argument("--limit", type=bounded_int("limit", 1, 1000), default=100)
    exercises.add_argument("--page", type=bounded_int("page", 1), default=1)
    exercises.add_argument("--decode-ids", action="store_true")

    library = subparsers.add_parser("library", help="Search the exercise catalog")
    library.add_argument("--search", default="")
    library.add_argument("--limit", type=bounded_int("limit", 1, 100), default=10)
    library.add_argument("--offset", type=bounded_int("offset", 0), default=0)
    library.add_argument("--decode-ids", action="store_true")

    progress = subparsers.add_parser("progress", help="Fetch progress for one exercise")
    progress.add_argument("--exercise-id", type=bounded_int("exercise-id", 1), required=True)
    progress.add_argument("--duration", type=bounded_int("duration", 1), required=True)
    return parser


def run(args: argparse.Namespace) -> Any:
    if args.command == "workouts":
        return get_json("/api/v1/workouts", {"limit": args.limit, "page": args.page})
    if args.command == "workout-summary":
        return get_json("/api/v1/workouts/summary", {"limit": args.limit, "page": args.page})
    if args.command == "exercises":
        payload = get_json("/api/v1/exercises", {"limit": args.limit, "page": args.page})
        return decode_exercise_ids(payload) if args.decode_ids else payload
    if args.command == "library":
        payload = get_json(
            "/api/v1/exercises/library",
            {"search": args.search, "limit": args.limit, "offset": args.offset},
        )
        return decode_exercise_ids(payload) if args.decode_ids else payload
    return get_json(
        "/api/v1/exercises/progress",
        {"exercise_id": args.exercise_id, "duration": args.duration},
    )


def main() -> int:
    try:
        payload = run(build_parser().parse_args())
    except LyftaError as exc:
        print(json.dumps({"status": False, "message": str(exc)}), file=sys.stderr)
        return 1
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
