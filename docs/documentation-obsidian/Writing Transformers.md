# Writing Transformers

Transformers are Python functions that take a Polars DataFrame, apply a modification, and return the modified DataFrame. Built-in transformers ship with the library in `pangolin/utils/transformers.py`; project-specific ones live in your project's `custom/transformers.py`. Both are registered automatically via the same decorator.

---

## The Transformer Contract

Every transformer **must** follow this signature:

```python
def my_transformer(df, messages=None, **kwargs) -> pl.DataFrame:
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `df` | `polars.DataFrame` | The input data |
| `messages` | `list` (optional) | Mutable list — append human-readable strings describing operations performed |
| `**kwargs` | varies | Additional parameters from the registry YAML `params` section |

### Return Value

- Always return a `polars.DataFrame` — never return `None`.
- On error, raise an exception. The `DataTransformer` processor catches it and marks the transform as failed.
- If **any** transform in the chain fails, the entire output file is **not saved**.

---

## Registering a Transformer

Decorate the function with `@register_transformer`:

```python
from pangolin.utils.transformers import register_transformer

@register_transformer
def my_transformer(df, messages=None, **kwargs) -> pl.DataFrame:
    # ... transformation logic ...
    return df
```

This adds the function to `TRANSFORMERS_DICT` under its `__name__`.

> [!important]
> Do **not** add entries to `TRANSFORMERS_DICT` manually. The decorator handles registration.

---

## Step-by-Step: Creating a New Transformer

### 1. Write the Function in `custom/transformers.py`

```python
@register_transformer
def rename_columns(
    df: pl.DataFrame,
    column_mapping: dict,
    messages: list = None,
) -> pl.DataFrame:
    """
    Rename columns based on a mapping dictionary.
    
    Parameters:
        df: Input DataFrame
        column_mapping: Dict of {old_name: new_name}
        messages: Optional message list
    """
    result_df = df.rename(column_mapping)
    
    if messages is not None:
        renamed = [f"{old} → {new}" for old, new in column_mapping.items()]
        messages.append(
            f"rename_columns: Renamed {len(renamed)} columns: {', '.join(renamed)}"
        )
    
    return result_df
```

### 2. Reference It in a Registry YAML

```yaml
# config/registries/1_transform.yaml
"*_sales_*":
  transforms:
    - name: "rename_columns"
      function: "rename_columns"
      params:
        column_mapping:
          old_column_name: "new_column_name"
          sellout_price: "unit_price"
      order: 5
```

### How Parameters Flow

The `params` dict from the YAML is unpacked as `**kwargs`:

```python
# The DataTransformer calls:
transformer_func(
    modified_data,
    messages=messages,
    **transform["params"]  # column_mapping={"old_column_name": "new_column_name", ...}
)
```

So each key in `params` must match a parameter name in your function signature.

---

## Built-in Transformers

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `enrich_with_mapping` | `mapping_file`, `df_join_column`, `mapping_key_column`, `columns_to_add` | Left-joins a mapping file onto the DataFrame to add new columns |
| `strings_strip_whitespace` | `columns`, `strip_whitespace` | Strips leading/trailing whitespace from string columns |
| `case_transform` | `columns`, `to_uppercase`, `to_lowercase` | Converts string columns to upper or lower case |
| `multiply_columns` | `columns_to_multiply`, `output_column` | Creates a new column as the product of multiple columns |
| `sum_columns` | `columns_to_sum`, `output_column` | Creates a new column as the sum of multiple columns |
| `subtract_columns` | `columns_to_subtract`, `output_column` | Creates a new column as the difference of multiple columns |
| `divide_columns` | `columns_to_divide`, `output_column` | Creates a new column as the quotient of multiple columns |
| `drop_columns` | `columns` | Drops the listed columns |
| `save_inventory_snapshot` | `snapshot_file`, `product_id_column` | Appends distinct product IDs to a versioned snapshot file |
| `blank` | (none) | No-op transformer. Returns the DataFrame unchanged. |

> [!note]
> Check the exact parameter names in `pangolin/utils/transformers.py` before using one — this table is a quick reference, not the source of truth.

---

## Using DataFacility in Transformers

DataFacility (`D`) is available at module level. You can reference DataFacility paths as string parameters in the registry:

```yaml
params:
  mapping_file: "D.static.mappings.product_mapping"
```

Then resolve it in the transformer:

```python
from pangolin.engine.DataFacility import DataFacility
D = DataFacility()

@register_transformer
def my_transformer(df, mapping_file, messages=None):
    node = D.get_node(mapping_file)
    if not node.exists():
        raise FileNotFoundError(f"File not found: {mapping_file}")
    
    mapping_df = node.read()
    # ... use mapping_df
    return df
```

---

## Transform Execution Order

Transforms are sorted by the `order` field (ascending) and executed sequentially. The output of one transform becomes the input of the next:

```
Input DataFrame
    │
    ▼ order 1: enrich_with_mapping
    │
    ▼ order 2: strings_strip_whitespace
    │
    ▼ order 3: case_transform
    │
    ▼ order 4: multiply_columns
    │
Output DataFrame → saved to disk
```

If any transform raises an exception, the chain stops and the file is marked as failed.

---

## Tips

- **Always clone** the DataFrame before modifying if you want to preserve immutability: `result_df = df.clone()`
- **Always append to `messages`** — messages are what get written to the report file and help with debugging.
- Use descriptive `name` fields in the registry YAML — they appear in transform logs and reports.
- The `order` field controls execution sequence. Use gaps (1, 10, 20) to make it easy to insert new transforms later.
- Keep transformers **focused** — one transformation per function. Compose complex pipelines through the registry file.

---

Next: [[Creating a New Processor]] →
