"""
Main entry point for the data processing pipeline using Prefect.
Handles both transformation and validation of data files.
Pipeline is defined in Python code using Prefect's @flow decorators.
"""

import os
os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "pangolin") # Ensure pangolin logger is included in Prefect's logging configuration

from prefect import flow, get_run_logger
from engine.processors.DataValidator import Validator
from engine.processors.DataTranformer import DataTransformer
from engine.processors.FileDispatcher import FileDispatcher
from engine.core.exceptions import PipelineError
from config.settings import *


# ================================
# Subflow Definitions
# ================================

@flow(name="0 - Raw Data Validation")
def raw_validation_flow(S):
    """Step 0: Validate raw input files."""
    validator = Validator(
        name="0_validator",
        registry_path="config/registries/0_raw_validation.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder=S.INPUT_FOLDER_NAME,
        output_folder="staging.0_validator"
    )
    validator.execute()


@flow(name="1 - Raw Data Dispatch")
def raw_dispatch_flow(S):
    """Step 1: Dispatch raw files based on file type/pattern."""
    dispatcher = FileDispatcher(
        name="1_dispatcher",
        registry_path="config/registries/1_dispatcher.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder=S.STAGING_FOLDER_NAME,
        output_folder="staging.1_dispatcher",
        rm_from_input_folder=False
    )
    dispatcher.execute()


@flow(name="2 - Data Transformation")
def transform_flow(S):
    """Step 2: Transform data according to business rules."""
    transformer = DataTransformer(
        name="2_transform",
        registry_path="config/registries/2_transform_registry.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder=S.STAGING_FOLDER_NAME,
        output_folder="staging.2_transform"
    )
    transformer.execute()


@flow(name="3 - Transformed Data Validation")
def validation_flow(S):
    """Step 3: Validate transformed data."""
    validator = Validator(
        name="3_validation",
        registry_path="config/registries/3_validation.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder=S.STAGING_FOLDER_NAME,
        output_folder="staging.3_validation"
    )
    validator.execute()


@flow(name="4 - Cross Validation")
def cross_validation_flow(S):
    """Step 4: Perform cross-validation checks between datasets."""
    validator = Validator(
        name="4_cross_validation",
        registry_path="config/registries/4_cross_validation.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder=S.STAGING_FOLDER_NAME,
        output_folder="staging.4_cross_validation"
    )
    validator.execute()


@flow(name="5 - Final Data Dispatch")
def final_dispatch_flow(S):
    """Step 5: Dispatch validated and processed data to delivery folder."""
    dispatcher = FileDispatcher(
        name="5_dispatcher",
        registry_path="config/registries/5_dispatcher.yaml",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder=S.STAGING_FOLDER_NAME,
        output_folder=S.DELIVERY_FOLDER_NAME,
        rm_from_input_folder=True
    )
    dispatcher.execute()


# ================================
# Main Flow Definition
# ================================

@flow(name="Full Processing Pipeline", description="End-to-end data validation, transformation, and delivery pipeline")
def data_pipeline():
    """
    Main data processing pipeline flow.
    Orchestrates the following subflows:
    0. Raw Data Validation
    1. Raw Data Dispatch
    2. Data Transformation
    3. Transformed Data Validation
    4. Cross Validation
    5. Final Data Dispatch
    """
    logger = get_run_logger()
    S = get_settings()
    
    logger.info(f"Process started - PANGOLIN_RUN_ID: {S.RUN_ID}")

    try:
        s0 = raw_validation_flow(S, return_state=True)
        s1 = raw_dispatch_flow(S, return_state=True, wait_for=[s0])
        s2 = transform_flow(S, return_state=True, wait_for=[s1])
        s3 = validation_flow(S, return_state=True, wait_for=[s2])
        s4 = cross_validation_flow(S, return_state=True, wait_for=[s3])
        final_dispatch_flow(S, wait_for=[s4])
    except PipelineError as e:
        logger.error(f"Pipeline halted: {e}")
        raise

    logger.info("Process ended successfully")


# ================================
# Entry Point
# ================================

if __name__ == "__main__":
    data_pipeline()



