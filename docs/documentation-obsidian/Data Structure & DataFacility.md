# Data Structure & DataFacility

Pangolin uses a single YAML file (`config/data_structure.yaml`) to declare every folder and file the pipeline works with. The `DataFacility` class then maps this schema onto the real filesystem, giving you a navigable Python object tree with built-in I/O.

---

## The YAML Schema

`config/data_structure.yaml` describes the logical folder layout. Here is the default structure:

```yaml
input:
  _description: "Folder with input files"
  _settings_key: "INPUT_FOLDER_NAME"

staging:
  _description: "Processing area"
  _settings_key: "STAGING_FOLDER_NAME"
  _timestamped: true
  0_validator:
    _pattern_matching: true
    _registry: "config/registries/0_raw_validation.yaml"
  1_dispatcher:
    _pattern_matching: true
    _registry: "config/registries/1_dispatcher.yaml"
  2_transform:
    _pattern_matching: true
    _registry: "config/registries/2_transform_registry.yaml"
  3_validation:
    _pattern_matching: true
    _registry: "config/registries/3_validation.yaml"
  4_cross_validation:
    _pattern_matching: true
    _registry: "config/registries/4_cross_validation.yaml"
  5_dispatcher:
    _pattern_matching: true
    _registry: "config/registries/5_dispatcher.yaml"

delivery:
  _description: "Final output"
  _settings_key: "DELIVERY_FOLDER_NAME"
  _timestamped: true
  sales_final:
    _filename: "sales_final.csv"

reports:
  _description: "Report files"
  _settings_key: "REPORTS_FOLDER_NAME"
  _timestamped: true

static:
  _description: "Static support files"
  mappings:
    product_mapping:
      _filename: "product_mapping.csv"
      _required: true
    inventory_snapshot:
      _filename: "inventory_snapshot_product_ids.csv"
      _versioned: true

cache:
  _description: "Temporary cache"
  _path: "cache"
```

---

## Reserved YAML Keys

Keys starting with `_` are metadata directives:

| Key | Type | Description |
|-----|------|-------------|
| `_filename` | `str` | Marks this node as a **file** (not a folder). Value is the filename. |
| `_settings_key` | `str` | Reads the folder name from `SETTINGS.<value>` at runtime. |
| `_timestamped` | `bool` | Appends `<RUN_ID>` to the path. Inherited by children. |
| `_versioned` | `bool` | On overwrite, backs up the old file into a `history/` subfolder. |
| `_required` | `bool` | Can be bulk-checked with `D.validate_required()`. |
| `_description` | `str` | Human-readable description. Exposed as `node.description`. |
| `_path` | `str` | Explicit path relative to `DATAPATH` (overrides name-based resolution). |
| `_pattern_matching` | `bool` | Marks the folder as following the **pattern-matching approach**. Can be used standalone — DataFacility is not limited to processor steps. |
| `_registry` | `str` | Path to the registry YAML used for pattern matching. Requires `_pattern_matching: true`. Processors named after the node resolve their registry from here (no `registry_path` parameter). |

Any other `_`-prefixed key is exposed as a Python attribute with the leading underscore stripped:

```python
node = D.get_node("staging.0_validator")
node.pattern_matching  # True
node.registry          # "config/registries/0_raw_validation.yaml"
```

---

## Path Resolution Rules

DataFacility resolves paths in this priority order:

1. **`_settings_key`** — folder name comes from `SETTINGS`:
   ```yaml
   input:
     _settings_key: "INPUT_FOLDER_NAME"
   # → data/input/   (if INPUT_FOLDER_NAME="input")
   ```

2. **`_path`** — explicit path relative to `DATAPATH`:
   ```yaml
   cache:
     _path: "cache"
   # → data/cache/
   ```

3. **Default** — the node's YAML key is used as the folder name under its parent:
   ```yaml
   static:
     mappings:         # → data/static/mappings/
       product_mapping:
         _filename: "product_mapping.csv"
         # → data/static/mappings/product_mapping.csv
   ```

When `_timestamped: true`, the current `RUN_ID` is inserted:
```
data/staging/  →  data/staging/20260324_185705/
```

---

## Using DataFacility in Code

### Getting the Instance

```python
from engine.DataFacility import get_project_data

D = get_project_data()
```

### Browsing the Tree

```python
D.input                              # <DataFolder: input>
D.staging                            # <DataFolder: staging>  (timestamped)
D.static.mappings.product_mapping    # <DataFile: product_mapping.csv>
```

### Navigating by String (Dot Notation)

Useful when paths come from YAML configuration:

```python
node = D.get_node("static.mappings.product_mapping")
# same as D.static.mappings.product_mapping

# Nodes starting with digits need get_node():
node = D.get_node("staging.0_validator")
```

> [!note]
> `get_node()` also accepts a `D.` prefix — it is tolerated and stripped automatically.

### Inspecting a Node

```python
node = D.static.mappings.product_mapping

node.name          # "product_mapping"
node.is_file       # True
node.path          # Path("…/data/static/mappings/product_mapping.csv")
node.file_format   # "csv"
node.description   # "Mapping files folder"
node.exists()      # True / False
node.config        # raw dict from YAML
```

Folder nodes expose children:

```python
D.delivery.children()   # {'sales_final': <DataNode>, ...}
D.input.list()          # [Path('…/FR_sales_…csv'), …]
D.input.list('FR_*')    # only French files
```

---

## Reading Files

`DataNode.read()` dispatches on format and uses the configured backend:

```python
# CSV → polars.DataFrame
df = D.static.mappings.product_mapping.read()

# Override delimiter for this call:
df = D.static.mappings.product_mapping.read(delimiter=',')

# Parquet, Excel, JSON, YAML all work the same way:
df = D.delivery.sales_final.read()
```

Supported formats: `.csv`, `.parquet`, `.pq`, `.xlsx`, `.xls`, `.json`, `.yaml`, `.yml`

---

## Writing Files

```python
import polars as pl

df = pl.DataFrame({"product_id": ["A1"], "price": [9.99]})

# Overwrite (default)
D.delivery.sales_final.write(df)

# Append — reads existing, concatenates, writes back
D.delivery.sales_final.write(df, mode='append')
# or shortcut:
D.delivery.sales_final.append(df)

# Extra kwargs forwarded to the writer:
D.delivery.sales_final.write(df, delimiter=',')
```

### Versioned Writes

Nodes with `_versioned: true` automatically back up the previous file before overwriting:

```python
# First write: creates the file
D.static.mappings.inventory_snapshot.write(df)

# Second write: moves previous to history/ then writes new data
#   → …/static/mappings/history/inventory_snapshot_20260324_185705.csv
D.static.mappings.inventory_snapshot.write(new_df)
```

---

## Switching Between Runs

```python
# List recent runs
D.list_runs()  # ['20260322_190454', '20260324_185705', ...]

# Switch to a previous run
D.switch_to_run("20260322_190454")
old_df = D.delivery.sales_final.read()

# Or use negative index (-1 = previous run)
D.switch_to_run(-1)

# Restore current run
D.restore_current_run()
```

> [!warning]
> `switch_to_run()` mutates the global Settings singleton. Always call `restore_current_run()` when done.

---

## Validating Required Files

If `_required: true` is present, an error will be raised, having a impact in the output of the process.

```python
results = D.validate_required()
# {'static.mappings.product_mapping': True}

missing = [path for path, ok in results.items() if not ok]
if missing:
    raise FileNotFoundError(f"Required files missing: {missing}")
```

---

## Adding a New Folder or File

To make a new folder/file accessible via DataFacility, add it to `data_structure.yaml`:

### New folder under staging:

```yaml
staging:
  my_new_step:
    _pattern_matching: true
    _registry: "config/registries/my_new_step.yaml"
```

Then access it: `D.get_node("staging.my_new_step")`. `_pattern_matching` declares the approach; `_registry` tells the processor named `my_new_step` which registry YAML to load. A folder can also declare `_pattern_matching: true` alone if it follows the approach without a processor registry.

### New static file:

```yaml
static:
  mappings:
    store_mapping:
      _filename: "store_mapping.csv"
      _required: true
```

Then access it: `D.static.mappings.store_mapping.read()`

---

Next: [[Registry Reference]] →
