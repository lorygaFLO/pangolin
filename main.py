"""
Main entry point for the data processing pipeline.
Handles both transformation and validation of data files.
Every step must have an execute attribute
"""

from engine.DataValidator import Validator
from engine.DataTranformer import DataTransformer
from engine.FileDispatcher import FileDispatcher

from config.settings import *
import yaml

def load_pipeline_structure(config_path):
    """Load pipeline configuration from a YAML file."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def step_factory(step_type, **kwargs):
    """Factory function to create step instances based on type."""
    if step_type == 'transform':
        return DataTransformer(
            name=kwargs['name'],
            registry_path=kwargs['registry_path'],
            report_folder=kwargs['report_folder'],
            input_folder=kwargs['input_folder'],
            output_folder=kwargs.get('output_folder') or kwargs['name']  # Default to step name
        )
    elif step_type == 'validate':
        return Validator(
            name=kwargs['name'],
            registry_path=kwargs['registry_path'],
            report_folder=kwargs['report_folder'],
            input_folder=kwargs['input_folder'],
            output_folder=kwargs.get('output_folder') or kwargs['name'] # Default to step name
        )
    elif step_type == 'dispatcher':
        return FileDispatcher(
            name=kwargs['name'],
            registry_path=kwargs['registry_path'],
            report_folder=kwargs['report_folder'],
            input_folder=kwargs['input_folder'],
            output_folder=kwargs.get('output_folder') or kwargs['name'],  # Default to step name
            rm_from_input_folder=kwargs.get('rm_from_input_folder', False)
        )
    else:
        raise ValueError(f"Unsupported step type: {step_type}")


def run():
    S = get_settings()
    print("Process started with RUN_ID:", S.RUN_ID)

    # Load pipeline configuration
    pipeline_structure = load_pipeline_structure('config/pipeline_structure.yaml')

    for step in pipeline_structure['steps']:

        step_type = step['type']
        step_name = step['name']
        print(f"\nStarting {step_type} step: {step_name}...")

        try:
            step_instance = step_factory(step_type, **step)
            # Execute the step (assumes all step classes have a `run` method)
            step_instance.execute()
        except ValueError as e:
            print(f"Error: {e}")

        print(f"{step_type.capitalize()} step {step_name} completed")

    print("\nProcess ended")


if __name__ == "__main__":
    run()



