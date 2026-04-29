"""
Main entry point for the data processing pipeline using Prefect.
Handles both transformation and validation of data files.
Pipeline is defined in Python code using Prefect's @flow decorators.
"""

import os
os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "pangolin") # Ensure pangolin logger is included in Prefect's logging configuration

import sys

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
        input_folder="staging.0_validator",
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
        input_folder="staging.1_dispatcher",
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
        input_folder="staging.2_transform",
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
        input_folder="staging.3_validation",
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
        input_folder="staging.4_cross_validation",
        output_folder=S.DELIVERY_FOLDER_NAME,
        rm_from_input_folder=True
    )
    dispatcher.execute()


# ================================
# Test Data Generation Flow
# ================================

@flow(name="Generate Test Data", description="Generate test input files for the pipeline")
def generate_test_data():
    """
    Generates test CSV files (sales, inventory, edge cases) and product mappings
    into the pipeline's input folder. Uses the logic from test_files_generator.
    """
    import random
    import pandas as pd
    from test_files_generator.generator import (
        generate_product_mapping,
        save_product_mapping,
        generate_sales_data,
        generate_inventory_data,
    )

    logger = get_run_logger()
    S = get_settings()

    input_path = os.path.join(S.DATAPATH, S.INPUT_FOLDER_NAME)
    os.makedirs(input_path, exist_ok=True)

    logger.info(f"Generating test data into {input_path}")

    # Product mapping
    max_products = 100
    product_registry = generate_product_mapping(num_products=max_products)
    save_product_mapping(product_registry, settings=S)
    logger.info("Product mapping generated")

    # CASE 1 - US sales, all correct
    sales_df = generate_sales_data(num_records=500, num_products=8, num_stores=3)
    sales_df.to_csv(os.path.join(input_path, "US_sales_data_case1_all_correct.csv"), index=False, sep=S.CSV_DELIMITER)

    # CASE 2 - FR sales, all correct
    sales_df = generate_sales_data(num_records=1000, num_products=50, num_stores=3)
    sales_df.to_csv(os.path.join(input_path, "FR_sales_data_case2_all_correct.csv"), index=False, sep=S.CSV_DELIMITER)

    # CASE 3 - FR sales, price is string
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    for idx in random.sample(range(len(sales_df)), k=5):
        sales_df.at[idx, 'price'] = "test"
    sales_df.to_csv(os.path.join(input_path, "FR_sales_data_case3_price_is_string.csv"), index=False, sep=S.CSV_DELIMITER)

    # CASE 4 - US sales, quantity is string
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    for idx in random.sample(range(len(sales_df)), k=5):
        sales_df.at[idx, 'quantity'] = "test"
    sales_df.to_csv(os.path.join(input_path, "US_sales_data_case4_quantity_is_string.csv"), index=False, sep=S.CSV_DELIMITER)

    # CASE 5 - No nation prefix
    sales_df = generate_sales_data(num_records=800, num_products=8, num_stores=5)
    sales_df.to_csv(os.path.join(input_path, "sales_data_case5_no_nation.csv"), index=False, sep=S.CSV_DELIMITER)

    # CASE 6 - US sales, with duplicates
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    duplicates = sales_df.sample(n=10, random_state=1)
    sales_df = pd.concat([sales_df, duplicates], ignore_index=True)
    sales_df.to_csv(os.path.join(input_path, "US_sales_data_case6_with_duplicates.csv"), index=False, sep=S.CSV_DELIMITER)

    # CASE 7 - FR sales, with missing values
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    for col in ['price', 'quantity']:
        for idx in random.sample(range(len(sales_df)), k=5):
            sales_df.at[idx, col] = pd.NA
    sales_df.to_csv(os.path.join(input_path, "FR_sales_data_case7_with_missing_values.csv"), index=False, sep=S.CSV_DELIMITER)

    # CASE 8 - FR sales, missing product_id column
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    sales_df.drop(columns=['product_id'], inplace=True)
    sales_df.to_csv(os.path.join(input_path, "FR_sales_data_case8_missing_product_id.csv"), index=False, sep=S.CSV_DELIMITER)

    # CASE 9 - FR sales, out-of-scale values
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    sales_df.at[random.randint(0, len(sales_df) - 1), 'price'] = 10000
    sales_df.at[random.randint(0, len(sales_df) - 1), 'quantity'] = 10000
    sales_df.to_csv(os.path.join(input_path, "FR_sales_data_case9_out_of_scale.csv"), index=False, sep=S.CSV_DELIMITER)

    # CASE 10 - Empty file
    empty_df = pd.DataFrame()
    empty_df.to_csv(os.path.join(input_path, "sales_data_case10_empty_file.csv"), index=False, sep=S.CSV_DELIMITER)

    # INVENTORY - FR
    inventory_df = generate_inventory_data(num_records=1500, num_products=3, num_stores=4)
    inventory_df.to_csv(os.path.join(input_path, "FR_inventory_data_case1_all_correct.csv"), index=False, sep=S.CSV_DELIMITER)

    # INVENTORY - US
    inventory_df = generate_inventory_data(num_records=2000, num_products=3, num_stores=6)
    inventory_df.to_csv(os.path.join(input_path, "US_inventory_data_case2_all_correct.csv"), index=False, sep=S.CSV_DELIMITER)

    logger.info("Test data generation completed")


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

    s0 = raw_validation_flow(S, return_state=True)
    s1 = raw_dispatch_flow(S, return_state=True, wait_for=[s0])
    s2 = transform_flow(S, return_state=True, wait_for=[s1])
    s3 = validation_flow(S, return_state=True, wait_for=[s2])
    s4 = cross_validation_flow(S, return_state=True, wait_for=[s3])
    final_dispatch_flow(S, wait_for=[s4])


    logger.info("Process ended successfully")


# ================================
# Entry Point
# ================================

if __name__ == "__main__":
    if "--generate" in sys.argv:
        generate_test_data()
    else:
        data_pipeline()



