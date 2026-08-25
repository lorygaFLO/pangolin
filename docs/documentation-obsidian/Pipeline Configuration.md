# Pipeline Configuration

This page explains how pipelines are structured, how the default pipeline is assembled in `pipelines/full_processing.py`, and how to add, remove, or reorder stages — or add a whole new pipeline.

---

## Pipelines Are Auto-Discovered

Every file in `pipelines/` (except ones prefixed with `_`) is a **self-contained pipeline**: it can define as many internal `@flow`-decorated subflow steps as it needs, but must expose a module-level `PIPELINE = <flow>` pointing at the flow to run/deploy. `pipelines/__init__.py` scans the folder at import time and builds a `PIPELINES: dict[str, Flow]` registry — used by both `main.py` (CLI) and `docker/deploy.py` (Prefect deployments).

```bash
python main.py --list-pipelines     # list all discovered pipelines
python main.py --pipeline <name>    # run one by name
python main.py                      # runs the default pipeline (full_processing)
python main.py --generate           # shorthand for --pipeline generate_test_data
```

To add a brand-new pipeline: drop a new file in `pipelines/`, define its flow(s), and set `PIPELINE = <your_flow>` — no other registration is needed. It automatically gets its own Prefect deployment (see [[Docker Deployment]]).

> [!warning]
> Don't import subflow steps from another pipeline's file unless you actually want that coupling — steps are typically written around one pipeline's own staging folder layout (e.g. `staging.0_validator`). If two pipelines truly need the same step, that import is explicit and visible in the code, which is intentional: it should look like a deliberate choice, not something that happens by accident.

---

## How the Default Pipeline Works

The default pipeline is defined in `pipelines/full_processing.py` using **Prefect flows**. The structure is **fully configurable** — you choose how many steps to include and in what order. It chains the following subflows as an example:

```python
@flow(name="Full Processing Pipeline")
def data_pipeline(restore_from: Optional[str] = None, clear_input: bool = False):
    logger = get_run_logger()
    CTX = RunContext()

    # Either restore from a previous backup, or backup current input
    if restore_from:
        s_init = restore_flow(CTX, restore_from=restore_from, return_state=True)
    else:
        s_init = backup_flow(CTX, return_state=True)

    s0 = raw_validation_flow(CTX, return_state=True, wait_for=[s_init])
    s1 = raw_dispatch_flow(CTX, return_state=True, wait_for=[s0])
    s2 = transform_flow(CTX, return_state=True, wait_for=[s1])
    s3 = validation_flow(CTX, return_state=True, wait_for=[s2])
    s4 = cross_validation_flow(CTX, return_state=True, wait_for=[s3])
    s5 = final_dispatch_flow(CTX, return_state=True, wait_for=[s4])

    if clear_input and not restore_from:
        clear_input_flow(CTX, wait_for=[s5])
```

| Parameter | Description |
|-----------|-------------|
| `restore_from` | If set (e.g. `"20260324_185705"`), restores files from that backup run instead of backing up fresh input. See [[#BackupRestore]] below. |
| `clear_input` | If `True`, deletes all files from `data/input/` after the pipeline completes (only when not restoring). |

Each subflow:
1. Creates a **Processor** instance (`Validator`, `DataTransformer`, `FileDispatcher`, or `BackupRestore`)
2. Names it after a node in `data_structure.yaml` that declares `_pattern_matching: true` and `_registry` — the **registry YAML** is resolved from there
3. Specifies **input** and **output** folders using dot-notation paths into `data_structure.yaml`
4. Calls `.execute()`

---

## Anatomy of a Subflow

Here is a dissected example — step 2 (Transformation):

```python
@flow(name="2 - Data Transformation")
def transform_flow(CTX):           # ← receives RunContext from the parent flow
    S = get_settings()
    transformer = DataTransformer(
        CTX,                                  # 1. RunContext
        name="2_transform",                   # 2. Step name — must match a data_structure.yaml node with '_registry'
        report_folder=S.REPORTS_FOLDER_NAME,  # 3. Where reports go
        input_folder="staging.1_dispatcher",  # 4. Input (dot-notation)
        output_folder="staging.2_transform"   # 5. Output (dot-notation)
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
    name="2_transform",
    report_folder=S.REPORTS_FOLDER_NAME,
    input_folder="staging.1_dispatcher",
    output_folder="staging.2_transform",
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

- `"staging.1_dispatcher"` → `data/staging/<RUN_ID>/1_dispatcher/`
- `"staging.2_transform"` → `data/staging/<RUN_ID>/2_transform/`
- `S.INPUT_FOLDER_NAME` → `"input"` → `data/input/`
- `S.DELIVERY_FOLDER_NAME` → `"delivery"` → `data/delivery/<RUN_ID>/`

See [[Data Structure & DataFacility]] for the complete path resolution rules.

---

## The Four Processor Types

| Processor | Class | Used For | Registry Format |
|-----------|-------|----------|-----------------|
| **Validator** | `engine.processors.DataValidator.Validator` | Running validation rules on each file | `pattern → {validators: {func_name: params}}` |
| **Transformer** | `engine.processors.DataTranformer.DataTransformer` | Applying ordered transformations | `pattern → {transforms: [{name, function, params, order}]}` |
| **Dispatcher** | `engine.processors.FileDispatcher.FileDispatcher` | Routing files into subfolders | `pattern → "target_folder"` |
| **BackupRestore** | `engine.processors.BackupRestore.BackupRestore` | Backup/restore input files | No registry — uses input/output folders directly |

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
  2b_custom_validation:
    _pattern_matching: true
    _registry: "config/registries/2b_custom_validation.yaml"
```

### 3. Define the Subflow in `pipelines/full_processing.py`

```python
@flow(name="2b - Custom Validation")
def custom_validation_flow(CTX):    # ← receives RunContext
    S = get_settings()
    validator = Validator(
        CTX,
        name="2b_custom_validation",   # registry resolved from data_structure.yaml (_registry)
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.2_transform",
        output_folder="staging.2b_custom_validation"
    )
    validator.execute()
```

### 4. Wire It Into the Main Flow

Insert it in the correct order with `wait_for` dependencies:

```python
    s2 = transform_flow(CTX, return_state=True, wait_for=[s1])
    s2b = custom_validation_flow(CTX, return_state=True, wait_for=[s2])  # ← new
    s3 = validation_flow(CTX, return_state=True, wait_for=[s2b])         # ← updated
    s4 = cross_validation_flow(CTX, return_state=True, wait_for=[s3])
    s5 = final_dispatch_flow(CTX, return_state=True, wait_for=[s4])
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
    name="5_dispatcher",
    report_folder=S.REPORTS_FOLDER_NAME,
    input_folder="staging.4_cross_validation",
    output_folder=S.DELIVERY_FOLDER_NAME,
    rm_from_input_folder=True   # ← moves files instead of copying
)
```

- `rm_from_input_folder=True` — the file is removed from the input after dispatch (move semantics)
- `rm_from_input_folder=False` (default) — the file is copied (original stays)

---

## Deployment Config Per Pipeline

Each pipeline module may optionally declare how `docker/deploy.py` should deploy it:

```python
DEPLOYMENT_NAME = "pangolin-daily"      # optional, defaults to "pangolin-<module_name>"
DEPLOYMENT_KWARGS: dict = {}            # optional extra kwargs merged into .to_deployment()
if os.getenv("PANGOLIN_CRON"):
    DEPLOYMENT_KWARGS["cron"] = os.getenv("PANGOLIN_CRON")
```

`extra_tags` is a special key inside `DEPLOYMENT_KWARGS`, merged into the deployment's tag list (e.g. `generate_test_data.py` uses it to add a `"test-data"` tag). Both attributes are optional — without them, `deploy.py` falls back to `pangolin-<module_name>` with no schedule.

---

## Debugging a Single Step

Every subflow is a plain function that accepts a `RunContext` — you can call it directly from the debugger without running the whole pipeline (e.g. set a breakpoint and evaluate `raw_dispatch_flow(RunContext())` in the Debug Console).

The catch: staging folders are namespaced by `RUN_ID`, which is normally a fresh timestamp on every run, so a standalone step call wouldn't find any previously staged input. Set `DEBUG=True` in `.env` to pin `RUN_ID` to a fixed `DEBUG_RUN_ID` (default `"debug_run"`) instead:

```env
DEBUG=True
DEBUG_RUN_ID=debug_run
```

Run the pipeline (or just the steps you need) once with `DEBUG=True` to populate `data/staging/debug_run/...`, then re-run individual steps against that same folder as many times as you like. Remember to set `DEBUG=False` before running for real — every run in debug mode overwrites the same `debug_run` folder.

---

Next: [[Data Structure & DataFacility]] →
