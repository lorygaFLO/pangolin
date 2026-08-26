"""
BackupRestore Class:
Backs up all files from the input folder to the backup folder,
organized in timestamped subfolders (run_id).
Supports restoring files from a previous backup run.
"""

from typing import List, Tuple, Optional
from config.settings import get_settings
from config.run_context import RunContext
from engine.DataFacility import get_project_data
from engine.common.logger import ProcessorLogger
from engine.common.exceptions import NoInputFilesError
from utils.fs_wrapper import FSWrapper


class BackupRestore:
    def __init__(self, CTX: RunContext, name: str, input_folder: str, output_folder: str = None):
        """
        Initialize the BackupRestore processor.

        Args:
            CTX: RunContext with runtime state (RUN_ID)
            name: Step name for identification
            input_folder: Dot-notation path to input folder in data structure
            output_folder: Dot-notation path to backup folder in data structure
        """
        if not name:
            raise ValueError("Step name must be provided")
        if not input_folder:
            raise ValueError("input_folder must be provided")

        S = get_settings()
        self.S = S
        self.CTX = CTX
        self.name = name
        self.log = ProcessorLogger(name)

        self.fs = FSWrapper(
            protocol=getattr(S, "FS_PROTOCOL", "file"),
            **getattr(S, "FS_OPTIONS", {})
        )

        self.D = get_project_data(run_id=CTX.RUN_ID)

        self.input_folder = input_folder
        self.input_node = self._get_node_by_path(input_folder)
        self.output_node = self._get_node_by_path(output_folder or "backup")

        if not self.fs.exists(str(self.input_node.path)):
            self.fs.makedirs(str(self.input_node.path), exist_ok=True)

    def _get_node_by_path(self, path_str: str):
        """Navigate to a node in DataFacility using dot notation."""
        parts = path_str.split('.')
        node = self.D
        for part in parts:
            node = getattr(node, part)
        return node

    def _get_backup_base_path(self) -> str:
        """Get the parent backup folder path (without run_id timestamp)."""
        # output_node.path already includes the run_id due to _timestamped: true
        # We need the parent to access other run_id subfolders
        return self.fs.dirname(str(self.output_node.path))

    def get_input_files(self) -> List[Tuple[str, str]]:
        """
        Get all files from input folder recursively.

        Returns:
            List of tuples (full_path, relative_path).
        """
        file_paths = []
        for item in self.fs.glob(self.fs.join(str(self.input_node.path), '**')):
            if self.fs.isfile(item):
                relative_path = self.fs.relpath(item, str(self.input_node.path))
                file_paths.append((item, relative_path))
        return file_paths

    def execute(self, clear_input: bool = False):
        """
        Back up all files from input folder to backup folder,
        preserving the original directory structure.

        Args:
            clear_input: If True, empty the input folder after backup.
        """
        file_paths = self.get_input_files()

        if not file_paths:
            raise NoInputFilesError(self.name, str(self.input_node.path))

        backup_base = str(self.output_node.path)

        for full_path, relative_path in file_paths:
            target_path = self.fs.join(backup_base, relative_path)
            target_dir = self.fs.dirname(target_path)
            self.fs.makedirs(target_dir, exist_ok=True)
            self.fs.copy(full_path, target_path)

        self.log.info(f"Backup complete: {len(file_paths)} file(s) copied to '{backup_base}'")

        if clear_input:
            self.clear_input_folder()

    def clear_input_folder(self):
        """Remove all files from the input folder."""
        input_path = str(self.input_node.path)
        for item in self.fs.glob(self.fs.join(input_path, '**')):
            if self.fs.isfile(item):
                self.fs.remove(item)
        self.log.info(f"Input folder cleared: '{input_path}'")

    def restore(self, backup_run_id: str):
        """
        Restore files from a previous backup into the input folder.

        Args:
            backup_run_id: The run_id (timestamp subfolder) to restore from.

        Raises:
            FileNotFoundError: If the specified backup folder does not exist.
            NoInputFilesError: If the backup folder is empty.
        """
        backup_base = self._get_backup_base_path()
        source_path = self.fs.join(backup_base, backup_run_id)

        if not self.fs.exists(source_path):
            raise FileNotFoundError(
                f"Backup folder not found: '{source_path}'. "
                f"Available backups: {self._list_available_backups()}"
            )

        file_paths = []
        for item in self.fs.glob(self.fs.join(source_path, '**')):
            if self.fs.isfile(item):
                relative_path = self.fs.relpath(item, source_path)
                file_paths.append((item, relative_path))

        if not file_paths:
            raise NoInputFilesError(self.name, source_path)

        input_path = str(self.input_node.path)
        for full_path, relative_path in file_paths:
            target_path = self.fs.join(input_path, relative_path)
            target_dir = self.fs.dirname(target_path)
            self.fs.makedirs(target_dir, exist_ok=True)
            self.fs.copy(full_path, target_path)

        self.log.info(
            f"Restore complete: {len(file_paths)} file(s) restored from backup '{backup_run_id}' to '{input_path}'"
        )

    def _list_available_backups(self) -> List[str]:
        """List available backup run_id folders."""
        backup_base = self._get_backup_base_path()
        if not self.fs.exists(backup_base):
            return []
        return [
            self.fs.basename(d)
            for d in self.fs.listdir(backup_base)
            if self.fs.isdir(self.fs.join(backup_base, d))
        ]
