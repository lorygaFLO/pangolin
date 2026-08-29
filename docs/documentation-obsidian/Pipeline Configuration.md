# Pipeline Configuration

This page explains how pipelines are structured, how the example pipeline is assembled in `pipelines/example_pipeline.py` (scaffolded by `pangolin init`), and how to add, remove, or reorder stages — or add a whole new pipeline.

---

## Pipelines Are Auto-Discovered

Every file in your project's `pipelines/` (except ones prefixed with `_`) is a **self-contained pipeline**: it can define as many internal `@flow`-decorated subflow steps as it needs, but must expose a module-level `PIPELINE = <flow>` pointing at the flow to run/deploy. `pipelines/__init__.py` scans the folder at import time and builds a `PIPELINES: dict[str, Flow]` registry — used by every pipeline-related `pangolin` CLI command.

```bash
pangolin list                     # list all discovered pipelines and their steps
pangolin run <name>               # run one by name
pangolin run                      # runs the default pipeline (example_pipeline, or the only one)
pangolin step <name> <step>       # run a single step in isolation (see below)
pangolin deploy                   # serve every pipeline as a Prefect deployment
```

To add a brand-new pipeline: drop a new file in `pipelines/`, define its flow(s), and set `PIPELINE = <your_flow>` — no other registration is needed. It automatically gets its own Prefect deployment (see [[Docker Deployment]]).

> [!warning]
> Don't import subflow steps from another pipeline's file unless you actually want that coupling — steps are typically written around one pipeline's own staging folder layout (e.g. `staging.0_validator`). If two pipelines truly need the same step, that import is explicit and visible in the code, which is intentional: it should look like a deliberate choice, not something that happens by accident.

---

## How the Example Pipeline Works

The example pipeline is defined in `pipelines/example_pipeline.py` using **Prefect flows**. The structure is **fully configurable** — you choose how many steps to include and in what order. It chains the following subflows as an example:

```python
@flow(name="Example Pipeline")
def example_pipeline():
    logger = get_run_logger()
    CTX = RunContext()

    s_init = backup_flow(CTX, return_state=True)
    s0 = raw_validation_flow(CTX, return_state=True, wait_for=[s_init])
    s1 = transform_flow(CTX, return_state=True, wait_for=[s0])
    s2 = audit_flow(CTX, return_state=True, wait_for=[s1])
    delivery_flow(CTX, return_state=True, wait_for=[s2])
```

The bundled `BackupRestore` processor also supports restoring from a previous backup instead of backing up fresh input, and clearing `data/input/` after a successful run — the example pipeline above doesn't expose these as flow parameters, but you can add them the same way the processor supports them (`backup.restore(run_id)` / `backup.clear_input_folder()`, see [[Creating a New Processor]] for the `BackupRestore` API, or just add `restore_from`/`clear_input` parameters to your own `@flow` the way you would any Prefect flow).

Each subflow:
1. Creates a **Processor** instance (`Validator`, `DataTransformer`, `FileDispatcher`, or `BackupRestore`)
2. Names it after a node in `data_structure.yaml` that declares `_pattern_matching: true` and `_registry` — the **registry YAML** is resolved from there
3. Specifies **input** and **output** folders using dot-notation paths into `data_structure.yaml`
4. Calls `.execute()`

---

## Anatomy of a Subflow

Here is a dissected example — step 1 (Transform):

```python
@flow(name="1 - Transform")
def transform_flow(CTX):           # ← receives RunContext from the parent flow
    S = get_settings()
    transformer = DataTransformer(
        CTX,                                  # 1. RunContext
        name="1_transform",                   # 2. Step name — must match a data_structure.yaml node with '_registry'
        report_folder=S.REPORTS_FOLDER_NAME,  # 3. Where reports go
        input_folder="staging.0_validator",   # 4. Input (dot-notation)
        output_folder="staging.1_transform"   # 5. Output (dot-notation)
    )
    transformer.execute()
```

| Parameter | Description |
|-----------|-------------|
| `CTX` | `RunContext` instance — carries the `RUN_ID` shared across all steps of a run |
| `name` | Unique step identifier, appears in logs and report subfolder names. The registry YAML is resolved from the `_registry` key on the `data_structure.yaml` node with this name (which must also declare `_pattern_matching: true`). |
| `report_folder` | Dot-notation path to the reports folder in `data_structure.yaml` |
| `input_folder` | Dot-notation path to the input folder — reads files from here |
| `output_folder` | Dot-notation path to the output folder — writes results here |
| `registry` | *(optional)* Custom registry — a `dict` (in-memory) or a `str` path to a YAML file. Takes priority over `_registry` in `data_structure.yaml`. If neither is available, the processor raises a `ValueError`. |

### Passing a Custom Registry

A registry can also come from another source (hand-written dict, database, API, …) instead of `data_structure.yaml`:

```python
transformer = DataTransformer(
    CTX,
    name="1_transform",
    report_folder=S.REPORTS_FOLDER_NAME,
    input_folder="staging.0_validator",
    output_folder="staging.1_transform",
    registry={  # ← in-memory registry, overrides data_structure.yaml
        "*sales*": {
            "transforms": [
                {"name": "clean", "function": "drop_nulls", "order": 1}
            ]
        }
    }
    # or: registry="path/to/custom_registry.yaml"
)
```

### Dot-Notation Paths

Input and output folders use **dot-notation** to navigate the `data_structure.yaml` tree:

- `"staging.0_validator"` → `data/staging/<RUN_ID>/0_validator/`
- `"staging.1_transform"` → `data/staging/<RUN_ID>/1_transform/`
- `S.INPUT_FOLDER_NAME` → `"input"` → `data/input/`
- `S.DELIVERY_FOLDER_NAME` → `"delivery"` → `data/delivery/<RUN_ID>/`

See [[Data Structure & DataFacility]] for the complete path resolution rules.

---

## The Four Processor Types

| Processor | Class | Used For | Registry Format |
|-----------|-------|----------|-----------------|
| **Validator** | `pangolin.engine.processors.DataValidator.Validator` | Running validation rules on each file | `pattern → {validators: {func_name: params}}` |
| **Transformer** | `pangolin.engine.processors.DataTransformer.DataTransformer` | Applying ordered transformations | `pattern → {transforms: [{name, function, params, order}]}` |
| **Dispatcher** | `pangolin.engine.processors.FileDispatcher.FileDispatcher` | Routing files into subfolders | `pattern → "target_folder"` |
| **BackupRestore** | `pangolin.engine.processors.BackupRestore.BackupRestore` | Backup/restore input files | No registry — uses input/output folders directly |

A custom processor type (like the `AuditProcessor` in the example project's `custom/processors/`) can implement whatever registry format it wants — see [[Creating a New Processor]].

See [[Registry Reference]] for detailed YAML formats.

---

## Adding a New Step

To add a new step to the pipeline:

### 1. Create the Registry File

Create a new YAML file in `config/registries/`. Follow the naming convention `<N>_<name>.yaml`:

```yaml
# config/registries/2b_custom_validation.yaml
"*sales*":
  validators:
    value_range:
      price:
        min: 0
        max: 10000
```

### 2. Update `data_structure.yaml`

Add the staging folder under `staging` — `_pattern_matching: true` declares the approach, `_registry` links the registry file:

```yaml
staging:
  # ... existing entries ...
  1b_custom_validation:
    _pattern_matching: true
    _registry: "config/registries/1b_custom_validation.yaml"
```

### 3. Define the Subflow in `pipelines/example_pipeline.py`

```python
@flow(name="1b - Custom Validation")
def custom_validation_flow(CTX):    # ← receives RunContext
    S = get_settings()
    validator = Validator(
        CTX,
        name="1b_custom_validation",   # registry resolved from data_structure.yaml (_registry)
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.1_transform",
        output_folder="staging.1b_custom_validation"
    )
    validator.execute()
```

### 4. Wire It Into the Main Flow

Insert it in the correct order with `wait_for` dependencies:

```python
    s1 = transform_flow(CTX, return_state=True, wait_for=[s0])
    s1b = custom_validation_flow(CTX, return_state=True, wait_for=[s1])  # ← new
    s2 = audit_flow(CTX, return_state=True, wait_for=[s1b])              # ← updated
    delivery_flow(CTX, return_state=True, wait_for=[s2])
```

> [!important]
> Make sure the `input_folder` of the new step matches the `output_folder` of the previous step.

---

## Removing a Step

1. Remove the subflow call from `data_pipeline()`
2. Update `wait_for` references so the chain is not broken
3. Optionally remove the registry file and `data_structure.yaml` entry

---

## Error Handling

If any step fails, the pipeline raises a `PipelineError`:

- **`NoInputFilesError`** — no files found in the input folder (check previous step)
- **`AllFilesFailedError`** — every file failed validation/transformation (check reports)

These are caught in the main flow and logged:

```python
try:
    # ... subflow calls ...
except PipelineError as e:
    logger.error(f"Pipeline halted: {e}")
    raise
```

---

## FileDispatcher-Specific Options

The `FileDispatcher` has an extra parameter:

```python
dispatcher = FileDispatcher(
    CTX,
    name="3_dispatcher",
    report_folder=S.REPORTS_FOLDER_NAME,
    input_folder="staging.2_audit",
    output_folder=S.DELIVERY_FOLDER_NAME,
    rm_from_input_folder=True   # ← moves files instead of copying
)
```

- `rm_from_input_folder=True` — the file is removed from the input after dispatch (move semantics)
- `rm_from_input_folder=False` (default) — the file is copied (original stays)

---

## Deployment Config Per Pipeline

Each pipeline module may optionally declare how `pangolin deploy` should deploy it:

```python
DEPLOYMENT_NAME = "pangolin-daily"      # optional, defaults to "pangolin-<module_name>"
DEPLOYMENT_KWARGS: dict = {}            # optional extra kwargs merged into .to_deployment()
if os.getenv("PANGOLIN_CRON"):
    DEPLOYMENT_KWARGS["cron"] = os.getenv("PANGOLIN_CRON")
```

`extra_tags` is a special key inside `DEPLOYMENT_KWARGS`, merged into the deployment's tag list. Both attributes are optional — without them, `pangolin deploy` falls back to `pangolin-<module_name>` (e.g. `example_pipeline` → `pangolin-example-pipeline`) with no schedule.

---

## Debugging a Single Step

Every subflow is a plain function that accepts a `RunContext` — you don't need to run the whole pipeline to exercise or debug just one of them. The CLI exposes this directly (the pipeline name is always required):

```bash
# List steps discovered for each pipeline (any module-level @flow that isn't its PIPELINE)
pangolin list

# Run a single step in isolation
pangolin step example_pipeline transform_flow

# Steps that take extra arguments forward them positionally, e.g. a subflow
# that wraps BackupRestore.restore(run_id):
pangolin step example_pipeline restore_flow 20260324_185705
```

Steps are **auto-discovered** by inspecting the pipeline module for `Flow` objects (excluding the one assigned to `PIPELINE`) — so nothing needs to be kept in sync by hand when you add, rename, or remove a subflow.

> [!important]
> Unknown/mistyped flags (e.g. `--lists-steps`) are rejected with a `unrecognized arguments` error instead of silently falling through to running the whole pipeline.

### Staging Data with `DEBUG=True`

The catch: staging folders are namespaced by `RUN_ID`, which is normally a fresh timestamp on every run, so a standalone step call wouldn't find any previously staged input. Set `DEBUG=True` in `.env` (or as an env var) to pin `RUN_ID` to a fixed `DEBUG_RUN_ID` (default `"debug_run"`) instead:

```env
DEBUG=True
DEBUG_RUN_ID=debug_run
```

Run the pipeline (or just the steps you need) once with `DEBUG=True` to populate `data/staging/debug_run/...`, then re-run individual steps against that same folder as many times as you like. Remember to set `DEBUG=False` before running for real — every run in debug mode overwrites the same `debug_run` folder.

### Configuring the VS Code Debugger

`pangolin init` doesn't scaffold a `.vscode/launch.json` (editor config is a personal/project choice, not something the library should impose). Add one yourself with a config like this:

```jsonc
{
    // Template: duplicate me and edit "args" (and "name") to debug a
    // different step. Run `pangolin list` to see valid step names.
    // Equivalent CLI: pangolin step <pipeline> <step> [args...]
    "name": "Python: Debug Step - example_pipeline/transform_flow",
    "type": "debugpy",
    "request": "launch",
    "module": "pangolin.cli",
    "args": ["step", "example_pipeline", "transform_flow"],
    "console": "integratedTerminal",
    "justMyCode": false,
    "env": {
        "DEBUG": "True"
    }
}
```

To debug a different step:

1. Duplicate the whole block inside `configurations` in `.vscode/launch.json`.
2. Change `"name"` to something recognizable (e.g. `"...  - example_pipeline/audit_flow"`).
3. Change the step name in `"args"` to the one you want (see `pangolin list` for valid names), and the pipeline name if it's a different pipeline.
4. Pick it from the Run and Debug dropdown (or `F5`) and set breakpoints anywhere — including inside `pangolin/engine/processors/*`, since `justMyCode` is `false`.

`"env": {"DEBUG": "True"}` is already set on the template, so `RUN_ID` stays pinned without touching `.env`.

---

Next: [[Data Structure & DataFacility]] →
