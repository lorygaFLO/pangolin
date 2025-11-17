"""
DataTransformer Class:
Transforms datasets according to rules in the transform registry.
Inherits from BaseProcessor for file operations.
"""

import os
from typing import Dict, Any, Literal
from utils.transformers import TRANSFORMERS_DICT
from engine.processors.BaseProcessor import BaseProcessor
from engine.Reporter import Reporter
from config.settings import get_settings
from pathlib import Path
from utils.fs_wrapper import FSWrapper
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
        transformation_results = {}

        # Iterate over files one by one using the generator
        for full_path, data, pattern, relative_path, error_messages in self.process_files(file_paths):
            if error_messages:
                # Report errors from file reading or pattern matching
                self.reporter.write_report(relative_path, error_messages)
                transformation_results[full_path] = {"overall_success": False, "errors": error_messages}
                continue

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
                    error_msg = f"ERROR in transform '{transform['name']}': {str(e)}"
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
                    relative_path_obj = self.fs.join(*self.fs.dirname(relative_path).split(os.sep)) if self.fs.dirname(relative_path) != '' else ''
                    output_filename = f"{os.path.splitext(self.fs.basename(relative_path))[0]}.{S.OUTPUT_FORMAT}"
                    output_relative_path = self.fs.join(relative_path_obj, output_filename) if relative_path_obj else output_filename
                    output_path = self.write_file(modified_data, output_relative_path)
                    print(f"Transformed file saved to {output_relative_path}")
                except Exception as e:
                    all_success = False
                    messages.append(f"Error saving transformed file: {str(e)}")
            else:
                messages.append("\nFile NOT saved due to transformation errors")
                print(f"Transformation failed for {relative_path} - file not saved")
            
            self.reporter.write_report(relative_path, messages)
            transformation_results[full_path] = {"overall_success": all_success, "transform_log": transform_log, "messages": messages}

        if not transformation_results:
            print(f"No files to transform in '{self.input_node.path}'")

        return transformation_results

# Usage example
if __name__ == "__main__":
    # Ensure you have a registry.yaml with 'transforms' defined for a pattern
    # Example registry.yaml entry:
    # my_pattern_*.csv:
    #   transforms:
    #     - name: "Rename Column A"
    #       order: 1
    #       function: "rename_column"
    #       params:
    #         old_name: "Column A"
    #         new_name: "New Column A"
    #     - name: "Filter Rows"
    #       order: 2
    #       function: "filter_rows"
    #       params:
    #         column: "Value"
    #         operator: ">"
    #         value: 10
    
    transformer = DataTransformer(
        name='transformation_step',
        registry_path='config/registry.yaml',
        report_folder='reports.transformation',
        input_folder='staging.validated',
        output_folder='staging.transformed'
    )
    transformation_results = transformer.execute()
    print(transformation_results)
