"""
Full end-to-end processing pipeline: backup/restore -> raw validation ->
raw dispatch -> transform -> validation -> cross-validation -> final dispatch.
"""

import os
from typing import Optional

from prefect import flow, get_run_logger

from pangolin.engine.processors.DataValidator import Validator
from pangolin.engine.processors.DataTransformer import DataTransformer
from pangolin.engine.processors.FileDispatcher import FileDispatcher
from pangolin.engine.processors.BackupRestore import BackupRestore
from pangolin.config.settings import get_settings
from pangolin.config.run_context import RunContext


# ================================
# Subflow steps (private to this pipeline)
# ================================

@flow(name="Backup Input")
def backup_flow(CTX: RunContext):
    """Backup current input files to backup/<run_id>/."""
    S = get_settings()
    backup = BackupRestore(CTX, name="backup", input_folder=S.INPUT_FOLDER_NAME, output_folder="backup")
    backup.execute()


@flow(name="Restore from Backup")
def restore_flow(CTX: RunContext, restore_from: str):
    """Restore files from a previous backup run into the input folder."""
    S = get_settings()
    backup = BackupRestore(CTX, name="backup", input_folder=S.INPUT_FOLDER_NAME, output_folder="backup")
    backup.restore(restore_from)


@flow(name="Clear Input Folder")
def clear_input_flow(CTX: RunContext):
    """Remove all files from the input folder after successful processing."""
    S = get_settings()
    backup = BackupRestore(CTX, name="backup", input_folder=S.INPUT_FOLDER_NAME, output_folder="backup")
    backup.clear_input_folder()


@flow(name="0 - Raw Data Validation")
def raw_validation_flow(CTX: RunContext):
    """Step 0: Validate raw input files."""
    S = get_settings()
    validator = Validator(
        CTX,
        name="0_validator",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder=S.INPUT_FOLDER_NAME,
        output_folder="staging.0_validator"
    )
    validator.execute()


@flow(name="1 - Raw Data Dispatch")
def raw_dispatch_flow(CTX: RunContext):
    """Step 1: Dispatch raw files based on file type/pattern."""
    S = get_settings()
    dispatcher = FileDispatcher(
        CTX,
        name="1_dispatcher",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.0_validator",
        output_folder="staging.1_dispatcher",
        rm_from_input_folder=False
    )
    dispatcher.execute()


@flow(name="2 - Data Transformation")
def transform_flow(CTX: RunContext):
    """Step 2: Transform data according to business rules."""
    S = get_settings()
    transformer = DataTransformer(
        CTX,
        name="2_transform",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.1_dispatcher",
        output_folder="staging.2_transform"
    )
    transformer.execute()


@flow(name="3 - Transformed Data Validation")
def validation_flow(CTX: RunContext):
    """Step 3: Validate transformed data."""
    S = get_settings()
    validator = Validator(
        CTX,
        name="3_validation",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.2_transform",
        output_folder="staging.3_validation"
    )
    validator.execute()


@flow(name="4 - Cross Validation")
def cross_validation_flow(CTX: RunContext):
    """Step 4: Perform cross-validation checks between datasets."""
    S = get_settings()
    validator = Validator(
        CTX,
        name="4_cross_validation",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.3_validation",
        output_folder="staging.4_cross_validation"
    )
    validator.execute()


@flow(name="5 - Final Data Dispatch")
def final_dispatch_flow(CTX: RunContext):
    """Step 5: Dispatch validated and processed data to delivery folder."""
    S = get_settings()
    dispatcher = FileDispatcher(
        CTX,
        name="5_dispatcher",
        report_folder=S.REPORTS_FOLDER_NAME,
        input_folder="staging.4_cross_validation",
        output_folder=S.DELIVERY_FOLDER_NAME,
        rm_from_input_folder=True
    )
    dispatcher.execute()


# ================================
# Pipeline flow
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
    restore_from = restore_from.strip() if restore_from else None

    if restore_from:
        logger.info(f"Process started - PANGOLIN_RUN_ID: {CTX.RUN_ID} - RESTORING from backup {restore_from}")
    else:
        logger.info(f"Process started - PANGOLIN_RUN_ID: {CTX.RUN_ID}")

    # Either restore from a previous backup, or backup current input
    if restore_from:
        s_init = restore_flow(CTX, restore_from=restore_from, return_state=True)
    else:
        s_init = backup_flow(CTX, return_state=True)

    s0 = raw_validation_flow(CTX, return_state=True, wait_for=[s_init])
    s1 = raw_dispatch_flow(CTX, return_state=True, wait_for=[s0])
    s2 = transform_flow(CTX, return_state=True, wait_for=[s1])
    s3 = validation_flow(CTX, return_state=True, wait_for=[s2])
    s4 = cross_validation_flow(CTX, return_state=True, wait_for=[s3])
    s5 = final_dispatch_flow(CTX, return_state=True, wait_for=[s4])

    if clear_input and not restore_from:
        clear_input_flow(CTX, wait_for=[s5])

    logger.info("Process ended successfully")


# Marks the flow to expose/deploy for this module — required since a
# pipeline file may define several internal @flow-decorated subflow steps.
PIPELINE = data_pipeline

# Deployment config consumed by docker/deploy.py — keeps the original
# deployment name/schedule tied to this pipeline's own file.
DEPLOYMENT_NAME = "pangolin-daily"
DEPLOYMENT_KWARGS: dict = {}
_cron = os.getenv("PANGOLIN_CRON")
if _cron:
    DEPLOYMENT_KWARGS["cron"] = _cron
