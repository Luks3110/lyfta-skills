# Lyfta personal read API

Base URL: `https://my.lyfta.app`

Authentication: `Authorization: Bearer <API key>`

Limits: 60 requests per minute and 5,000 requests per day. A limit violation returns HTTP 429.

## Endpoints

| Command | Endpoint | Parameters | Main response data |
| --- | --- | --- | --- |
| `workouts` | `GET /api/v1/workouts` | `limit` (max 100), `page` | Detailed workouts in `workouts[]` |
| `workout-summary` | `GET /api/v1/workouts/summary` | `limit` (max 1000), `page` | Summaries in `workouts[]` |
| `exercises` | `GET /api/v1/exercises` | `limit`, `page` | Performed exercises in `exercises[]` |
| `library` | `GET /api/v1/exercises/library` | `search`, `limit`, `offset` | Catalog results in `data.results[]` |
| `progress` | `GET /api/v1/exercises/progress` | required `exercise_id`, required `duration` in days | Daily records in `data[]` |

Do not send `client_id`; coach access is outside this skill.

## Detailed workouts

`GET /api/v1/workouts` returns pagination fields plus:

```json
{
  "workouts": [{
    "id": 123,
    "title": "Push day",
    "body_weight": 80,
    "workout_perform_date": "2026-08-01 07:30:00",
    "total_volume": 12345,
    "totalLiftedWeight": 12345,
    "user": {"username": "Example"},
    "exercises": [{
      "exercise_id": 31,
      "excercise_name": "Bench Press",
      "exercise_type": "weight_reps",
      "exercise_image": "https://...",
      "exercise_rest_time": 90,
      "sets": [{
        "id": "1",
        "weight": "60",
        "reps": "10",
        "rir": "2",
        "duration": "",
        "distance": "",
        "set_type_id": "0",
        "is_completed": true,
        "record_type": "",
        "record_level": "",
        "record_value": ""
      }]
    }]
  }]
}
```

Fields can be null or omitted. Set values often arrive as strings.

## Workout summaries

`GET /api/v1/workouts/summary` returns up to 1,000 records per request. Each item includes `id`, `title`, nullable `description`, `workout_duration`, `total_volume`, and `workout_perform_date`. Durations use `HH:MM:SS`; volume and IDs may be strings.

## Exercises

Performed and catalog exercise records can contain:

```json
{
  "id": "31",
  "name": "Rear Lunge",
  "image_name": "https://apilyfta.com/static/...png",
  "equipment_id": "[\"1\"]",
  "body_part_id": "[\"19\",\"1\"]",
  "Target_muscles_id": "[\"13\",\"27\"]",
  "Synergist_muscles_id": "[\"3\",\"32\"]",
  "exercise_type": "weight_reps"
}
```

The four metadata ID fields are JSON-encoded arrays, not native arrays. `--decode-ids` preserves those fields and adds readable `equipment`, `body_parts`, `target_muscles`, and `synergist_muscles` arrays using `id-mappings.json`.

Library pagination is cursor-style:

```json
{
  "data": {
    "results": [],
    "pagination": {"limit": 10, "offset": 0, "total": 108, "hasMore": true}
  }
}
```

`exercise_type` may be null in catalog results. Do not infer a type from the name alone.

## Exercise progress

`GET /api/v1/exercises/progress` requires both parameters and returns:

```json
{
  "weight_unit": "kg",
  "data": [{
    "date": "2026-07-21",
    "best_weight": 110,
    "best_reps": 15,
    "best_volume": 800,
    "estimated_rm": "128"
  }]
}
```

The values are the API's daily bests for the requested exercise. `estimated_rm` usually arrives as a string.
