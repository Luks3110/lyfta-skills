# Lyfta Skills

Agent skills for working with a user's own account through the Lyfta Developer API.

## Included skills

- `lyfta-read-data`: reads workout history, summaries, performed exercises, exercise-library results, and progress.
- `lyfta-build-programs`: validates and creates personal collections and workout templates after explicit confirmation.

Coach and client operations are intentionally out of scope.

## Install

Install both skills:

```bash
npx skills add Luks3110/lyfta-skills
```

Or install one skill:

```bash
npx skills add Luks3110/lyfta-skills --skill lyfta-read-data
npx skills add Luks3110/lyfta-skills --skill lyfta-build-programs
```

## Authentication

Expose the Lyfta API key through the environment. Do not save it in this repository or pass it as a command argument.

```bash
export LYFTA_API_KEY="your-api-key"
```

The read skill performs only GET requests. The program-building skill defaults to dry runs and requires both explicit user confirmation and `--execute` before sending a write request.

## Requirements

- Python 3.10 or newer
- A Lyfta Developer API key
