"""
Main entry point for the data processing pipeline using Prefect.
Handles both transformation and validation of data files.
Pipeline is defined in Python code using Prefect's @flow decorators.
"""

import os
os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "pangolin") # Ensure pangolin logger is included in Prefect's logging configuration

from typing import Optional
from prefect import flow, get_run_logger
from engine.processors.DataValidator import Validator
from engine.processors.DataTranformer import DataTransformer
from engine.processors.FileDispatcher import FileDispatcher
from engine.processors.FileBackup import FileBackup
from engine.core.exceptions import PipelineError
from config.settings import get_settings
from config.run_context import RunContext


# ================================
# Subflow Definitions
# ================================

@flow(name="Backup Input")
def backup_flow(CTX):
    """Backup current input files to backup/<run_id>/."""
    S = get_settings()
    backup = FileBackup(CTX, name="backup", input_folder=S.INPUT_FOLDER_NAME, output_folder="backup")
    backup.execute()


@flow(name="Restore from Backup")
def restore_flow(CTX, restore_from: str):
    """Restore files from a previous backup run into the input folder."""
    S = get_settings()
    backup = FileBackup(CTX, name="backup", input_folder=S.INPUT_FOLDER_NAME, output_folder="backup")
    backup.restore(restore_from)


@flow(name="Clear Input Folder")
def clear_input_flow(CTX):
    """Remove all files from the input folder after successful processing."""
    S = get_settings()
    backup = FileBackup(CTX, name="backup", input_folder=S.INPUT_FOLDER_NAME, output_folder="backup")
    backup.clear_input_folder()

@flow(name="0 - Raw Data Validation")
def raw_validation_flow(CTX):
    """Step 0: Validate raw input files."""
    S = get_settings()
    validator = Validator(
        CTX,
        name="0_validator",
        registry_path="config/registries/0_raw_validation.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder=S.INPUT_FOLDER_NAME,
        output_folder="staging.0_validator"
    )
    validator.execute()


@flow(name="1 - Raw Data Dispatch")
def raw_dispatch_flow(CTX):
    """Step 1: Dispatch raw files based on file type/pattern."""
    S = get_settings()
    dispatcher = FileDispatcher(
        CTX,
        name="1_dispatcher",
        registry_path="config/registries/1_dispatcher.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.0_validator",
        output_folder="staging.1_dispatcher",
        rm_from_input_folder=False
    )
    dispatcher.execute()


@flow(name="2 - Data Transformation")
def transform_flow(CTX):
    """Step 2: Transform data according to business rules."""
    S = get_settings()
    transformer = DataTransformer(
        CTX,
        name="2_transform",
        registry_path="config/registries/2_transform_registry.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.1_dispatcher",
        output_folder="staging.2_transform"
    )
    transformer.execute()


@flow(name="3 - Transformed Data Validation")
def validation_flow(CTX):
    """Step 3: Validate transformed data."""
    S = get_settings()
    validator = Validator(
        CTX,
        name="3_validation",
        registry_path="config/registries/3_validation.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.2_transform",
        output_folder="staging.3_validation"
    )
    validator.execute()


@flow(name="4 - Cross Validation")
def cross_validation_flow(CTX):
    """Step 4: Perform cross-validation checks between datasets."""
    S = get_settings()
    validator = Validator(
        CTX,
        name="4_cross_validation",
        registry_path="config/registries/4_cross_validation.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.3_validation",
        output_folder="staging.4_cross_validation"
    )
    validator.execute()


@flow(name="5 - Final Data Dispatch")
def final_dispatch_flow(CTX):
    """Step 5: Dispatch validated and processed data to delivery folder."""
    S = get_settings()
    dispatcher = FileDispatcher(
        CTX,
        name="5_dispatcher",
        registry_path="config/registries/5_dispatcher.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.4_cross_validation",
        output_folder=S.DELIVERY_FOLDER_NAME,
        rm_from_input_folder=True
    )
    dispatcher.execute()


# ================================
# Main Flow Definition
# ================================

@flow(name="Full Processing Pipeline", description="End-to-end data validation, transformation, and delivery pipeline")
def data_pipeline(restore_from: Optional[str] = None, clear_input: bool = False):
    """
    Main data processing pipeline flow.
    Orchestrates the following subflows:
    -1. Backup / Restore (skipped when restoring from backup)
    0. Raw Data Validation
    1. Raw Data Dispatch
    2. Data Transformation
    3. Transformed Data Validation
    4. Cross Validation
    5. Final Data Dispatch

    Args:
        restore_from: If specified, restore input from this backup run_id
                      (e.g. "20260429_193608") instead of backing up.
        clear_input: If True (and not restoring), clear input folder after backup.
    """
    logger = get_run_logger()
    CTX = RunContext()
    
    logger.info(f"Process started - PANGOLIN_RUN_ID: {CTX.RUN_ID}")

    # Either restore from a previous backup, or backup current input
    if restore_from and restore_from.strip():
        s_init = restore_flow(CTX, restore_from=restore_from.strip(), return_state=True)
    else:
        s_init = backup_flow(CTX, return_state=True)

    s0 = raw_validation_flow(CTX, return_state=True, wait_for=[s_init])
    s1 = raw_dispatch_flow(CTX, return_state=True, wait_for=[s0])
    s2 = transform_flow(CTX, return_state=True, wait_for=[s1])
    s3 = validation_flow(CTX, return_state=True, wait_for=[s2])
    s4 = cross_validation_flow(CTX, return_state=True, wait_for=[s3])
    s5 = final_dispatch_flow(CTX, return_state=True, wait_for=[s4])

    if clear_input:
        clear_input_flow(CTX, wait_for=[s5])

    logger.info("Process ended successfully")


# ================================
# Entry Point
# ================================

if __name__ == "__main__":
    data_pipeline()



