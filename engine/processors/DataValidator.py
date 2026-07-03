"""
Validator Class:
Validates datasets against predefined rules specified in the registry.
Inherits from BaseProcessor for file operations.
"""

from utils.validators import VALIDATORS_DICT
from engine.processors.BaseProcessor import BaseProcessor, Operation, FileOperations
from engine.reporter import Reporter
from engine.core.exceptions import NoInputFilesError, AllFilesFailedError
from typing import Dict, Any, Optional, List, Tuple, Union
from utils.fs_wrapper import FSWrapper
from config.settings import get_settings
from config.run_context import RunContext

class Validator(BaseProcessor):
    def __init__(self, CTX: RunContext, name: str, report_folder: str, input_folder: str, output_folder: str = None,
                 registry: Optional[Union[dict, str]] = None):
        """
        Initialize the Validator class.
        
        Args:
            CTX: RunContext with runtime state (RUN_ID)
            name: Step name for identification (must match a node with
                  '_registry' in data_structure.yaml, unless 'registry' is passed)
            report_folder: Dot-notation path to report folder in data structure
            input_folder: Dot-notation path to input folder
            output_folder: Dot-notation path to output folder
            registry: Optional custom registry (dict or YAML path). Takes
                      priority over '_registry' in data_structure.yaml.
        """
        super().__init__(CTX, name, input_folder, output_folder, registry=registry)
        self.reporter = Reporter(CTX, report_folder, step_name=name)

    def build_operations_plan(
        self,
        file_paths: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, FileOperations]:
        """
        Pre-resolve, for each input file, the list of validator operations
        to run. Does NOT read file contents.

        Verifies during planning that every validator referenced in the
        registry exists in VALIDATORS_DICT. All missing validators are
        collected and reported together via a single ValueError at the
        end of planning (fail-fast on configuration errors).

        Args:
            file_paths: Optional list of (full_path, relative_path) tuples.
                        If None, uses self.get_input_files().

        Returns:
            Dict keyed by relative_path. Each value is a FileOperations with:
              - pattern: matched registry pattern (None if no match)
              - operations: list of Operation objects (registry insertion order)
              - error: planning error message (currently only for pattern miss)

        Raises:
            ValueError: if any referenced validator is missing from
                        VALIDATORS_DICT. The message lists every missing
                        validator and the patterns that reference it.
        """
        if file_paths is None:
            file_paths = self.get_input_files()

        plan: Dict[str, FileOperations] = {}
        missing_validators: Dict[str, set] = {}  # validator_name -> {patterns using it}

        for full_path, relative_path in file_paths:
            fp = FileOperations(full_path=full_path, relative_path=relative_path)

            pattern, match_error = self.match_file(relative_path)
            if match_error:
                fp.error = match_error
                plan[relative_path] = fp
                continue
            fp.pattern = pattern

            validators = self.registry[pattern].get("validators", {}) or {}

            ops: List[Operation] = []
            for validator_name, params in validators.items():
                func = VALIDATORS_DICT.get(validator_name)
                if func is None:
                    missing_validators.setdefault(validator_name, set()).add(pattern)
                    continue  # keep collecting; don't bind an Operation for this entry
                ops.append(Operation(
                    name=validator_name,
                    func=func,
                    params=params,
                ))

            fp.operations = ops
            plan[relative_path] = fp

        if missing_validators:
            lines = [
                f"  - '{name}' (used by patterns: {sorted(patterns)})"
                for name, patterns in sorted(missing_validators.items(), key=lambda kv: str(kv[0]))
            ]
            raise ValueError(
                f"[{self.name}] Missing validator(s) in VALIDATORS_DICT:\n"
                + "\n".join(lines)
            )

        return plan

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

            self.log.info(f"Validating {relative_path}")
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
                output_filename = f"{self.fs.splitext(self.fs.basename(relative_path))[0]}.{self.S.OUTPUT_FORMAT}"
                output_relative_path = self.fs.join(relative_path_obj, output_filename) if relative_path_obj else output_filename
                output_path = self.write_file(dataset, output_relative_path)
                self.log.info(f"Valid file saved to {output_relative_path}")
            else:
                # Validation failed - generate report with all issues
                messages.append("\nFile NOT saved due to validation errors")
                self.log.warning(f"Validation failed for {relative_path} - file not saved")
                # Write report using relative path to maintain folder structure
                self.reporter.write_report(relative_path, messages)
                
        if not validation_results:
            raise NoInputFilesError(self.name, str(self.input_node.path))

        # ---- Final summary ----
        passed = [self.fs.basename(p) for p, r in validation_results.items() if r.get("overall_passed")]
        failed = [self.fs.basename(p) for p, r in validation_results.items() if not r.get("overall_passed")]

        self.log.info(f"Validation complete: {len(passed)} passed, {len(failed)} failed out of {len(validation_results)} files")
        if passed:
            self.log.info("PASSED:\n   - " + "\n   - ".join(passed))
        if failed:
            self.log.warning("FAILED:\n   - " + "\n   - ".join(failed))

        if len(passed) == 0:
            raise AllFilesFailedError(
                f"[{self.name}] All {len(failed)} file(s) failed validation."
            )
        
        return validation_results

# Usage example
if __name__ == "__main__":
    validator = Validator(
        name='validation_step',
        report_folder='reports.validation',  # Using dot notation
        input_folder='input.raw',            # Using dot notation
        output_folder='staging.validated'     # Using dot notation
    )
    validation_results = validator.execute()
    print(validation_results)
