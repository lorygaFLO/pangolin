import pandas as pd
import polars as pl
import os
from config.settings import *
from typing import Optional, Union, List
import pandas as pd
import polars as pl
import duckdb
from config.settings import get_settings

class DataHandler:
    """
    Universal data reader with unified interface.
    Supports pandas, polars, and duckdb backends.
    Always returns pandas DataFrames for compatibility.
    """
    
    def __init__(self, folder_path: str = None, delimiter: str = None):
        self.S = get_settings()
        self.folder_path = folder_path or self.S.PATH_INPUT
        self.delimiter = delimiter or self.S.CSV_DELIMITER
        self.chunk_size = self.S.DUCKDB_CHUNK_SIZE
        
        # Validate backend
        if self.S.BACKEND_ENGINE not in ['pandas', 'polars', 'duckdb']:
            raise ValueError(f"Invalid BACKEND_ENGINE: {self.S.BACKEND_ENGINE}. Must be 'pandas', 'polars', or 'duckdb'")
        
        print(f"DataReader initialized with {self.S.BACKEND_ENGINE} backend")
    
    def read_csv(self, file_path: str) -> pd.DataFrame:
        """Read CSV file using configured backend"""
        if self.S.BACKEND_ENGINE == 'pandas':
            return pd.read_csv(file_path, delimiter=self.delimiter)
        
        elif self.S.BACKEND_ENGINE == 'polars':
            df_pl = pl.read_csv(file_path, separator=self.delimiter)
            return df_pl.to_pandas()
        
        elif self.S.BACKEND_ENGINE == 'duckdb':
            con = duckdb.connect(':memory:')
            try:
                query = f"""
                SELECT * FROM read_csv_auto('{file_path}', 
                    delim='{self.delimiter}', 
                    header=true)
                """
                return con.execute(query).df()
            finally:
                con.close()
    
    def read_parquet(self, file_path: str) -> pd.DataFrame:
        """Read Parquet file using configured backend"""
        if self.S.BACKEND_ENGINE == 'pandas':
            return pd.read_parquet(file_path)
        
        elif self.S.BACKEND_ENGINE == 'polars':
            df_pl = pl.read_parquet(file_path)
            return df_pl.to_pandas()
        
        elif self.S.BACKEND_ENGINE == 'duckdb':
            con = duckdb.connect(':memory:')
            try:
                query = f"SELECT * FROM read_parquet('{file_path}')"
                return con.execute(query).df()
            finally:
                con.close()
    
    def read_file(self, file_path: str):
        """
        Read file based on extension.
        Returns pandas DataFrame regardless of backend.
        """
        messages = []
        try:
            if file_path.endswith('.csv'):
                return self.read_csv(file_path), messages
            elif file_path.endswith('.parquet'):
                return self.read_parquet(file_path), messages
            else:
                raise ValueError(f"Unsupported file format: {file_path}. Only CSV and Parquet are supported.")
        except Exception as e:
            return None, [f"Error reading file {file_path}: {str(e)}"]


    def read_all_files(self) -> List[str]:
        """Get list of all supported file paths in folder"""
        file_paths = []
        for root, _, files in os.walk(self.folder_path):
            for file_name in files:
                if file_name.lower().endswith(('.csv', '.parquet')):
                    file_path = os.path.join(root, file_name)
                    file_paths.append(file_path)
        return file_paths

    def to_csv(self, df: pd.DataFrame, file_path: str) -> None:
        """
        Write DataFrame to a CSV file using the configured backend.
        """
        if self.S.BACKEND_ENGINE == 'pandas':
            df.to_csv(file_path, index=False, sep=self.delimiter)
        elif self.S.BACKEND_ENGINE == 'polars':
            df = pl.from_pandas(df)
            df.write_csv(file_path, separator=self.delimiter)
        elif self.S.BACKEND_ENGINE == 'duckdb':
            con = duckdb.connect(':memory:')
            try:
                con.register('df', df)
                query = f"COPY df TO '{file_path}' (DELIMITER '{self.delimiter}', HEADER TRUE)"
                con.execute(query)
            finally:
                con.close()

    def to_parquet(self, df: pd.DataFrame, file_path: str) -> None:
        """
        Write DataFrame to a Parquet file using the configured backend.
        """
        if self.S.BACKEND_ENGINE == 'pandas':
            df.to_parquet(file_path, index=False)
        elif self.S.BACKEND_ENGINE == 'polars':
            df = pl.from_pandas(df)
            df.write_parquet(file_path)
        elif self.S.BACKEND_ENGINE == 'duckdb':
            con = duckdb.connect(':memory:')
            try:
                con.register('df', df)
                query = f"COPY df TO '{file_path}' (FORMAT PARQUET)"
                con.execute(query)
            finally:
                con.close()
    
    def write_file(self, df, file_path: str, file_format: str = 'csv'):
        """
        Write DataFrame to a file in the specified format.
        Supports 'csv' and 'parquet' formats.
        """        

        if file_format == 'csv':
            df = self.to_csv(file_path)
            return df
        elif file_format == 'parquet':
            df = self.to_parquet(file_path)
            return df
        else:
            raise ValueError(f"Unsupported file format: {file_format}")
        

    def copy(self, data):
        """
        Create a copy of the data using the configured backend.
        Supports pandas DataFrame and polars DataFrame as input.
        """
        if self.S.BACKEND_ENGINE == 'pandas':
            if isinstance(data, pd.DataFrame):
                modified_data = data.copy()
        elif self.S.BACKEND_ENGINE == 'polars':
            modified_data = data.clone()
        elif self.S.BACKEND_ENGINE == 'duckdb':
            con = duckdb.connect(':memory:')
            try:
                con.register('data', data)
                query = "SELECT * FROM data"
                modified_data = con.execute(query).df()
            finally:
                con.close()
        else:
            raise ValueError(f"Unsupported BACKEND_ENGINE: {self.S.BACKEND_ENGINE}")
        return modified_data