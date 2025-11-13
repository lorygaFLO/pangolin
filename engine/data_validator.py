"""
Validator Class:
Validates datasets against predefined rules specified in the registry.
Inherits from BaseProcessor for file operations.
"""

import os
import shutil
from utils.validators import VALIDATORS_DICT
from engine.file_handler import BaseProcessor
from engine.reporter import Reporter
from typing import Dict, Any, Optional, List
from pathlib import Path
from config.settings import get_settings
S = get_settings()

class Validator(BaseProcessor):
    def __init__(self, name: str, registry_path: str, report_folder: str, input_folder: str, output_folder: str = None):
        """
        Initialize the Validator class.
        
        Args:
            name: Step name for identification
            registry_path: Path to the registry file
            report_folder: Dot-notation path to report folder in data structure
            input_folder: Dot-notation path to input folder
            output_folder: Dot-notation path to output folder
        """
        super().__init__(name, registry_path, input_folder, output_folder)
        self.reporter = Reporter(report_folder, step_name=name)

    def _execute_validator(self, validator_func, dataset: Any, messages: List[str], params: Optional[Dict] = None) -> bool:
        """Execute a validator function."""
        try:
            if params is None:
                result = validator_func(dataset, messages)
            else:
                result = validator_func(dataset, messages, params)

            return result[0] if isinstance(result, tuple) else result
        except Exception as e:
            messages.append(str(e))
            return False

    def execute(self, file_paths=None) -> Dict[str, bool]:
        """
        Validate the input files against the registry rules.
        """
        # Let process_files handle getting the files and potential errors
        processed_files, error_files = self.process_files(file_paths)
        validation_results = {}
        
        # Report errors
        for file_path, error_messages in error_files.items():
            # Extract relative path from file_path for report structure
            relative_path = Path(file_path).relative_to(self.input_node.path) if Path(file_path).is_relative_to(self.input_node.path) else Path(file_path).name
            self.reporter.write_report(str(relative_path), error_messages)
        
        if not processed_files:
            print(f"No files to validate in '{self.input_node.path}'")
            return validation_results

        # Validate each file
        for file_path, (dataset, pattern, relative_path) in processed_files.items():
            print(f"Validating {relative_path}")
            messages = []
            
            file_validation_results = {}
            validators = self.registry[pattern]['validators']
            all_passed = True
            
            for validator_name, params in validators.items():
                validator_func = VALIDATORS_DICT.get(validator_name)
                if not validator_func:
                    raise ValueError(f"Validator {validator_name} not found")

                result = self._execute_validator(validator_func, dataset, messages, params)
                file_validation_results[validator_name] = result
                
                if result is False:
                    all_passed = False
                    # Continue validating all rules to get complete report
            
            # Add validation summary to messages
            messages.append("\n\n------ VALIDATION RESULTS -------\n")
            for validator_name, result in file_validation_results.items():
                messages.append(f"{validator_name}: {'Passed' if result else 'Failed'}")
            
            validation_results.update(file_validation_results)
            
            # Save only if ALL validations passed
            if all_passed:
                output_path = self.write_file(dataset, relative_path)
                print(f"Valid file saved to {relative_path}")
            else:
                # Validation failed - generate report with all issues
                messages.append("\nFile NOT saved due to validation errors")
                print(f"Validation failed for {relative_path} - file not saved")
                # Write report using relative path to maintain folder structure
                self.reporter.write_report(relative_path, messages)
                
        return validation_results

# Usage example
if __name__ == "__main__":
    validator = Validator(
        name='validation_step',
        registry_path='config/registry.yaml',
        report_folder='reports.validation',  # Using dot notation
        input_folder='input.raw',            # Using dot notation
        output_folder='staging.validated'     # Using dot notation
    )
    validation_results = validator.execute()
    print(validation_results)
