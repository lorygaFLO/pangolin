"""
DataTransformer Class:
Transforms datasets according to rules in the transform registry.
Inherits from BaseProcessor for file operations.
"""

from typing import Dict, Any, List, Literal, Optional, Tuple
from utils.transformers import TRANSFORMERS_DICT
from engine.processors.BaseProcessor import BaseProcessor, Operation, FileOperations
from engine.reporter import Reporter
from engine.core.exceptions import NoInputFilesError, AllFilesFailedError
from config.settings import get_settings
from config.run_context import RunContext



class DataTransformer(BaseProcessor):
    def __init__(self, CTX: RunContext, name: str, report_folder: str, input_folder: str, output_folder: str = None):
        """
        Initialize the DataTransformer.
        
        Args:
            CTX: RunContext with runtime state (RUN_ID)
            name: Step name for identification (must match a node with
                  '_registry' in data_structure.yaml)
            report_folder: Dot-notation path to report folder in data structure
            input_folder: Dot-notation path to input folder
            output_folder: Dot-notation path to output folder
        """
        super().__init__(CTX, name, input_folder, output_folder)
        self.reporter = Reporter(CTX, report_folder, step_name=name)

    def build_operations_plan(
        self,
        file_paths: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, FileOperations]:
        """
        Pre-resolve, for each input file, the ordered list of transform
        operations to apply. Does NOT read file contents.

        Verifies during planning that every transformer function referenced
        in the registry exists in TRANSFORMERS_DICT. All missing functions
        are collected and reported together via a single ValueError at the
        end of planning (fail-fast on configuration errors).

        Args:
            file_paths: Optional list of (full_path, relative_path) tuples.
                        If None, uses self.get_input_files().

        Returns:
            Dict keyed by relative_path. Each value is a FileOperations with:
              - pattern: matched registry pattern (None if no match)
              - operations: ordered list of Operation objects (sorted by 'order')
              - error: planning error message (currently only for pattern miss)

        Raises:
            ValueError: if any referenced transformer function is missing
                        from TRANSFORMERS_DICT. The message lists every
                        missing function and the patterns that reference it.
        """
        if file_paths is None:
            file_paths = self.get_input_files()

        plan: Dict[str, FileOperations] = {}
        missing_functions: Dict[str, set] = {}  # func_name -> {patterns using it}

        for full_path, relative_path in file_paths:
            fp = FileOperations(full_path=full_path, relative_path=relative_path)

            pattern, match_error = self.match_file(relative_path)
            if match_error:
                fp.error = match_error
                plan[relative_path] = fp
                continue
            fp.pattern = pattern

            transforms = self.registry[pattern].get("transforms", []) or []
            sorted_transforms = sorted(transforms, key=lambda t: t.get("order", 0))

            ops: List[Operation] = []
            for t in sorted_transforms:
                func_name = t.get("function")
                func = TRANSFORMERS_DICT.get(func_name)
                if func is None:
                    missing_functions.setdefault(func_name, set()).add(pattern)
                    continue  # keep collecting; don't bind an Operation for this entry
                ops.append(Operation(
                    name=t.get("name", func_name),
                    func=func,
                    params=t.get("params", {}) or {},
                ))

            fp.operations = ops
            plan[relative_path] = fp

        if missing_functions:
            lines = [
                f"  - '{name}' (used by patterns: {sorted(patterns)})"
                for name, patterns in sorted(missing_functions.items(), key=lambda kv: str(kv[0]))
            ]
            raise ValueError(
                f"[{self.name}] Missing transformer function(s) in TRANSFORMERS_DICT:\n"
                + "\n".join(lines)
            )

        return plan

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

            self.log.info(f"Transforming {relative_path}")
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
                    relative_path_obj = self.fs.dirname(relative_path)
                    output_filename = f"{self.fs.splitext(self.fs.basename(relative_path))[0]}.{self.S.OUTPUT_FORMAT}"
                    output_relative_path = self.fs.join(relative_path_obj, output_filename) if relative_path_obj else output_filename
                    output_path = self.write_file(modified_data, output_relative_path)
                    self.log.info(f"Transformed file saved to {output_relative_path}")
                except Exception as e:
                    all_success = False
                    messages.append(f"Error saving transformed file: {str(e)}")
            else:
                messages.append("\nFile NOT saved due to transformation errors")
                self.log.warning(f"Transformation failed for {relative_path} - file not saved")
            
            self.reporter.write_report(relative_path, messages)
            transformation_results[full_path] = {"overall_success": all_success, "transform_log": transform_log, "messages": messages}

        if not transformation_results:
            raise NoInputFilesError(self.name, str(self.input_node.path))

        # ---- Final summary ----
        passed = [self.fs.basename(p) for p, r in transformation_results.items() if r.get("overall_success")]
        failed = [self.fs.basename(p) for p, r in transformation_results.items() if not r.get("overall_success")]

        self.log.info(f"Transformation complete: {len(passed)} passed, {len(failed)} failed out of {len(transformation_results)} files")
        if passed:
            self.log.info("TRANSFORMED:\n   - " + "\n   - ".join(passed))
        if failed:
            self.log.warning("FAILED:\n   - " + "\n   - ".join(failed))

        if len(passed) == 0:
            raise AllFilesFailedError(
                f"[{self.name}] All {len(failed)} file(s) failed transformation."
            )

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
        report_folder='reports.transformation',
        input_folder='staging.validated',
        output_folder='staging.transformed'
    )
    transformation_results = transformer.execute()
    print(transformation_results)
