"""
DataTransformer Class:
Transforms datasets according to rules in the transform registry.
Inherits from BaseProcessor for file operations.
"""

import os
from typing import Dict, Any, Literal
from utils.transformers import TRANSFORMERS_DICT
from engine.file_handler import BaseProcessor
from engine.reporter import Reporter
from config.settings import get_settings
from pathlib import Path
S = get_settings()
class DataTransformer(BaseProcessor):
    def __init__(self, name: str, registry_path: str, report_folder: str, input_folder: str, output_folder: str = None):
        """
        Initialize the DataTransformer.
        
        Args:
            name: Step name for identification
            registry_path: Path to the registry file
            report_folder: Dot-notation path to report folder in data structure
            input_folder: Dot-notation path to input folder
            output_folder: Dot-notation path to output folder
        """
        super().__init__(name, registry_path, input_folder, output_folder)
        self.reporter = Reporter(report_folder, step_name=name)

    def execute(self, file_paths=None) -> Dict[str, Dict[str, Any]]:
        """
        Transform files according to the rules in the registry.
        """
        # Let process_files handle getting the files and potential errors
        processed_files, error_files = self.process_files(file_paths)
        transformation_results = {}

        # Report errors
        for file_path, error_messages in error_files.items():
            # Extract relative path from file_path for report structure
            relative_path = Path(file_path).relative_to(self.input_node.path) if Path(file_path).is_relative_to(self.input_node.path) else Path(file_path).name
            self.reporter.write_report(str(relative_path), error_messages)

        if not processed_files:
            print(f"No files to transform in '{self.input_node.path}'")
            return transformation_results

        # Transform each file
        for file_path, (data, pattern, relative_path) in processed_files.items():
            print(f"Transforming {relative_path}")
            messages = []
            
            transforms = self.registry[pattern]["transforms"]
            sorted_transforms = sorted(transforms, key=lambda x: x["order"])
            
            modified_data = data.clone()  # Polars clone
            transform_log = []

            for transform in sorted_transforms:
                try:
                    transformer_func = TRANSFORMERS_DICT.get(transform["function"])
                    
                    if transformer_func:
                        modified_data = transformer_func(
                            modified_data, 
                            messages=messages,
                            **transform["params"]
                        )
                        transform_log.append({
                            "transform": transform["name"],
                            "status": "success"
                        })
                        messages.append(f"Transform '{transform['name']}' completed successfully")
                    else:
                        error_msg = f"Transformer function '{transform['function']}' not found"
                        transform_log.append({
                            "transform": transform["name"],
                            "status": "failed",
                            "error": error_msg
                        })
                        messages.append(error_msg)
                
                except Exception as e:
                    error_msg = f"Error in transform '{transform['name']}': {str(e)}"
                    transform_log.append({
                        "transform": transform["name"],
                        "status": "failed",
                        "error": str(e)
                    })
                    messages.append(error_msg)

            # Save only if ALL transformations were successful
            all_success = all(log["status"] == "success" for log in transform_log)
            
            if all_success:
                try:
                    # Preserve folder structure but change extension to output format
                    relative_path_obj = Path(relative_path)
                    
                    # Change extension but keep folder structure
                    if str(relative_path_obj.parent) == '.':
                        # File at root level
                        output_relative_path = Path(f"{relative_path_obj.stem}.{S.OUTPUT_FORMAT}")
                    else:
                        # File in subfolder - preserve structure
                        output_relative_path = relative_path_obj.parent / f"{relative_path_obj.stem}.{S.OUTPUT_FORMAT}"
                    
                    output_path = self.write_file(modified_data, str(output_relative_path))
                    messages.append(f"Transformed file saved to: {str(output_relative_path)}")
                    print(f"Transformed file saved to: {str(output_relative_path)}")
                except Exception as e:
                    error_msg = f"Error saving file: {str(e)}"
                    transform_log.append({
                        "transform": "save_file",
                        "status": "failed",
                        "error": str(e)
                    })
                    messages.append(error_msg)
            else:
                # Transformation failed - only generate report, don't save file
                messages.append("File NOT saved due to transformation errors")
                print(f"Transformation failed for {file_path} - file not saved")

            transformation_results[file_path] = {
                "data": modified_data,
                "log": transform_log
            }

            # Write report
            if messages:
                messages.insert(0, f"\n------ TRANSFORMATION RESULTS for {file_path} -------\n")
                # Use relative_path to maintain folder structure in reports
                self.reporter.write_report(relative_path, messages)

        return transformation_results

# Usage example
if __name__ == "__main__":
    transformer = DataTransformer(
        name='transform_step',
        registry_path='config/transform_registry.yaml',
        report_folder='reports.transformation',  # Using dot notation
        input_folder='staging.0_dispatcher',     # Using dot notation  
        output_folder='staging.1_transform'      # Using dot notation
    )
    transformation_results = transformer.execute()
    
    # Print summary
    for file_path, result in transformation_results.items():
        print(f"\nFile: {file_path}")
        for log_entry in result['log']:
            status = log_entry.get('status', 'unknown')
            transform_name = log_entry.get('transform', 'unknown')
            print(f"  - {transform_name}: {status}")
            if status == 'failed' and 'error' in log_entry:
                print(f"    Error: {log_entry['error']}")
