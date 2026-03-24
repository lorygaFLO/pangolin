"""
transformers.py
===============
Collection of transformer functions used by the pipeline engine.

CONVENTION — Every transformer MUST follow this signature:

    def my_transformer(df, messages=None, **kwargs) -> polars.DataFrame:

Mandatory parameters:
    df        (polars.DataFrame): The dataframe to transform.
    messages  (list, optional)  : Mutable list; append human-readable strings
                                  describing the operations performed.

Additional parameters depend on the specific transformer (e.g. column names,
configuration values).  They must all have sensible defaults where possible.

Return value:
    polars.DataFrame — the transformed dataframe (may be a modified clone or
    the original, depending on the operation).  Never return None.

Registration — decorate every new transformer with @register_transformer if you want to use it for transformations:

    @register_transformer
    def my_transformer(df, ..., messages=None) -> pl.DataFrame:
        ...

    This automatically adds the function to TRANSFORMERS_DICT under its __name__.
    Do NOT add entries to TRANSFORMERS_DICT manually.
"""
import polars as pl
from typing import List, Union
from engine.DataFacility import DataFacility
D = DataFacility()

TRANSFORMERS_DICT = {}


def register_transformer(func):
    """Decorator that automatically registers a transformer function in TRANSFORMERS_DICT."""
    TRANSFORMERS_DICT[func.__name__] = func
    return func


@register_transformer
def enrich_with_mapping(
    df: pl.DataFrame,
    mapping_file: str,  # Now accepts path like "static.mapping.product_mapping"
    df_join_column: Union[str, List[str]],  # More descriptive: column(s) in the DataFrame to join on
    mapping_key_column: Union[str, List[str]],  # More descriptive: key column(s) in the mapping to join on
    columns_to_add: List[str],  # More descriptive: columns to add from the mapping
    messages: list = None,
) -> pl.DataFrame:
    """
    Enrich the DataFrame with additional columns from a mapping file.

    Parameters:
    df: Input DataFrame (polars)
    mapping_file: DataFacility path (e.g. "static.mapping.product_mapping")
    df_join_column: Column(s) in the DataFrame to join on
    mapping_key_column: Column(s) in the mapping file to join on
    columns_to_add: List of columns to add from the mapping
    messages: Optional list to append messages
    """
    # Get the DataFacility node passed in the parameters
    mapping_node = D.get_node(mapping_file)
    
    # Check if it exists
    if not mapping_node.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_file}")
    
    # Ensure join columns are lists for consistency
    if isinstance(df_join_column, str):
        df_join_column = [df_join_column]
    if isinstance(mapping_key_column, str):
        mapping_key_column = [mapping_key_column]
    
    # Read the mapping file
    mapping_df = mapping_node.read()
    
    # Perform the join between the DataFrame and the mapping file
    enriched_df = df.join(
        mapping_df.select(mapping_key_column + columns_to_add),
        left_on=df_join_column,
        right_on=mapping_key_column,
        how="left"
    )
    
    # Simple report on unmatched records
    if messages is not None:
        # Check how many records didn't get matched (first added column will be null)
        first_added_column = columns_to_add[0]
        unmatched_count = enriched_df[first_added_column].null_count()
        total_count = len(enriched_df)
        
        if unmatched_count > 0:
            # Get a few examples of unmatched records
            unmatched_examples = enriched_df.filter(
                pl.col(first_added_column).is_null()
            ).select(df_join_column).unique().head(3)
            
            examples_str = ", ".join([
                str(row) for row in unmatched_examples.iter_rows()
            ])
            
            messages.append(
                f"{enrich_with_mapping.__name__}: Enriched with {mapping_file}. "
                f"Unmatched records: {unmatched_count}/{total_count}. "
                f"Examples: {examples_str}"
            )
        else:
            messages.append(
                f"{enrich_with_mapping.__name__}: Successfully enriched all records with {mapping_file}."
            )
    
    return enriched_df


@register_transformer
def strings_strip_whitespace(
    df: pl.DataFrame, 
    columns: List[str], 
    strip_whitespace: bool = True, 
    messages: list = None,
) -> pl.DataFrame:
    """
    Clean string columns by applying various transformations.
    
    Parameters:
    df: Input DataFrame
    messages: list with messages to print
    columns: List of column names containing strings
    strip_whitespace: Whether to strip leading/trailing whitespace
    
    Returns:
    DataFrame with cleaned strings
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("df must be polars DataFrame")
    
    result_df = df.clone()
    
    if strip_whitespace:
        for column in columns:
            if column in result_df.columns:
                result_df = result_df.with_columns(
                    pl.col(column).str.strip_chars().alias(column)
                )

    if messages is not None:
        messages.append(f"{strings_strip_whitespace.__name__}: string columns {columns} transformed.")
    
    return result_df


@register_transformer
def case_transform(
    df: pl.DataFrame, 
    columns: List[str], 
    to_uppercase: bool = False,
    to_lowercase: bool = False,
    messages: list = None
) -> pl.DataFrame:
    """
    Transform string columns to upper or lower case.
    
    Parameters:
    df: Input DataFrame (polars)
    columns: List of column names containing strings
    to_uppercase: Whether to convert strings to uppercase
    to_lowercase: Whether to convert strings to lowercase
    
    Returns:
    DataFrame with transformed strings
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("df must be a polars DataFrame")
    
    if to_uppercase and to_lowercase:
        raise ValueError("Cannot set both to_uppercase and to_lowercase to True")
    
    if not (to_uppercase or to_lowercase):
        raise ValueError("At least one of to_uppercase or to_lowercase must be True")
    
    result_df = df.clone()
    
    for col in columns:
        if col in result_df.columns:
            if to_uppercase:
                result_df = result_df.with_columns(
                    pl.col(col).str.to_uppercase().alias(col)
                )
            if to_lowercase:
                result_df = result_df.with_columns(
                    pl.col(col).str.to_lowercase().alias(col)
                )
    
    if messages is not None:
        messages.append(f"{case_transform.__name__}: string columns {columns} transformed.")

    return result_df


@register_transformer
def blank(df: pl.DataFrame, messages: list = None) -> pl.DataFrame:
    """
    Transform string columns to upper or lower case.
    
    Parameters:
    df: Input DataFrame (pandas or polars)
    columns: List of column names containing strings
    
    Returns:
    DataFrame with transformed strings
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("df must be a polars DataFrame")

    result_df = df.clone()
    
    if messages is not None:
        messages.append(f"{blank.__name__} No operation has been correctly made.")

    return result_df


@register_transformer
def multiply_columns(
        df: pl.DataFrame, 
        columns_to_multiply: List[str], 
        output_column: str, 
        messages: list = None
    ) -> pl.DataFrame:
        """
        Multiply values from multiple columns and store the result in a new column.
        
        Parameters:
        df: Input DataFrame (polars)
        columns_to_multiply: List of column names to multiply
        output_column: Name of the resulting column
        messages: Optional list to append messages
        
        Returns:
        DataFrame with the new column containing the product of input columns
        """
        if not isinstance(df, pl.DataFrame):
            raise TypeError("df must be a polars DataFrame")
        
        if not all(col in df.columns for col in columns_to_multiply):
            raise ValueError("One or more columns to multiply are not present in the DataFrame")
        
        result_df = df.clone()
        
        # Compute the product of the input columns
        product_expr = pl.lit(1)
        for col in columns_to_multiply:
            product_expr *= pl.col(col)
        
        result_df = result_df.with_columns(
            product_expr.alias(output_column)
        )
        
        if messages is not None:
            messages.append(f"{multiply_columns.__name__}: Created column '{output_column}' as the product of {columns_to_multiply}.")
        
        return result_df


@register_transformer
def save_inventory_snapshot(
    df: pl.DataFrame,
    snapshot_file: str,  # DataFacility path (e.g. "static.inventory.product_snapshot")
    product_id_column: str,  # Column name containing product IDs
    messages: list = None
    ) -> pl.DataFrame:
    """
    Save or append distinct product IDs to an inventory snapshot file.
    
    Parameters:
    df: Input DataFrame (polars)
    snapshot_file: DataFacility path for the snapshot file
    product_id_column: Column name containing product IDs
    messages: Optional list to append messages
    
    Returns:
    Original DataFrame (unchanged)
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("df must be a polars DataFrame")
    
    if product_id_column not in df.columns:
        raise ValueError(f"Column '{product_id_column}' not found in DataFrame")
    
    # Get the DataFacility node
    snapshot_node = D.get_node(snapshot_file)
    
    # Get distinct product IDs from current DataFrame
    new_products = df.select(pl.col(product_id_column)).unique()
    
    # Check if snapshot file exists
    if snapshot_node.exists():
        # Read existing snapshot
        existing_snapshot = snapshot_node.read()
        
        # Combine with new products and get distinct values
        combined_snapshot = pl.concat([existing_snapshot, new_products]).unique()
        
        # Save the combined snapshot
        snapshot_node.write(combined_snapshot)
        
        new_count = len(combined_snapshot) - len(existing_snapshot)
        messages.append(
            f"{save_inventory_snapshot.__name__}: Appended {new_count} new product IDs to {snapshot_file}. "
            f"Total products: {len(combined_snapshot)}."
        )
    else:
        # Create new snapshot with distinct product IDs
        snapshot_node.write(new_products)
        
        if messages is not None:
            messages.append(
                f"{save_inventory_snapshot.__name__}: Created new snapshot at {snapshot_file} with new product IDs."
            )
    
    return df

############################################################################################################
# TRANSFORMERS_DICT is automatically populated by the @register_transformer decorator.
# To register a new transformer, simply decorate it with @register_transformer.