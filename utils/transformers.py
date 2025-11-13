import polars as pl
from typing import List



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


############################################################################################################
# Dictionary to map transformer names to functions - All new transformers must be added here
TRANSFORMERS_DICT = {
    "strings_strip_whitespace": strings_strip_whitespace,
    "case_transform": case_transform,
    "blank": blank,
}