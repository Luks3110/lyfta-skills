# Lyfta personal write API

Base URL: `https://my.lyfta.app`

Authentication: `Authorization: Bearer <API key>`

All writes use `Content-Type: application/json`. Coach fields are deliberately unsupported.

## Create a collection

`POST /api/v1/collections`

```json
{
  "collection": {
    "title": "Strength block",
    "description": "Four-week strength block",
    "goal": "strength",
    "image": "BASE64_WITHOUT_A_DATA_URI_PREFIX"
  }
}
```

`collection.title` is required after trimming. Description, goal, and image are optional. Collection images must be base64 strings; URLs are rejected. A successful response has `status: true` and the created resource under `data`, including its numeric `id`.

## Create a template

`POST /api/v1/templates`

```json
{
  "collectionId": 42,
  "workout": {
    "title": "Push day",
    "description": "Chest and shoulders",
    "note": "Stop before technical failure",
    "color": "#178B76",
    "picture": "https://cdnlyfta.com/images/original/example.jpeg",
    "exercises": [{
      "exercise_id": 123,
      "excercise_name": "Bench Press",
      "exercise_type": "weight_reps",
      "exercise_image": "https://apilyfta.com/static/example.png",
      "exercise_note": "Controlled eccentric",
      "exercise_rest_time": 90,
      "exercise_superset_id": 0,
      "is_rep_range_active": false,
      "sets": [
        {"set_type_id": 0, "reps": "10", "weight": "60", "rir": "2"}
      ]
    }]
  }
}
```

Required top-level fields:

- `collectionId`: positive integer for an existing collection owned by the authenticated user.
- `workout`: object.

The server can generate a title, color, and timestamps, but an explicit title is preferable. Exercises may be empty.

For every exercise, copy these exact catalog values:

| Template field | Catalog field |
| --- | --- |
| `exercise_id` | `id` |
| `excercise_name` | `name` |
| `exercise_type` | `exercise_type` |
| `exercise_image` | `image_name` |

The spelling `excercise_name` is intentional. If the API does not provide an unambiguous exact match or returns missing required metadata, stop instead of guessing.

Optional exercise fields include `exercise_note`, `exercise_rest_time`, `exercise_superset_id`, `is_rep_range_active`, and `sets`.

### Rest intervals

`exercise_rest_time` is an integer number of seconds, not minutes. Convert a user-provided value exactly once before building the payload:

| Requested rest | API value |
| --- | ---: |
| 30 seconds | `30` |
| 1 minute | `60` |
| 2 minutes | `120` |
| 3 minutes | `180` |
| 5 minutes | `300` |
| 10 minutes | `600` |

Keep rest separate from the set-level `duration` field, which represents exercise work time. Before a write, summarize both representations, such as `2 min (120 seconds)`, and scan every exercise. If the user says “2 minutes for all,” every `exercise_rest_time` must equal `120`.

The bundled client rejects values above 300 seconds by default because an accidental `600` produces a 10-minute rest. Use `--allow-long-rest` only after the user explicitly requests more than 5 minutes.

Set fields:

- `set_type_id`: integer, default 0.
- `reps`, `from_reps`, `to_reps`, `weight`, `rir`, `duration`, `distance`: strings.
- Use `from_reps` and `to_reps` when `is_rep_range_active` is true.
- Use `duration` for time-based exercises and `distance` for distance-based exercises.

Template pictures accept a base64 data URI or an existing HTTPS URL. Lyfta CDN URLs are safest because non-CDN URLs may be sanitized away.

## Catalog lookup

Use `GET /api/v1/exercises/library?search=...&limit=...&offset=...` to search the full catalog and `GET /api/v1/exercises?limit=...&page=...` to inspect exercises already performed by the user. Catalog `exercise_type` can be null; do not infer a value merely from an exercise name.

## Errors and retries

Expected messages include `Title is required`, `workout is required`, `collectionId is required`, `Collection not found`, and `Invalid API key`. Rate limits return HTTP 429.

Do not automatically retry a timed-out POST. Its outcome is ambiguous and retrying may create a duplicate collection or template.
