# Lyfta Skills

[![skills.sh](https://skills.sh/b/Luks3110/lyfta-skills)](https://skills.sh/Luks3110/lyfta-skills)

Agent skills for working with a user's own account through the Lyfta Developer API.

## Included skills

- `lyfta-read-data`: reads workout history, summaries, performed exercises, exercise-library results, and progress.
- `lyfta-build-programs`: validates and creates personal collections and workout templates after explicit confirmation.

Coach and client operations are intentionally out of scope.

Browse the skills on skills.sh:

- [lyfta-read-data](https://skills.sh/Luks3110/lyfta-skills/lyfta-read-data)
- [lyfta-build-programs](https://skills.sh/Luks3110/lyfta-skills/lyfta-build-programs)

## Install

Install both skills:

```bash
npx skills add https://github.com/Luks3110/lyfta-skills
```

Or install one skill:

```bash
npx skills add https://github.com/Luks3110/lyfta-skills --skill lyfta-read-data
npx skills add https://github.com/Luks3110/lyfta-skills --skill lyfta-build-programs
```

Install both non-interactively for Codex:

```bash
npx skills add https://github.com/Luks3110/lyfta-skills --agent codex --skill '*' --yes
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
