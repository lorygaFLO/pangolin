"""
FileDispatcher Class:
Dispatches files to subfolders based on pattern matching.
Inherits from BaseProcessor for file operations.
"""

from engine.processors.BaseProcessor import BaseProcessor
from engine.reporter import Reporter
from engine.core.exceptions import NoInputFilesError, AllFilesFailedError
from utils.fs_wrapper import FSWrapper
from typing import List, Tuple
from config.settings import get_settings
from config.run_context import RunContext


class FileDispatcher(BaseProcessor):
    def __init__(self, CTX: RunContext, name: str, report_folder: str, input_folder: str, output_folder: str = None, rm_from_input_folder: bool = False):
        """
        Initialize the FileDispatcher.
        
        Args:
            CTX: RunContext with runtime state (RUN_ID)
            name: Step name for identification (must match a node with
                  '_registry' in data_structure.yaml)
            report_folder: Dot-notation path to report folder in data structure
            input_folder: Dot-notation path to input folder
            output_folder: Dot-notation path to output folder
            rm_from_input_folder: Whether to remove files from input after processing
        """
        super().__init__(CTX, name, input_folder, output_folder)
        self.reporter = Reporter(CTX, report_folder, step_name=name)
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
            raise NoInputFilesError(self.name, str(self.input_node.path))

        passed = []
        failed = []
        for full_path, relative_path in file_paths:
            filename = self.fs.basename(full_path)

            # Match file to pattern using the relative path
            matched_pattern, match_error = self.match_file(relative_path)

            if match_error:
                if not self.S.DISABLE_REPORTS:
                    # Pass relative_path to reporter to maintain structure in report name
                    self.reporter.write_report(relative_path, [match_error])
                failed.append(filename)
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
                self.log.info(f"Moved '{filename}' to '{target_path}'")
            else:
                self.fs.copy(full_path, target_path)
                self.log.info(f"Copied '{filename}' to '{target_path}'")

            passed.append(filename)

        # ---- Final summary ----
        total = len(passed) + len(failed)
        self.log.info(f"Dispatch complete: {len(passed)} dispatched, {len(failed)} failed out of {total} files")
        if passed:
            self.log.info("DISPATCHED:\n   - " + "\n   - ".join(passed))
        if failed:
            self.log.warning("FAILED:\n   - " + "\n   - ".join(failed))

        if len(passed) == 0:
            raise AllFilesFailedError(
                f"[{self.name}] All {len(failed)} file(s) failed dispatch."
            )


