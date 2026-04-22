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

Used by the `Validator` processor (e.g. steps 0, 3, 4 in the default configuration).

```yaml
"<pattern>":
  validators:
    <validator_function_name>: <params_or_null>
    <validator_function_name>: <params_or_null>
```

### Example: `0_raw_validation.yaml`

```yaml
"*sales*":
  validators:
    is_empty_dataframe:           # no params → null
    required_columns:             # params = list of column names
      - product_id
      - price
      - store_id
      - quantity
    additional_columns:
      - product_id
      - price
      - store_id
      - quantity
    validate_product_ids:         # params = dict
      product_id_column: product_id
      product_id_master_column: product_id
```

### Parameter Passing

The YAML value after the function name becomes the `params` argument:

| YAML | Python `params` |
|------|-----------------|
| `is_empty_dataframe:` (empty) | `None` — function called as `func(df, messages)` |
| `required_columns:\n  - col_a\n  - col_b` | `["col_a", "col_b"]` |
| `validate_product_ids:\n  product_id_column: product_id` | `{"product_id_column": "product_id"}` |
| `value_range:\n  price:\n    min: 0\n    max: 1000` | `{"price": {"min": 0, "max": 1000}}` |

### Example: `4_cross_validation.yaml`

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
      sellout_price:
        min: 0
```

See [[Writing Validators]] for the list of built-in validators and how to create your own.

---

## Transformation Registry Format

Used by the `DataTransformer` processor (e.g. step 2 in the default configuration).

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

### Example: `2_transform_registry.yaml`

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
          - "product_version"
          - "brand"
      order: 1

    - name: "strings_strip_whitespace"
      function: "strings_strip_whitespace"
      params:
        columns: ["product_name", "product_version"]
        strip_whitespace: true
      order: 2

    - name: "case_transform"
      function: "case_transform"
      params:
        columns: ["product_version", "product_name", "brand"]
        to_lowercase: false
        to_uppercase: true
      order: 3

    - name: "total_sales_calculation"
      function: "multiply_columns"
      params:
        columns_to_multiply:
          - "sellout_price"
          - "quantity"
        output_column: "total_sales"
      order: 4
```

### Important Notes

- `params` are passed as `**kwargs` to the transformer function (along with `df` and `messages`).
- DataFacility paths like `"D.static.mappings.product_mapping"` can be used as parameter values — the transformer function resolves them via `D.get_node()`.
- If **any** transform fails, the file is **not saved** and reported as failed.

See [[Writing Transformers]] for the list of built-in transformers and how to create your own.

---

## Dispatch Registry Format

Used by the `FileDispatcher` processor (e.g. steps 1, 5 in the default configuration).

```yaml
"<pattern>": "<target_subfolder>"
```

This is the simplest format: pattern → destination folder name.

### Example: `1_dispatcher.yaml`

```yaml
"*sales*": "SALES"
"*inventory*": "INVENTORY"
"test_*.csv": "test_data"
```

Files matching `*sales*` are copied/moved into a `SALES/` subfolder under the output folder.

### Example: `5_dispatcher.yaml`

```yaml
"*FR_*": "FR"
"*US_*": "US"
```

Files are dispatched by region into `FR/` and `US/` subfolders.

---

## Creating a New Registry

1. Create a YAML file in `config/registries/` following the naming convention `<N>_<name>.yaml`
2. Choose the format based on the processor type you'll use
3. Add the appropriate glob patterns as keys
4. Reference the registry path when creating the processor in `main.py`

See [[Pipeline Configuration]] for how to wire a new step into the pipeline.

---

Next: [[Writing Validators]] →
