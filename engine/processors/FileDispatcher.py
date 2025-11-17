"""
FileDispatcher Class:
Dispatches files to subfolders based on pattern matching.
Inherits from BaseProcessor for file operations.
"""

import os
from engine.processors.BaseProcessor import BaseProcessor
from engine.Reporter import Reporter
from utils.fs_wrapper import FSWrapper
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
        """
        Override to get all files from input folder recursively.
        Allows empty input for dispatcher (first step in pipeline).
        
        Returns:
            List of tuples (full_path, relative_path).
        """
        file_paths = []
        # Use glob to find files recursively
        for item in self.fs.glob(self.fs.join(str(self.input_node.path), '**')):
            if self.fs.isfile(item):
                # Calculate relative path from input folder
                relative_path = self.fs.relpath(item, str(self.input_node.path))
                file_paths.append((item, relative_path))
        return file_paths

    def execute(self, rm_from_input_folder: bool = None):
        """
        Dispatch files based on the keyword mapping.
        """
        if rm_from_input_folder is not None:
            self.rm_from_input = rm_from_input_folder

        file_paths = self.get_input_files()

        if not file_paths:
            print(f"No files to dispatch in '{self.input_node.path}'.")
            return

        processed_count = 0
        for full_path, relative_path in file_paths:
            filename = self.fs.basename(full_path)

            # Match file to pattern using the relative path
            matched_pattern, match_error = self.match_file(relative_path)

            if match_error:
                if not S.DISABLE_REPORTS:
                    # Pass relative_path to reporter to maintain structure in report name
                    self.reporter.write_report(relative_path, [match_error])
                continue

            # Get target folder from registry
            target_folder = self.registry.get(matched_pattern, matched_pattern)

            target_dir = self.fs.join(str(self.output_node.path), target_folder)
            self.fs.makedirs(target_dir, exist_ok=True)
            target_path = self.fs.join(target_dir, filename)

            # Move or copy file
            if self.rm_from_input:
                self.fs.copy(full_path, target_path)
                self.fs.remove(full_path)
                print(f"Moved '{filename}' to '{target_path}'")
            else:
                self.fs.copy(full_path, target_path)
                print(f"Copied '{filename}' to '{target_path}'")

            processed_count += 1

        print(f"Dispatcher processed {processed_count} files.")


