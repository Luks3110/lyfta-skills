#!/usr/bin/env python3
"""Validate and create personal Lyfta collections and workout templates."""

from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://my.lyfta.app"
USER_AGENT = "lyfta-build-programs-skill/1.0"
SET_STRING_FIELDS = {
    "reps",
    "from_reps",
    "to_reps",
    "weight",
    "rir",
    "duration",
    "distance",
}


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


def request_json(method: str, path: str, params: dict[str, Any] | None = None, payload: Any = None) -> Any:
    query = urlencode({key: value for key, value in (params or {}).items() if value is not None})
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key()}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return ensure_api_success(decode_body(response.read()))
    except HTTPError as exc:
        try:
            response_payload = decode_body(exc.read())
        except LyftaError:
            response_payload = None
        message = error_message(
            response_payload, f"Lyfta API request failed with HTTP {exc.code}"
        )
        if exc.code == 429:
            retry_after = exc.headers.get("Retry-After")
            if retry_after:
                message = f"{message} (retry after {retry_after} seconds)"
        if method == "POST" and (exc.code == 408 or exc.code >= 500):
            message = f"{message}. Do not retry automatically."
        raise LyftaError(message) from exc
    except URLError as exc:
        if method == "POST":
            raise LyftaError(
                f"Lyfta write outcome is unknown: {exc.reason}. Do not retry automatically."
            ) from exc
        raise LyftaError(f"Could not reach Lyfta: {exc.reason}") from exc
    except TimeoutError as exc:
        if method == "POST":
            raise LyftaError(
                "Lyfta write timed out and its outcome is unknown. Do not retry automatically."
            ) from exc
        raise LyftaError("Lyfta request timed out") from exc


def load_payload(source: str) -> Any:
    try:
        if source == "-":
            return json.load(sys.stdin)
        with Path(source).open(encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise LyftaError(f"Could not read input JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LyftaError(f"Invalid JSON input: {exc.msg}") from exc


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LyftaError(f"{label} must be an object")
    return value


def reject_unknown_fields(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise LyftaError(f"Unsupported {label} field(s): {', '.join(unknown)}")


def non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LyftaError(f"{label} must be a non-empty string")
    return value.strip()


def integer(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise LyftaError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise LyftaError(f"{label} must be an integer") from exc
    if parsed < minimum:
        raise LyftaError(f"{label} must be >= {minimum}")
    return parsed


def validate_base64(value: str, label: str) -> None:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise LyftaError(f"{label} must contain valid base64 data") from exc
    if not decoded:
        raise LyftaError(f"{label} must not be empty")


def validate_collection(raw: Any) -> dict[str, Any]:
    payload = copy.deepcopy(require_object(raw, "payload"))
    if "client_id" in payload or "clientId" in payload:
        raise LyftaError("Coach/client operations are outside this skill")
    reject_unknown_fields(payload, {"collection"}, "top-level")
    collection = require_object(payload.get("collection"), "collection")
    reject_unknown_fields(collection, {"title", "description", "goal", "image"}, "collection")
    collection["title"] = non_empty_string(collection.get("title"), "collection.title")
    for field in ("description", "goal"):
        if field in collection and not isinstance(collection[field], str):
            raise LyftaError(f"collection.{field} must be a string")
    if "image" in collection:
        image = non_empty_string(collection["image"], "collection.image")
        if image.startswith(("http://", "https://", "data:")):
            raise LyftaError("collection.image must be raw base64, not a URL or data URI")
        validate_base64(image, "collection.image")
        collection["image"] = image
    return payload


def normalize_set(raw: Any, label: str) -> dict[str, Any]:
    item = copy.deepcopy(require_object(raw, label))
    reject_unknown_fields(item, SET_STRING_FIELDS | {"set_type_id"}, label)
    if "set_type_id" in item:
        item["set_type_id"] = integer(item["set_type_id"], f"{label}.set_type_id")
    for field in SET_STRING_FIELDS:
        if field not in item:
            continue
        value = item[field]
        if isinstance(value, bool) or value is None or not isinstance(value, (str, int, float)):
            raise LyftaError(f"{label}.{field} must be a string or number")
        item[field] = str(value)
    return item


def normalize_exercise(raw: Any, index: int) -> dict[str, Any]:
    label = f"workout.exercises[{index}]"
    exercise = copy.deepcopy(require_object(raw, label))
    allowed = {
        "exercise_id",
        "excercise_name",
        "exercise_type",
        "exercise_image",
        "exercise_note",
        "exercise_rest_time",
        "exercise_superset_id",
        "is_rep_range_active",
        "sets",
    }
    reject_unknown_fields(exercise, allowed, label)
    exercise["exercise_id"] = integer(exercise.get("exercise_id"), f"{label}.exercise_id", 1)
    for field in ("excercise_name", "exercise_type", "exercise_image"):
        exercise[field] = non_empty_string(exercise.get(field), f"{label}.{field}")
    if not exercise["exercise_image"].startswith("https://"):
        raise LyftaError(f"{label}.exercise_image must be the HTTPS catalog image URL")
    if "exercise_note" in exercise and not isinstance(exercise["exercise_note"], str):
        raise LyftaError(f"{label}.exercise_note must be a string")
    for field in ("exercise_rest_time", "exercise_superset_id"):
        if field in exercise:
            exercise[field] = integer(exercise[field], f"{label}.{field}")
    if "is_rep_range_active" in exercise and not isinstance(
        exercise["is_rep_range_active"], bool
    ):
        raise LyftaError(f"{label}.is_rep_range_active must be boolean")
    sets = exercise.get("sets", [])
    if not isinstance(sets, list):
        raise LyftaError(f"{label}.sets must be an array")
    exercise["sets"] = [normalize_set(item, f"{label}.sets[{i}]") for i, item in enumerate(sets)]
    if exercise.get("is_rep_range_active"):
        for i, item in enumerate(exercise["sets"]):
            if not item.get("from_reps") or not item.get("to_reps"):
                raise LyftaError(
                    f"{label}.sets[{i}] requires from_reps and to_reps when rep range is active"
                )
    if exercise["exercise_type"] == "duration":
        for i, item in enumerate(exercise["sets"]):
            if not item.get("duration"):
                raise LyftaError(f"{label}.sets[{i}] requires duration for a duration exercise")
    return exercise


def validate_template(raw: Any) -> dict[str, Any]:
    payload = copy.deepcopy(require_object(raw, "payload"))
    if "client_id" in payload or "clientId" in payload:
        raise LyftaError("Coach/client operations are outside this skill")
    reject_unknown_fields(payload, {"collectionId", "workout"}, "top-level")
    payload["collectionId"] = integer(payload.get("collectionId"), "collectionId", 1)
    workout = require_object(payload.get("workout"), "workout")
    reject_unknown_fields(
        workout, {"title", "description", "note", "color", "picture", "exercises"}, "workout"
    )
    for field in ("title", "description", "note"):
        if field in workout and not isinstance(workout[field], str):
            raise LyftaError(f"workout.{field} must be a string")
    if "color" in workout:
        color = non_empty_string(workout["color"], "workout.color")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise LyftaError("workout.color must be a six-digit hex color")
        workout["color"] = color
    if "picture" in workout and workout["picture"]:
        picture = non_empty_string(workout["picture"], "workout.picture")
        if picture.startswith("data:image/") and ";base64," in picture:
            validate_base64(picture.split(",", 1)[1], "workout.picture")
        elif not picture.startswith("https://"):
            raise LyftaError("workout.picture must be a base64 image data URI or HTTPS URL")
        workout["picture"] = picture
    exercises = workout.get("exercises", [])
    if not isinstance(exercises, list):
        raise LyftaError("workout.exercises must be an array")
    workout["exercises"] = [normalize_exercise(item, i) for i, item in enumerate(exercises)]
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare personal Lyfta programs. Writes require the explicit --execute flag."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search-exercises", help="Search the Lyfta exercise catalog")
    search.add_argument("--search", required=True)
    search.add_argument("--limit", type=bounded_int("limit", 1, 100), default=20)
    search.add_argument("--offset", type=bounded_int("offset", 0), default=0)

    performed = subparsers.add_parser(
        "performed-exercises", help="Fetch exercises already performed by the user"
    )
    performed.add_argument("--limit", type=bounded_int("limit", 1, 1000), default=100)
    performed.add_argument("--page", type=bounded_int("page", 1), default=1)

    for name, help_text in (
        ("create-collection", "Validate or create a collection"),
        ("create-template", "Validate or create a workout template"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--input", required=True, help="JSON file path, or - for stdin")
        command.add_argument(
            "--execute",
            action="store_true",
            help="Perform the live write; omit for a dry run",
        )
    return parser


def run(args: argparse.Namespace) -> Any:
    if args.command == "search-exercises":
        return request_json(
            "GET",
            "/api/v1/exercises/library",
            {"search": args.search, "limit": args.limit, "offset": args.offset},
        )
    if args.command == "performed-exercises":
        return request_json(
            "GET", "/api/v1/exercises", {"limit": args.limit, "page": args.page}
        )

    raw = load_payload(args.input)
    if args.command == "create-collection":
        payload = validate_collection(raw)
        endpoint = "/api/v1/collections"
    else:
        payload = validate_template(raw)
        endpoint = "/api/v1/templates"

    if not args.execute:
        return {
            "status": True,
            "dry_run": True,
            "endpoint": endpoint,
            "payload": payload,
        }
    return request_json("POST", endpoint, payload=payload)


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
