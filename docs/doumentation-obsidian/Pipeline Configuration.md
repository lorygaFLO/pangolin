# Pipeline Configuration

This page explains how the main pipeline is assembled in `main.py` and how to add, remove, or reorder stages.

---

## How the Pipeline Works

The pipeline is defined in `main.py` using **Prefect flows**. The structure is **fully configurable** — you choose how many steps to include and in what order. The default configuration chains the following subflows as an example:

```python
@flow(name="Full Processing Pipeline")
def data_pipeline():
    S = get_settings()

    s0 = raw_validation_flow(S, return_state=True)
    s1 = raw_dispatch_flow(S, return_state=True, wait_for=[s0])
    s2 = transform_flow(S, return_state=True, wait_for=[s1])
    s3 = validation_flow(S, return_state=True, wait_for=[s2])
    s4 = cross_validation_flow(S, return_state=True, wait_for=[s3])
    final_dispatch_flow(S, wait_for=[s4])
```

Each subflow:
1. Creates a **Processor** instance (`Validator`, `DataTransformer`, or `FileDispatcher`)
2. Points it to a **registry YAML** file
3. Specifies **input** and **output** folders using dot-notation paths into `data_structure.yaml`
4. Calls `.execute()`

---

## Anatomy of a Subflow

Here is a dissected example — step 2 (Transformation):

```python
@flow(name="2 - Data Transformation")
def transform_flow(S):
    transformer = DataTransformer(
        name="2_transform", # 1. Step name (used in logs)
        registry_path="config/registries/2_transform_registry.yaml", # 2. Rules file
        report_folder=S.REPORTS_FOLDER_NAME, # 3. Where reports go
        input_folder="staging.1_dispatcher", # 4. Input (dot-notation)
        output_folder="staging.2_transform" # 5. Output (dot-notation)
    )
    transformer.execute()
```

| Parameter | Description |
|-----------|-------------|
| `name` | Unique step identifier, appears in logs and report subfolder names |
| `registry_path` | Path to the YAML registry file (relative to project root) |
| `report_folder` | Dot-notation path to the reports folder in `data_structure.yaml` |
| `input_folder` | Dot-notation path to the input folder — reads files from here |
| `output_folder` | Dot-notation path to the output folder — writes results here |

### Dot-Notation Paths

Input and output folders use **dot-notation** to navigate the `data_structure.yaml` tree:

- `"staging.1_dispatcher"` → `data/staging/<RUN_ID>/1_dispatcher/`
- `"staging.2_transform"` → `data/staging/<RUN_ID>/2_transform/`
- `S.INPUT_FOLDER_NAME` → `"input"` → `data/input/`
- `S.DELIVERY_FOLDER_NAME` → `"delivery"` → `data/delivery/<RUN_ID>/`

See [[Data Structure & DataFacility]] for the complete path resolution rules.

---

## The Three Processor Types

| Processor | Class | Used For | Registry Format |
|-----------|-------|----------|-----------------|
| **Validator** | `engine.processors.DataValidator.Validator` | Running validation rules on each file | `pattern → {validators: {func_name: params}}` |
| **Transformer** | `engine.processors.DataTranformer.DataTransformer` | Applying ordered transformations | `pattern → {transforms: [{name, function, params, order}]}` |
| **Dispatcher** | `engine.processors.FileDispatcher.FileDispatcher` | Routing files into subfolders | `pattern → "target_folder"` |

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

Add folders for staging input/output under `staging`:

```yaml
staging:
  # ... existing entries ...
  2b_custom_validation:
    _pattern_matching: true
```

### 3. Define the Subflow in `main.py`

```python
@flow(name="2b - Custom Validation")
def custom_validation_flow(S):
    validator = Validator(
        name="2b_custom_validation",
        registry_path="config/registries/2b_custom_validation.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.2_transform",
        output_folder="staging.2b_custom_validation"
    )
    validator.execute()
```

### 4. Wire It Into the Main Flow

Insert it in the correct order with `wait_for` dependencies:

```python
@flow(name="Full Processing Pipeline")
def data_pipeline():
    S = get_settings()

    s0 = raw_validation_flow(S, return_state=True)
    s1 = raw_dispatch_flow(S, return_state=True, wait_for=[s0])
    s2 = transform_flow(S, return_state=True, wait_for=[s1])
    s2b = custom_validation_flow(S, return_state=True, wait_for=[s2])  # ← new
    s3 = validation_flow(S, return_state=True, wait_for=[s2b])         # ← updated
    s4 = cross_validation_flow(S, return_state=True, wait_for=[s3])
    final_dispatch_flow(S, wait_for=[s4])
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
    name="5_dispatcher",
    registry_path="config/registries/5_dispatcher.yaml",
    report_folder=S.REPORTS_FOLDER_NAME,
    input_folder="staging.4_cross_validation",
    output_folder=S.DELIVERY_FOLDER_NAME,
    rm_from_input_folder=True   # ← moves files instead of copying
)
```

- `rm_from_input_folder=True` — the file is removed from the input after dispatch (move semantics)
- `rm_from_input_folder=False` (default) — the file is copied (original stays)

---

Next: [[Data Structure & DataFacility]] →
