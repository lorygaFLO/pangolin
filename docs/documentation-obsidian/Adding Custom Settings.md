# Adding Custom Settings

`SETTINGS` (in `pangolin.config.settings`) is fixed — it lives in the library, the same for every project. This page covers how a project adds its own settings on top, without touching the library.

---

## The Three Tiers

| Tier | Where it's declared | Who reads it | Example |
| --- | --- | --- | --- |
| **Core** | `pangolin.config.settings.SETTINGS` (library) | pangolin's engine itself (`DataFacility`, `FSWrapper`, `BaseProcessor`, ...) | `BASEPATH`, `BACKEND_ENGINE`, `CSV_DELIMITER`, `OUTPUT_FORMAT` |
| **Folder** | your project's `config/data_structure.yaml` (`_settings_key`) | pangolin's engine (`SETTINGS._resolve_paths`) | `INPUT_FOLDER_NAME`, `STAGING_FOLDER_NAME` |
| **Custom** | your project's `custom/settings.py` | only your own code (pipelines, custom processors/validators/transformers) | `TRAINING_EPOCHS`, an API key, a feature flag |

The test for where a new setting belongs: **does pangolin's engine need to read this to do its job, or only your own code?** If only your code cares, it's custom — it doesn't belong in the library, and there's no reason to wait for a pangolin release to add it.

(`BACKEND_ENGINE` is a good example of why "configurable" and "custom" aren't the same thing: it's already read from `.env` like everything else, but it's core because `DataFacility`/`FSWrapper` — engine code — read it directly. It's currently validated to accept only `"polars"` because that's the only backend the engine actually implements, not because the field is locked down; see [[Future Developments]] item 8.)

---

## Adding a Setting

`pangolin init` scaffolds an empty `custom/settings.py`:

```python
# custom/settings.py
from pangolin.config.settings import SETTINGS as _BaseSettings

class SETTINGS(_BaseSettings):
    # Add your fields here, same syntax as any pydantic-settings field:
    TRAINING_EPOCHS: int = 10
```

1. **Add the field** to the `SETTINGS` class in `custom/settings.py`, as above.
2. **Set it in `.env`** (or as an environment variable), same as any other setting:
   ```ini
   TRAINING_EPOCHS=20
   ```
3. **Read it anywhere** `get_settings()` is called — pipelines, custom processors, custom validators/transformers:
   ```python
   from pangolin.config.settings import get_settings
   S = get_settings()
   print(S.TRAINING_EPOCHS)  # 20
   ```

No registration step, no library changes. `pangolin.config.settings.get_settings()` auto-detects `custom/settings.py`: it tries `from custom.settings import SETTINGS` first, and falls back to the base class if the project doesn't define one (a real import error *inside* `custom/settings.py` — a typo, a bad import — still surfaces normally; only a genuinely missing file/package falls back silently). Delete `custom/settings.py` entirely and pangolin falls back to the base `SETTINGS` transparently.

> [!important]
> The field name **must match** the env variable name exactly (case-sensitive), same rule as every pydantic-settings field.

### Supported Types

Pydantic automatically coerces `.env` strings into the declared type:

| Field Type | `.env` Value | Python Result |
|------------|-------------|---------------|
| `str` | `MY_VAR=hello` | `"hello"` |
| `int` | `MY_VAR=42` | `42` |
| `bool` | `MY_VAR=true` | `True` (accepts `1`, `true`, `yes`, `on`) |
| `float` | `MY_VAR=3.14` | `3.14` |
| `dict` | `MY_VAR={"k": "v"}` | `{"k": "v"}` (parsed as JSON) |
| `Optional[str]` | *(not set)* | `None` |

---

## Adding Validation

Use `@field_validator` to enforce constraints, exactly as you would on any Pydantic model:

```python
from pydantic import field_validator
from pangolin.config.settings import SETTINGS as _BaseSettings

class SETTINGS(_BaseSettings):
    TRAINING_EPOCHS: int = 10

    @field_validator("TRAINING_EPOCHS")
    @classmethod
    def _validate_epochs(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"TRAINING_EPOCHS must be >= 1, got {v}")
        return v
```

An invalid value (e.g. `TRAINING_EPOCHS=0` in `.env`) makes `get_settings()` raise a `pydantic.ValidationError` immediately, before your pipeline runs.

## Adding a Derived / Computed Setting

Use `@computed_field` for a value derived from other settings — recalculated on every access, never stored:

```python
from pydantic import computed_field
from pangolin.config.settings import SETTINGS as _BaseSettings

class SETTINGS(_BaseSettings):
    MODEL_NAME: str = "baseline"

    @computed_field
    @property
    def PATH_MODEL_OUTPUT(self) -> str:
        return f"{self.DATAPATH}/models/{self.MODEL_NAME}"
```

`self.DATAPATH` (a core field) is available here too — a project's `SETTINGS` subclass has every core and folder field, plus whatever it adds.

---

## Sensitive Settings (Passwords, API Keys, DB Connection Strings)

Everything above works for a sensitive value too — `DATABASE_URL: str` in `custom/settings.py` behaves exactly like `TRAINING_EPOCHS`. What changes is **where the actual value lives**, and that depends on how you're running.

> [!important]
> The field must exist on the `SETTINGS` class first, in both cases below. `SETTINGS` has `extra="ignore"` — an env var with no matching field is silently dropped, not picked up. Setting `DATABASE_URL` in `.env` without declaring `DATABASE_URL: str` in `custom/settings.py` does nothing; `S.DATABASE_URL` would raise `AttributeError`.

### Local (no Docker)

1. Declare the field once in `custom/settings.py`:
   ```python
   class SETTINGS(_BaseSettings):
       DATABASE_URL: str
   ```
2. Put the real value in `.env`, same as anything else:
   ```ini
   DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
   ```

`.env` is git-ignored by the `.gitignore` `pangolin init` scaffolds — never committed. That's the whole story for local dev.

### Docker / cloud (`pangolin init --dockerization`)

`.env` doesn't travel with the image, and you don't want a real password baked into a committed file anyway. Use a Prefect **secret Block** in `docker/prefect_manifest.yaml` instead — see [[Docker Deployment]] for the full mechanism, in short:

```yaml
blocks:
  - name: pangolin-database-url
    type: secret
    value: "${DATABASE_URL}"        # resolved from docker/.env.docker at bootstrap
    expose_as_env: DATABASE_URL     # pangolin deploy exports it to os.environ under this name
```

1. Put the real value in `docker/.env.docker` (git-ignored, never committed — `docker/.env.docker.example` is the committed template).
2. `pangolin bootstrap` reads the manifest, resolves `${DATABASE_URL}`, and stores it **encrypted** in Prefect's own database.
3. `pangolin deploy` exports it into `os.environ` before your pipeline imports anything — your `custom/settings.py`'s `DATABASE_URL` field picks it up exactly like it would from `.env`, no extra code.
4. From then on you can also edit the value straight from the Prefect UI (Blocks) — it survives image rebuilds, and `docker/.env.docker` is only needed again if the Block is ever wiped (e.g. `make clean`).

This is the same mechanism the scaffolded `docker/prefect_manifest.yaml` already uses for `AZURE_STORAGE_CONNECTION_STRING` — copy that block, rename it, point `expose_as_env` at your own field name.

> [!warning]
> Never put a real secret value directly in `docker/prefect_manifest.yaml` (that file is meant to be committed) — always `${ENV_VAR}` or `null`, resolved from `docker/.env.docker` (git-ignored) or filled in later via the UI.

---

## Sharing a Custom Setting Across Projects

If the same custom setting keeps showing up in every project you build, that's a sign it might belong in the library itself instead of being re-declared per project — open an issue or contribute it to `pangolin.config.settings.SETTINGS` (this repo, not your project).

---

Next: [[Getting Started]] · [[Data Structure & DataFacility]]
