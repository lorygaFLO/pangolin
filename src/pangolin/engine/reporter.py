from pangolin.utils.fs_wrapper import FSWrapper
from pangolin.config.settings import get_settings
from pangolin.config.run_context import RunContext
from pangolin.engine.DataFacility import get_project_data
from pangolin.engine.common.logger import ProcessorLogger

class Reporter:
    def __init__(self, CTX: RunContext, report_folder: str = None, step_name: str = None):
        """
        Initialize the Reporter with DataFacility integration.

        Args:
            CTX: RunContext with runtime state (RUN_ID)
            report_folder (str): Dot-notation path to report folder in data structure 
                               (e.g., 'reports.validation', 'output.reports')
                               If None, uses 'reports' as default
            step_name (str): Name of the step for creating a subfolder structure

        Raises:
            ValueError: If the report folder node doesn't exist in data structure
        """
        S = get_settings()
        self.S = S
        self.D = get_project_data(run_id=CTX.RUN_ID)
        
        self.fs = FSWrapper(
            protocol=getattr(S, "FS_PROTOCOL", "file"))
        
        # Default to 'reports' node if not specified
        self.report_folder = report_folder or 'reports'
        self.step_name = step_name
        self.log = ProcessorLogger(step_name or 'reporter')
        
        # Navigate to report node using DataFacility
        try:
            self.report_node = self.D.get_node(self.report_folder)
        except AttributeError as e:
            raise ValueError(f"Report folder '{self.report_folder}' not found in data structure: {e}") from e

        # If step_name is provided, create a subfolder for it
        if self.step_name:
            self.report_path = self.fs.join(str(self.report_node.path), self.step_name)
        else:
            self.report_path = str(self.report_node.path)

        # Ensure the report path exists
        self.fs.makedirs(self.report_path, exist_ok=True)

    def _create_report_filename(self, input_file_path: str) -> str:
        """Create report filename based on input file."""
        # Get just the filename if it's an absolute path
        input_filename = self.fs.basename(input_file_path)
        # Remove extension and add .txt
        report_filename = self.fs.basename(self.fs.splitext(input_filename)[0]) + '_report.txt'
        return report_filename

    def write_report(self, input_file_path: str, messages: list):
        """
        Write validation report for a specific file.
        
        Args:
            input_file_path: Path to the input file being validated
            messages: List of validation messages
        """
        if not messages or all("Passed" in message for message in messages) or self.S.DISABLE_REPORTS:
            return
        
        report_filename = self._create_report_filename(input_file_path)
        report_path = self.fs.join(self.report_path, report_filename)
        
        report_type = "Report"
        with self.fs.open(report_path, 'w') as report_file:
            report_file.write(f"{report_type} for: {input_file_path}\n")
            report_file.write("=" * 50 + "\n\n")
            for message in messages:
                report_file.write(message + '\n')
        
        self.log.info(f"Report written to {report_path}")

    def list_reports(self, pattern: str = '*.txt') -> list:
        """List all reports in the report folder."""
        return self.fs.glob(self.fs.join(self.report_path, pattern))

    def clear_reports(self):
        """Clear all reports from the report folder."""
        for report_file in self.list_reports():
            self.fs.remove(report_file)
        self.log.info(f"Cleared all reports from {self.report_path}")

# Example usage with DataFacility
if __name__ == "__main__":
    # Using dot notation to specify report location in data structure with step name
    reporter = Reporter('reports.validation', step_name='dispatcher_step')
    
    # Write a report
    reporter.write_report('data/input/test1.csv', [
        "Validation failed: Missing required columns",
        "Column 'id' not found"
    ])
    
    # List all reports
    reports = reporter.list_reports()
    print(f"Found {len(reports)} reports")
