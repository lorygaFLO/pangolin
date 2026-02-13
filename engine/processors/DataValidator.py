"""
Validator Class:
Validates datasets against predefined rules specified in the registry.
Inherits from BaseProcessor for file operations.
"""

from utils.validators import VALIDATORS_DICT
from engine.processors.BaseProcessor import BaseProcessor
from engine.reporter import Reporter
from typing import Dict, Any, Optional, List
from utils.fs_wrapper import FSWrapper
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
        validation_results = {}
        
        # Iterate over files one by one using the generator
        for full_path, dataset, pattern, relative_path, error_messages in self.process_files(file_paths):
            if error_messages:
                # Report errors from file reading or pattern matching
                self.reporter.write_report(relative_path, error_messages)
                validation_results[full_path] = {"overall_passed": False, "errors": error_messages}
                continue

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
            
            validation_results[full_path] = {"overall_passed": all_passed, "details": file_validation_results}
            
            # Save only if ALL validations passed
            if all_passed:
                relative_path_obj = self.fs.dirname(relative_path)
                output_filename = f"{self.fs.splitext(self.fs.basename(relative_path))[0]}.{S.OUTPUT_FORMAT}"
                output_relative_path = self.fs.join(relative_path_obj, output_filename) if relative_path_obj else output_filename
                output_path = self.write_file(dataset, output_relative_path)
                print(f"Valid file saved to {output_relative_path}")
            else:
                # Validation failed - generate report with all issues
                messages.append("\nFile NOT saved due to validation errors")
                print(f"Validation failed for {relative_path} - file not saved")
                # Write report using relative path to maintain folder structure
                self.reporter.write_report(relative_path, messages)
                
        if not validation_results:
            print(f"No files to validate in '{self.input_node.path}'")
        
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
