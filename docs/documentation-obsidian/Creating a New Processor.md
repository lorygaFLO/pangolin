# Creating a New Processor

Processors are the engine of the pipeline. They read a YAML registry, iterate over input files, match them to patterns, and apply processing logic. All processors inherit from `BaseProcessor`.

This page explains the `BaseProcessor` API and how to create your own custom processor.

---

## BaseProcessor Overview

`BaseProcessor` (in `engine/processors/BaseProcessor.py`) provides:

| Feature | Method / Attribute |
|---------|--------------------|
| Registry loading | resolved from `data_structure.yaml` via `_registry` → `self.registry_path`, `self.registry` |
| DataFacility integration | `self.D` — the project data tree |
| File I/O | `read_file(path)`, `write_file(data, relative_path)` |
| Input discovery | `get_input_files()` → list of `(full_path, relative_path)` |
| Pattern matching | `match_file(relative_path)` → `(pattern, error)` |
| File processing loop | `process_files()` — generator yielding matched files |
| Logging | `self.log` — `ProcessorLogger` instance |
| Filesystem abstraction | `self.fs` — `FSWrapper` instance |

### Constructor Parameters

```python
class BaseProcessor:
    def __init__(self, CTX: RunContext, name: str, input_folder: str, output_folder: str = None):
```

| Parameter | Description |
|-----------|-------------|
| `CTX` | `RunContext` instance — carries the `RUN_ID` shared across the run |
| `name` | Unique step name (used in logs and reports). Must match a node in `data_structure.yaml` that declares `_pattern_matching: true` and `_registry` — the registry YAML is resolved from there. |
| `input_folder` | Dot-notation path to the input folder in `data_structure.yaml` |
| `output_folder` | Dot-notation path to the output folder (optional) |

> [!note]
> There is no `registry_path` parameter: on the step's node in `data_structure.yaml`, `_pattern_matching: true` declares the pattern-matching approach and `_registry` links the registry file.

---

## The `process_files()` Generator

The core iteration pattern is a generator that yields one file at a time:

```python
for full_path, data, pattern, relative_path, errors in self.process_files():
    # full_path:      absolute filesystem path
    # data:           polars.DataFrame (or None on read error)
    # pattern:        matched registry key (or None on match error)
    # relative_path:  path relative to input folder
    # errors:         list of error messages (empty if no errors)
```

This is used by all three built-in processors. Your custom processor should use it too.

---

## Step-by-Step: Creating a Custom Processor

Let's create a **DataAggregator** that groups data by specified columns and saves the aggregated result.

### 1. Create the Processor Class

Create `engine/processors/DataAggregator.py`:

```python
"""
DataAggregator: Groups data by specified columns and aggregates.
"""

import polars as pl
from engine.processors.BaseProcessor import BaseProcessor
from engine.reporter import Reporter
from engine.core.exceptions import NoInputFilesError, AllFilesFailedError
from config.settings import get_settings
from config.run_context import RunContext


class DataAggregator(BaseProcessor):
    def __init__(self, CTX: RunContext, name: str, report_folder: str,
                 input_folder: str, output_folder: str = None):
        super().__init__(CTX, name, input_folder, output_folder)
        self.reporter = Reporter(CTX, report_folder, step_name=name)

    def execute(self, file_paths=None):
        results = {}

        for full_path, data, pattern, rel_path, errors in self.process_files(file_paths):
            if errors:
                self.reporter.write_report(rel_path, errors)
                results[full_path] = {"success": False, "errors": errors}
                continue

            self.log.info(f"Aggregating {rel_path}")
            messages = []

            try:
                # Read aggregation config from registry
                config = self.registry[pattern]
                group_by = config["group_by"]
                agg_rules = config["aggregations"]

                # Build aggregation expressions
                agg_exprs = []
                for col, func in agg_rules.items():
                    if func == "sum":
                        agg_exprs.append(pl.col(col).sum().alias(col))
                    elif func == "mean":
                        agg_exprs.append(pl.col(col).mean().alias(col))
                    elif func == "count":
                        agg_exprs.append(pl.col(col).count().alias(col))

                aggregated = data.group_by(group_by).agg(agg_exprs)

                # Write output
                S = self.S
                out_name = f"{self.fs.splitext(self.fs.basename(rel_path))[0]}.{S.OUTPUT_FORMAT}"
                self.write_file(aggregated, out_name)
                messages.append(f"Aggregated {len(data)} → {len(aggregated)} rows")
                results[full_path] = {"success": True}

            except Exception as e:
                messages.append(f"Aggregation error: {e}")
                results[full_path] = {"success": False}

            self.reporter.write_report(rel_path, messages)

        if not results:
            raise NoInputFilesError(self.name, str(self.input_node.path))

        passed = [p for p, r in results.items() if r["success"]]
        failed = [p for p, r in results.items() if not r["success"]]

        if not passed:
            raise AllFilesFailedError(
                f"[{self.name}] All {len(failed)} file(s) failed aggregation."
            )

        return results
```

### 2. Create the Registry YAML

Create `config/registries/2b_aggregation.yaml`:

```yaml
"*_sales_*":
  group_by:
    - store_id
    - date
  aggregations:
    quantity: sum
    total_sales: sum
    price: mean
```

### 3. Add a Staging Folder to `data_structure.yaml`

`_pattern_matching: true` declares the approach; `_registry` links the step to its registry file:

```yaml
staging:
  # ... existing entries ...
  2b_aggregation:
    _pattern_matching: true
    _registry: "config/registries/2b_aggregation.yaml"
```

### 4. Create the Subflow in `main.py`

```python
from engine.processors.DataAggregator import DataAggregator

@flow(name="2b - Data Aggregation")
def aggregation_flow(CTX):     # ← receives RunContext
    S = get_settings()
    aggregator = DataAggregator(
        CTX,
        name="2b_aggregation",   # registry resolved from data_structure.yaml (_registry)
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.2_transform",
        output_folder="staging.2b_aggregation"
    )
    aggregator.execute()
```

### 5. Wire It Into the Pipeline

```python
    s2 = transform_flow(CTX, return_state=True, wait_for=[s1])
    s2b = aggregation_flow(CTX, return_state=True, wait_for=[s2])
    s3 = validation_flow(CTX, return_state=True, wait_for=[s2b])
```

---

## The Existing Processors

### Validator (`DataValidator.py`)

- Reads `validators` dict from the registry
- Executes each validator function in order
- File is saved to output **only if all validators pass**
- Reports are written for failed files

### DataTransformer (`DataTranformer.py`)

- Reads `transforms` list from the registry
- Sorts by `order` and executes sequentially
- Each transform receives `df`, `messages`, and `**params`
- File is saved **only if all transforms succeed**

### FileDispatcher (`FileDispatcher.py`)

- Reads simple `pattern → folder` mappings
- Copies (or moves) each file to the target subfolder
- Has `rm_from_input_folder` option for move vs copy semantics
- Overrides `get_input_files()` to not raise on empty input

### BackupRestore (`BackupRestore.py`)

- Backs up all input files to `backup/<RUN_ID>/` before processing
- Restores files from a previous backup into the input folder
- Optionally clears the input folder after successful processing
- Does not use a registry — operates directly on input/output folders


---

← [[Writing Transformers]] | [[Welcome|Back to Home]]
