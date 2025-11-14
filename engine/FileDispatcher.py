"""
FileDispatcher Class:
Dispatches files to subfolders based on pattern matching.
Inherits from BaseProcessor for file operations.
"""

import os
import shutil
from engine.BaseProcessor import BaseProcessor
from engine.Reporter import Reporter
from pathlib import Path
from typing import List, Tuple
from config.settings import get_settings
S = get_settings()


class FileDispatcher(BaseProcessor):
    def __init__(self, name: str, registry_path: str, report_folder: str, input_folder: str, output_folder: str = None, rm_from_input_folder: bool = False):
        """
        Initialize the FileDispatcher.
        
        Args:
            name: Step name for identification
            registry_path: Path to the registry file
            report_folder: Dot-notation path to report folder in data structure
            input_folder: Dot-notation path to input folder
            output_folder: Dot-notation path to output folder
            rm_from_input_folder: Whether to remove files from input after processing
        """
        super().__init__(name, registry_path, input_folder, output_folder)
        self.reporter = Reporter(report_folder, step_name=name)
        self.rm_from_input = rm_from_input_folder

    def get_input_files(self) -> List[Tuple[str, str]]:
        """Override to allow empty input for dispatcher (first step in pipeline)."""
        file_paths = []
        items = self.input_node.list('*')
        # Only list files, not directories - dispatcher only processes root files
        for item in items:
            if item.is_file():
                file_paths.append((str(item), item.name))
        return file_paths if file_paths else []

    def execute(self, rm_from_input_folder: bool = None):
        """
        Dispatch files based on the keyword mapping.
        """
        if rm_from_input_folder is not None:
            self.rm_from_input = rm_from_input_folder
            
        file_paths = self.get_input_files()
        
        if not file_paths:
            raise FileNotFoundError(f"No files found in input folder '{self.input_node.path}'. If this is unexpected, please check your input data location.")

        processed_count = 0
        for file_path, filename in file_paths:
            
            # Match file to pattern
            matched_pattern, match_error = self.match_file(file_path)

            if match_error:
                if not S.DISABLE_REPORTS:
                    # Pass filename as relative path to maintain structure
                    self.reporter.write_report(filename, [match_error])
                continue
            
            # Get target folder from registry
            target_folder = self.registry.get(matched_pattern, matched_pattern)
            
            # Create target path directly using output_node's path
            # Instead of looking for a child node, create the subfolder directly
            target_dir = self.output_node.path / target_folder
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / filename
            
            # Move or copy file
            if self.rm_from_input:
                shutil.move(file_path, target_path)
                print(f"Moved '{filename}' to '{target_path}'")
            else:
                shutil.copy2(file_path, target_path)
                print(f"Copied '{filename}' to '{target_path}'")
            
            processed_count += 1
        
        print(f"Dispatcher processed {processed_count} files.")
