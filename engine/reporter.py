import os
from config.settings import get_settings
from engine.data_facility import get_project_data
from pathlib import Path
from config.settings import get_settings
S = get_settings()
class Reporter:
    def __init__(self, report_folder: str = None, step_name: str = None):
        """
        Initialize the Reporter with DataFacility integration.

        Args:
            report_folder (str): Dot-notation path to report folder in data structure 
                               (e.g., 'reports.validation', 'output.reports')
                               If None, uses 'reports' as default
            step_name (str): Name of the step for creating a subfolder structure

        Raises:
            ValueError: If the report folder node doesn't exist in data structure
        """
        self.D = get_project_data()
        
        # Default to 'reports' node if not specified
        self.report_folder = report_folder or 'reports'
        self.step_name = step_name
        
        # Navigate to report node using DataFacility
        self.report_node = self._get_node_by_path(self.report_folder)
        
        # If step_name is provided, create a subfolder for it
        if self.step_name:
            self.report_path = self.report_node.path / self.step_name
        else:
            self.report_path = self.report_node.path
        
        # Ensure the report path exists
        self.report_path.mkdir(parents=True, exist_ok=True)

    def _get_node_by_path(self, path_str: str):
        """Navigate to a node in DataFacility using dot notation."""
        parts = path_str.split('.')
        node = self.D
        for part in parts:
            if not hasattr(node, part):
                raise ValueError(f"Report folder '{path_str}' not found in data structure")
            node = getattr(node, part)
        return node

    def _create_report_filename(self, input_file_path: str) -> str:
        """Create report filename based on input file."""
        # Get just the filename if it's an absolute path
        input_filename = os.path.basename(input_file_path)
        # Remove extension and add .txt
        report_filename = os.path.splitext(input_filename)[0] + '_report.txt'
        return report_filename

    def write_report(self, input_file_path: str, messages: list):
        """
        Write validation report for a specific file.
        
        Args:
            input_file_path: Path to the input file being validated
            messages: List of validation messages
        """
        if not messages or all("Passed" in message for message in messages) or S.DISABLE_REPORTS:
            return
        
        report_filename = self._create_report_filename(input_file_path)
        report_path = self.report_path / report_filename
        
        with open(report_path, 'w') as report_file:
            report_file.write(f"Validation Report for: {input_file_path}\n")
            report_file.write("=" * 50 + "\n\n")
            for message in messages:
                report_file.write(message + '\n')
        
        print(f"Report written to {report_path}")

    def list_reports(self, pattern: str = '*.txt') -> list:
        """List all reports in the report folder."""
        return list(self.report_path.glob(pattern))

    def clear_reports(self):
        """Clear all reports from the report folder."""
        for report_file in self.list_reports():
            report_file.unlink()
        print(f"Cleared all reports from {self.report_path}")

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
