# Writing Validators

Validators are Python functions that check a DataFrame against specific rules and return `True` (pass) or `False` (fail). They live in `utils/validators.py` and are automatically registered via a decorator.

---

## The Validator Contract

Every validator **must** follow this signature:

```python
def my_validator(df, messages, params=None) -> bool:
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `df` | `polars.DataFrame` | The data to validate |
| `messages` | `list` | Mutable list — append human-readable strings describing issues found |
| `params` | any (optional) | Extra configuration from the registry YAML. Can be `None`, a list, a dict, or a scalar |

### Return Value

- **`True`** — validation passed
- **`False`** — validation failed (soft failure, pipeline continues to the next validator)
- **`raise ValueError`** — fatal error, pipeline stops for this file (e.g. mandatory columns missing)

---

## Registering a Validator

Decorate the function with `@register_validator`:

```python
from utils.validators import register_validator

@register_validator
def my_validator(df, messages, params=None):
    # ... validation logic ...
    return True
```

This adds the function to `VALIDATORS_DICT` under its `__name__`. The validator is then available for use in any registry YAML file by referencing the function name.

> [!important]
> Do **not** add entries to `VALIDATORS_DICT` manually. The decorator handles registration.

---

## Step-by-Step: Creating a New Validator

### 1. Write the Function in `utils/validators.py`

```python
@register_validator
def no_duplicate_rows(df, messages, params=None):
    """
    Check that the DataFrame has no duplicate rows.
    
    Params (optional):
        List of column names to check. If None, checks all columns.
    """
    columns = params if params else df.columns
    
    duplicates = df.select(columns).is_duplicated()
    dup_count = duplicates.sum()
    
    if dup_count > 0:
        messages.append(
            f"Found {dup_count} duplicate rows based on columns: {columns}"
        )
        return False
    
    return True
```

### 2. Reference It in a Registry YAML

```yaml
# config/registries/3_validation.yaml
"*sales*":
  validators:
    no_duplicate_rows:
      - product_id
      - store_id
      - date
```

Here, `params` will be `["product_id", "store_id", "date"]`.

To call without parameters:

```yaml
    no_duplicate_rows:
```

Here, `params` will be `None`.

That's it — no other changes needed. The `Validator` processor discovers the function from `VALIDATORS_DICT` at runtime.

---

## Built-in Validators

| Function | Parameters | Description |
|----------|-----------|-------------|
| `always_true_validator` | None | Always passes. Useful for testing. |
| `always_false_validator` | None | Always fails. Useful for testing. |
| `is_empty_dataframe` | None | **Raises ValueError** if the DataFrame has 0 rows. |
| `required_columns` | `list[str]` | **Raises ValueError** if any listed column is missing. |
| `additional_columns` | `list[str]` | Returns `False` if there are columns not in the allowed list. |
| `value_range` | `dict[str, {min, max}]` | Returns `False` if values fall outside the specified range. |
| `check_null_values` | `dict` or `list` | Checks for null values and custom null strings (e.g. "NA", "N/A"). |
| `check_hierarchy` | `dict{higher_level_columns, lower_level_columns}` | Verifies that a data hierarchy is consistent. |
| `validate_product_ids` | `dict{product_id_column, product_id_master_column}` | Checks product IDs exist in the static mapping file. |
| `sales_inventory_consistency` | `dict{key_columns}` | Validates sales records have matching inventory records. |

---

## Parameter Examples

### No parameters

```yaml
is_empty_dataframe:
```

Called as: `is_empty_dataframe(df, messages)`

### List parameter

```yaml
required_columns:
  - product_id
  - price
  - quantity
```

Called as: `required_columns(df, messages, ["product_id", "price", "quantity"])`

### Dict parameter

```yaml
value_range:
  price:
    min: 0
    max: 1000
  quantity:
    min: 0
```

Called as: `value_range(df, messages, {"price": {"min": 0, "max": 1000}, "quantity": {"min": 0}})`

### Nested dict parameter

```yaml
check_null_values:
  columns:
    - price
    - quantity
  custom_null_values:
    - ""
    - "NA"
    - "N/A"
```

Called as: `check_null_values(df, messages, {"columns": [...], "custom_null_values": [...]})`

---

## Tips

- **Raise `ValueError`** only for fatal errors that should prevent further validation of the file (e.g. mandatory columns missing, empty file). For non-fatal issues, return `False` and let the pipeline continue checking all validators.
- **Always append to `messages`** when returning `False` — the message list is what gets written to the report file.
- Validators run **in the order they appear** in the registry YAML. If `required_columns` raises `ValueError`, subsequent validators for that file are skipped.
- You can access `DataFacility` from inside a validator — it is already imported at module level as `D`:
  ```python
  from engine.DataFacility import DataFacility
  D = DataFacility()
  ```

---

Next: [[Writing Transformers]] →
