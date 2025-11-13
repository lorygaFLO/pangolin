"""
BaseProcessor Class:
Base class for all pipeline processors. Provides:
- Integration with DataFacility for file operations
- Pattern matching against registry
- Common file processing functionality
"""

import os
import fnmatch
import polars as pl
from typing import Dict, List, Tuple, Optional, Any
from config.settings import get_settings
import yaml
from engine.data_facility import get_project_data
from pathlib import Path
S = get_settings()


class BaseProcessor:
    def __init__(self, name: str, registry_path: str, input_folder: str, output_folder: str = None):
        """
        Initialize the BaseProcessor.

        Args:
            name: Step name for identification
            registry_path: Path to the registry file
            input_folder: Name of input folder in data structure
            output_folder: Name of output folder in data structure

        Raises:
            ValueError: If required parameters are not provided
        """
        if not name:
            raise ValueError("Step name must be provided")
        if not registry_path:
            raise ValueError("registry_path must be provided")
        if not input_folder:
            raise ValueError("input_folder must be provided")
        
        S = get_settings()
        self.name = name
        self.output_folder = output_folder or name  # Default to step name
        
        # Initialize DataFacility
        self.D = get_project_data()
        
        # Get registry
        self.registry_path = registry_path
        self.registry = self.get_registry(registry_path)
        
        # Setup input/output paths using DataFacility
        self.input_node = self._get_node_by_path(input_folder)
        self.output_node = self._get_node_by_path(self.output_folder) if self.output_folder else None
        
        # Ensure input folder exists
        if not self.input_node.path.exists():
            self.input_node.path.mkdir(parents=True, exist_ok=True)
            
        # Ensure output folder exists if specified
        if self.output_node and not self.output_node.path.exists():
            self.output_node.path.mkdir(parents=True, exist_ok=True)

    def _get_node_by_path(self, path_str: str):
        """Navigate to a node in DataFacility using dot notation."""
        parts = path_str.split('.')
        node = self.D
        for part in parts:
            node = getattr(node, part)
        return node

    def get_registry(self, file_path: str = 'config/registry.yaml') -> dict:
        """Load registry configuration from YAML file."""
        if not os.path.isabs(file_path):
            file_path = S.BASEPATH / file_path  # S.BASEPATH is already a Path
        
        with open(file_path, 'r') as file:
            registry = yaml.safe_load(file)
        
        return registry

    def match_file(self, relative_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Match a file path to patterns in registry.
        Uses the relative path including subfolder structure for pattern matching.

        Returns:
            Tuple of (matched_pattern, error_message)
        """
        # Use the full relative path for matching (including subfolders)
        matches = [pattern for pattern in self.registry.keys() 
                  if fnmatch.fnmatch(relative_path, pattern)]
        
        if len(matches) > 1:
            return None, f"Multiple matches found for {relative_path}: {matches}"
        elif matches:
            return matches[0], None
        else:
            return None, f"No matching pattern found in registry for: {relative_path}"

    def get_input_files(self, include_subfolders: bool = True) -> List[Tuple[str, str]]:
        """
        Get all files from input folder using DataFacility.
        
        Returns:
            List of tuples (full_path, relative_path) where relative_path maintains folder structure
        """
        file_paths = []
        
        if include_subfolders:
            # Search recursively maintaining relative paths
            for item in self.input_node.path.rglob('*'):
                if item.is_file():
                    # Calculate relative path from input folder
                    relative_path = item.relative_to(self.input_node.path)
                    file_paths.append((str(item), str(relative_path)))
        else:
            # Only search in the direct folder
            items = self.input_node.list('*')
            for item in items:
                if item.is_file():
                    relative_path = item.name  # Just the filename
                    file_paths.append((str(item), str(relative_path)))
        
        if not file_paths:
            # This is an error for most processors - subclasses can override
            raise FileNotFoundError(
                f"No files found in input folder '{self.input_node.path}'. "
                f"This indicates a pipeline configuration error. "
                f"Please check previous steps' output folders."
            )
        return file_paths

    def read_file(self, file_path: str) -> Tuple[Optional[pl.DataFrame], List[str]]:
        """
        Read a file and return data with any messages.
        
        Returns:
            Tuple of (dataframe, messages_list)
        """
        messages = []
        try:
            # Convert string path to Path object
            file_path_obj = Path(file_path)
            
            # Create a temporary node for the file
            file_node = type('FileNode', (), {
                'path': file_path_obj,
                'file_format': self._infer_format(str(file_path_obj)),
                'is_file': True
            })()
            
            # Read based on format
            if file_node.file_format == 'csv':
                data = pl.read_csv(file_path_obj, separator=S.CSV_DELIMITER)
            elif file_node.file_format == 'parquet':
                data = pl.read_parquet(file_path_obj)
            else:
                raise ValueError(f"Unsupported file format: {file_node.file_format}")
            
            return data, messages
            
        except Exception as e:
            messages.append(f"Error reading file {file_path}: {str(e)}")
            return None, messages

    def _infer_format(self, filename: str) -> str:
        """Infer format from file extension."""
        ext = os.path.splitext(filename)[1].lower()
        format_map = {
            '.csv': 'csv',
            '.parquet': 'parquet',
            '.pq': 'parquet',
        }
        return format_map.get(ext, 'unknown')

    def write_file(self, data: pl.DataFrame, relative_path: str, folder_node=None):
        """
        Write data to output using DataFacility, preserving folder structure.
        
        Args:
            data: DataFrame to write
            relative_path: Relative path including subfolder structure
            folder_node: Optional specific folder node (defaults to self.output_node)
        """
        output_node = folder_node or self.output_node
        if not output_node:
            raise ValueError("No output folder specified")
        
        # Create output path preserving folder structure
        output_path = output_node.path / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write based on format
        file_format = self._infer_format(str(relative_path))
        if file_format == 'csv':
            data.write_csv(output_path, separator=S.CSV_DELIMITER)
        elif file_format == 'parquet':
            data.write_parquet(output_path)
        else:
            raise ValueError(f"Unsupported output format: {file_format}")
        
        return output_path

    def process_files(self, file_paths: List[Tuple[str, str]] = None) -> Tuple[Dict[str, Tuple[pl.DataFrame, str, str]], Dict[str, List[str]]]:
        """
        Process files with pattern matching.
        
        Returns:
            Tuple of (processed_files_dict, error_files_dict)
            processed_files_dict: {full_path: (dataframe, matched_pattern, relative_path)}
        """
        if file_paths is None:
            file_paths = self.get_input_files()

        processed_files = {}
        error_files = {}
        
        for full_path, relative_path in file_paths:
            # Read file
            data, read_messages = self.read_file(full_path)
            if data is None:
                error_files[full_path] = read_messages
                continue

            # Match pattern using relative path
            matched_pattern, match_error = self.match_file(relative_path)
            if matched_pattern:
                processed_files[full_path] = (data, matched_pattern, relative_path)
            else:
                error_files[full_path] = [match_error] if match_error else []

        return processed_files, error_files

    def execute(self, **kwargs):
        """To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement execute method")