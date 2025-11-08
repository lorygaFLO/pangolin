import os
import shutil
import fnmatch
from engine.data_handler import DataHandler
from engine.reporter import Reporter  
from config.settings import *

class FileDispatcher:
    def __init__(self, name: str, registry_path: str, report_path: str, input_folder_path: str, output_folder_path: str = None, rm_from_input_folder: bool = False):
        """
        Initialize the FileDispatcher.

        :param name: The name of the dispatcher.
        :param registry_path: The path to the registry module for keyword mapping.
        :param report_path: The path to the report file.
        :param input_folder_path: The path to the input folder containing files.
        :param output_folder_path: The path to the output folder where files will be dispatched. Defaults to input folder.
        """
        self.name = name
        self.input_folder_path = input_folder_path
        self.output_folder_path = output_folder_path or name  # Default to step name
        self.handler = DataHandler(registry_path, input_folder_path, output_folder_path)
        self.keyword_mapping = self.handler.get_registry(registry_path)
        self.reporter = Reporter(report_path)
        self.S = get_settings()

    def execute(self, rm_from_input_folder: bool = False):
        """
        Dispatch files based on the keyword mapping.
        """
        files = self.handler.get_input_files()

        for file_path in files:
            filename = os.path.basename(file_path)
            # Match the file to a pattern and get the folder name from registry
            matched_pattern, match_error = self.handler.match_file(file_path)

            if bool(match_error) and not self.S.DISABLE_REPORTS:
                self.reporter.write_report(file_path, [match_error])
                continue
            else:
                # Lookup the folder name from registry using the pattern
                folder_name = self.keyword_mapping.get(matched_pattern, matched_pattern)
                self.save_dispatched_file(file_path, folder_name, rm_from_input_folder)
                continue

    def save_dispatched_file(self, file_path, subfolder, rm_from_input=False):
        """
        Move a file to the specified subfolder.

        :param file_path: The full path of the file to move.
        :param subfolder: The name of the subfolder to move the file into.
        """
        target_folder = os.path.join(self.handler.output_folder_path, subfolder)
        os.makedirs(target_folder, exist_ok=True)

        target_path = os.path.join(target_folder, os.path.basename(file_path))
        if rm_from_input:
            shutil.move(file_path, target_path)
        else:
            shutil.copy2(file_path, target_path)
        print(f"Moved '{file_path}' to '{target_path}'")


# Example usages
if __name__ == "__main__":
    name = "MyDispatcher"
    registry_path = "registry.0_dispatcher"
    report_path = "/path/to/report/file"
    input_folder_path = "/path/to/your/input/folder"
    output_folder_path = "/path/to/your/output/folder"

    dispatcher = FileDispatcher(name, registry_path, report_path, input_folder_path, output_folder_path)
    dispatcher.dispatch_files()
