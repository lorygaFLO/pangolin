# Registry Reference

Registry files are the YAML configuration files in `config/registries/` that drive each pipeline step. They map **file-name glob patterns** to processing rules. Each processor type expects a specific registry format.

---

## How Pattern Matching Works

Every registry is a YAML dictionary where **keys are glob patterns** and values are the processing rules:

```yaml
"*sales*":       # matches any file with "sales" in the name
  # ... rules ...

"*inventory*":   # matches any file with "inventory" in the name
  # ... rules ...
```

When a processor reads a file, it matches the file's **relative path** (including subfolders) against all patterns in the registry. Standard `fnmatch` glob syntax is used:

| Pattern | Matches |
|---------|---------|
| `*sales*` | `FR_sales_data.csv`, `US_sales_data.csv` |
| `*inventory*` | `FR_inventory_data.csv` |
| `FR_*` | All files starting with `FR_` |
| `test_*.csv` | `test_data.csv`, `test_sample.csv` |
| `SALES/*sales*` | Files with "sales" inside the `SALES/` subfolder |

> [!warning]
> Each file must match **exactly one** pattern. Zero matches or multiple matches are errors.

---

## Validation Registry Format

Used by the `Validator` processor (step 0 in the example project).

```yaml
"<pattern>":
  validators:
    <validator_function_name>: <params_or_null>
    <validator_function_name>: <params_or_null>
```

### Example: `0_raw_validation.yaml` (as scaffolded by `pangolin init`)

```yaml
"*sales*":
  validators:
    is_empty_dataframe:           # no params → null
    required_columns:             # params = list of column names
      - product_id
      - product_name
      - price
      - quantity
      - date
    quantity_not_negative:        # custom validator, defined in custom/validators.py
      quantity_column: quantity
```

### Parameter Passing

The YAML value after the function name becomes the `params` argument:

| YAML | Python `params` |
|------|-----------------|
| `is_empty_dataframe:` (empty) | `None` — function called as `func(df, messages)` |
| `required_columns:\n  - col_a\n  - col_b` | `["col_a", "col_b"]` |
| `validate_product_ids:\n  product_id_column: product_id` | `{"product_id_column": "product_id"}` |
| `value_range:\n  price:\n    min: 0\n    max: 1000` | `{"price": {"min": 0, "max": 1000}}` |

### More Built-in Validators (usable in any validation registry)

```yaml
"*sales*":
  validators:
    always_true_validator:
    check_null_values:
      columns:
        - price
        - quantity
      custom_null_values:
        - ""
        - " "
        - "NA"
        - "N/A"
        - "NULL"
    value_range:
      price:
        min: 0
        max: 1000
```

Nothing stops you from adding a second validation step later in the pipeline (e.g. `1b_post_transform_validation.yaml`) if you need to validate again after transforming — see [[Pipeline Configuration]] for wiring in a new step.

See [[Writing Validators]] for the list of built-in validators and how to create your own.

---

## Transformation Registry Format

Used by the `DataTransformer` processor (step 1 in the example project).

```yaml
"<pattern>":
  transforms:
    - name: "<human-readable name>"
      function: "<transformer_function_name>"
      params:
        <key>: <value>
      order: <integer>
```

Transforms are executed **in `order`** (ascending). All must succeed for the file to be saved.

### Example: `1_transform.yaml` (as scaffolded by `pangolin init`)

```yaml
"*sales*":
  transforms:
    - name: "total_amount_calculation"
      function: "multiply_columns"
      params:
        columns_to_multiply:
          - price
          - quantity
        output_column: total_amount
      order: 1

    # Custom transformer, defined in custom/transformers.py
    - name: "ingestion_timestamp"
      function: "add_ingestion_timestamp"
      params:
        column_name: ingested_at
      order: 2
```

A richer example, showing a mapping-file enrichment and string cleanup chained before the calculation:

```yaml
"*_sales_*":
  transforms:
    - name: "enrich_with_mapping"
      function: "enrich_with_mapping"
      params:
        mapping_file: "D.static.mappings.product_mapping"
        df_join_column:
          - "product_id"
        mapping_key_column:
          - "product_id"
        columns_to_add:
          - "product_name"
          - "brand"
      order: 1

    - name: "strings_strip_whitespace"
      function: "strings_strip_whitespace"
      params:
        columns: ["product_name"]
        strip_whitespace: true
      order: 2

    - name: "total_sales_calculation"
      function: "multiply_columns"
      params:
        columns_to_multiply:
          - "price"
          - "quantity"
        output_column: "total_sales"
      order: 3
```

### Important Notes

- `params` are passed as `**kwargs` to the transformer function (along with `df` and `messages`).
- DataFacility paths like `"D.static.mappings.product_mapping"` can be used as parameter values — the transformer function resolves them via `D.get_node()`.
- If **any** transform fails, the file is **not saved** and reported as failed.

See [[Writing Transformers]] for the list of built-in transformers and how to create your own.

---

## Dispatch Registry Format

Used by the `FileDispatcher` processor (step 3 in the example project).

```yaml
"<pattern>": "<target_subfolder>"
```

This is the simplest format: pattern → destination folder name.

### Example: `3_dispatcher.yaml` (as scaffolded by `pangolin init`)

```yaml
"*sales*": "SALES"
```

Files matching `*sales*` are copied/moved into a `SALES/` subfolder under the output folder. Add more patterns for more categories, e.g.:

```yaml
"*sales*": "SALES"
"*inventory*": "INVENTORY"
"*FR_*": "FR"
"*US_*": "US"
```

---

## Non-Standard Registry Formats (Custom Processors)

The three formats above are conventions followed by pangolin's three built-in processors — nothing in the engine enforces them. A custom processor (see [[Creating a New Processor]]) can define its own registry shape entirely. The example project's audit step (`2_audit.yaml`, consumed by `custom/processors/example_processor.py`'s `AuditProcessor`) is one such case:

```yaml
"*sales*":
  count_nulls: true
```

`AuditProcessor` reads `self.registry[pattern]` itself and interprets `count_nulls` however it wants — `BaseProcessor` only handles pattern matching and file I/O, not the shape of what's under each pattern.

---

## Creating a New Registry

1. Create a YAML file in `config/registries/` following the naming convention `<N>_<name>.yaml`
2. Choose the format based on the processor type you'll use
3. Add the appropriate glob patterns as keys
4. Reference the registry path when creating the processor in your pipeline file (e.g. `pipelines/example_pipeline.py`)

See [[Pipeline Configuration]] for how to wire a new step into the pipeline.

---

Next: [[Writing Validators]] →
