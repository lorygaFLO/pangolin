"""
Generates synthetic test input files (sales, inventory, edge cases) and the
product mapping into the pipeline's input folder. Useful for demos and
local/dev testing without real source data.
"""

import os
import random

import pandas as pd
from prefect import flow, get_run_logger

from config.settings import get_settings
from test_files_generator.generator import (
    generate_product_mapping,
    save_product_mapping,
    generate_sales_data,
    generate_inventory_data,
)


@flow(name="Generate Test Data", description="Generate test input files for the pipeline")
def generate_test_data():
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


# Marks the flow to expose/deploy for this module.
PIPELINE = generate_test_data

# Deployment config consumed by docker/deploy.py.
DEPLOYMENT_KWARGS = {"extra_tags": ["test-data"]}
