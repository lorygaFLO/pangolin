import sys
import os

# Aggiungi la radice del progetto al percorso
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import random
import json
from faker import Faker
import pandas as pd
from datetime import datetime, timedelta
from config.settings import *


fake = Faker()

def generate_product_mapping(num_products: int = 10) -> dict:
    """
    Genera l'anagrafica prodotti con dettagli.
    
    Args:
        num_products: numero di prodotti unici
    
    Returns:
        Dictionary con product_id come chiave e dettagli prodotto
    """
    products = {}
    categories = ["Electronics", "Clothing", "Food", "Books", "Toys", "Home", "Sports"]
    brands = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta"]
    
    for i in range(1, num_products + 1):
        products[f"PROD_{i:04d}"] = {
            "product_name": fake.word().capitalize() + " " + fake.word().capitalize(),
            "product_version": f"v{random.randint(1, 5)}.{random.randint(0, 9)}",
            "category": random.choice(categories),
            "brand": random.choice(brands),
            "description": fake.text(max_nb_chars=100),
            "sku": f"SKU{i:04d}{random.randint(1000, 9999)}",
            "weight": round(random.uniform(0.1, 10.0), 2),
            "dimensions": f"{random.randint(10, 100)}x{random.randint(10, 100)}x{random.randint(10, 100)}mm",
            "status": random.choice(["Active", "Discontinued", "Coming Soon"]),
            "launch_date": fake.date_between(start_date='-2y', end_date='today').strftime('%Y-%m-%d')
        }
    
    return products

def save_product_mapping(products: dict):
    """
    Salva l'anagrafica prodotti nella cartella static/mappings.
    
    Args:
        products: dictionary con anagrafica prodotti
    """
    # Crea la cartella static/mappings se non esiste
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'static', 'mappings')
    os.makedirs(static_dir, exist_ok=True)
    
    # Salva come JSON
    json_path = os.path.join(static_dir, 'product_mapping.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    
    # Salva anche come CSV per comodità - USA IL DELIMITATORE DA SETTINGS
    csv_path = os.path.join(static_dir, 'product_mapping.csv')
    df_products = pd.DataFrame.from_dict(products, orient='index')
    # IMPORTANTE: reset_index per rendere product_id una colonna normale
    df_products.reset_index(inplace=True)
    df_products.rename(columns={'index': 'product_id'}, inplace=True)
    df_products.to_csv(csv_path, sep=S.CSV_DELIMITER, index=False)  # index=False per non salvare l'indice numerico
    
def generate_sales_data(num_records: int = 100, num_products: int = 10, num_stores: int = 5) -> pd.DataFrame:
    """
    Genera dati di test per sales (solo con product_id).
    
    Args:
        num_records: numero di record da generare
        num_products: numero di prodotti unici
        num_stores: numero di store unici
    
    Returns:
        DataFrame con colonne: product_id, price, store_id, sellout_price, date, quantity
    """
    
    # Genera date settimanali per il 2025
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 31)
    weekly_dates = []
    current_date = start_date
    while current_date <= end_date:
        weekly_dates.append(current_date.date())
        current_date += timedelta(weeks=1)
    
    data = []
    
    for _ in range(num_records):
        product_id = f"PROD_{random.randint(1, num_products):04d}"
        store_id = random.randint(1, num_stores)
        
        # Prezzo base del prodotto (varia poco tra store)
        base_price = round(random.uniform(10, 500), 2)
        store_variation = random.uniform(0.95, 1.05)  # ±5% di variazione per store
        price = round(base_price * store_variation, 2)
        
        # Sellout price: più alto del price (con variabilità 5-15%)
        markup = random.uniform(1.05, 1.15)
        sellout_price = round(price * markup, 2)
        
        data.append({
            "product_id": product_id,
            "price": price,
            "store_id": store_id,
            "sellout_price": sellout_price,
            "date": random.choice(weekly_dates),
            "quantity": random.randint(1, 100)
        })
    
    return pd.DataFrame(data)

def generate_inventory_data(num_records: int = 100, num_products: int = 10, num_stores: int = 5) -> pd.DataFrame:
    """
    Generate historical inventory data with daily/weekly snapshots.
    
    Args:
        num_records: number of records to generate
        num_products: number of unique products
        num_stores: number of unique stores
    
    Returns:
        DataFrame with columns: product_id, store_id, date, opening_stock, quantity_in, 
        quantity_out, closing_stock, reorder_point, reorder_quantity, unit_cost
    """
    
    # Generate weekly dates for 2025
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 31)
    weekly_dates = []
    current_date = start_date
    while current_date <= end_date:
        weekly_dates.append(current_date.date())
        current_date += timedelta(weeks=1)
    
    data = []
    
    # Track inventory state for each product-store combination
    inventory_states = {}
    
    for _ in range(num_records):
        product_id = f"PROD_{random.randint(1, num_products):04d}"
        store_id = random.randint(1, num_stores)
        date = random.choice(weekly_dates)
        
        # Create unique key for tracking inventory
        key = f"{product_id}_{store_id}_{date}"
        
        # Skip if this combination already exists for this date
        if key in inventory_states:
            continue
            
        # Opening stock (if first record for this product-store, random; otherwise use previous closing)
        base_key = f"{product_id}_{store_id}"
        if base_key not in inventory_states:
            opening_stock = random.randint(50, 300)
            inventory_states[base_key] = opening_stock
        else:
            opening_stock = inventory_states[base_key]
        
        # Quantity received (new stock coming in)
        quantity_in = random.choices(
            [0, random.randint(20, 150)], 
            weights=[0.6, 0.4]  # 60% chance of no incoming stock
        )[0]
        
        # Quantity sold/shipped out
        max_out = min(opening_stock + quantity_in, 100)  # Can't sell more than available
        quantity_out = random.randint(0, max(1, max_out))
        
        # Closing stock calculation
        closing_stock = opening_stock + quantity_in - quantity_out
        closing_stock = max(0, closing_stock)  # Ensure non-negative
        
        # Update state for next iteration
        inventory_states[base_key] = closing_stock
        inventory_states[key] = True  # Mark this date as used
        
        # Reorder point (when to order more stock)
        reorder_point = random.randint(20, 80)
        
        # Reorder quantity (how much to order when hitting reorder point)
        reorder_quantity = random.randint(50, 200)
        
        # Unit cost of the product
        unit_cost = round(random.uniform(5.0, 250.0), 2)
        
        data.append({
            "product_id": product_id,
            "store_id": store_id,
            "date": date,
            "opening_stock": opening_stock,
            "quantity_in": quantity_in,
            "quantity_out": quantity_out,
            "closing_stock": closing_stock,
            "reorder_point": reorder_point,
            "reorder_quantity": reorder_quantity,
            "unit_cost": unit_cost
        })
    
    df = pd.DataFrame(data)
    # Sort by date, product_id, and store_id for better readability
    df = df.sort_values(['date', 'product_id', 'store_id']).reset_index(drop=True)
    
    return df


# Esempio di utilizzo
if __name__ == "__main__":

    S = get_settings()
    
    # Genera e salva l'anagrafica prodotti
    max_products = 100  # Numero massimo di prodotti nell'anagrafica
    product_registry = generate_product_mapping(num_products=max_products)
    save_product_mapping(product_registry)

    ##CASE1##
    sales_df = generate_sales_data(num_records=500, num_products=8, num_stores=3)
    sales_df.to_csv(os.path.join(S.PATH_INPUT, "US_sales_data_case1_all_correct.csv"), index=False, sep=S.CSV_DELIMITER)
    ##CASE2##
    sales_df = generate_sales_data(num_records=1000, num_products=50, num_stores=3)
    sales_df.to_csv(os.path.join(S.PATH_INPUT, "FR_sales_data_case2_all_correct.csv"), index=False, sep=S.CSV_DELIMITER)
    ##CASE3##
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    # Convert some values in the 'price' column to strings with "test"
    indices_to_modify = random.sample(range(len(sales_df)), k=5)  # Select 5 random indices
    for idx in indices_to_modify:
        sales_df.at[idx, 'price'] = "test"
    sales_df.to_csv(os.path.join(S.PATH_INPUT, "FR_sales_data_case3_price_is_string.csv"), index=False, sep=S.CSV_DELIMITER)
    
    ##CASE4##
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    # Convert some values in the 'price' column to strings with "test"
    indices_to_modify = random.sample(range(len(sales_df)), k=5)  # Select 5 random indices
    for idx in indices_to_modify:
        sales_df.at[idx, 'quantity'] = "test"
    sales_df.to_csv(os.path.join(S.PATH_INPUT, "US_sales_data_case4_quantity_is_string.csv"), index=False, sep=S.CSV_DELIMITER)
    
    ##CASE5##
    # no nation, dispatcher does not know where to dispatch
    sales_df = generate_sales_data(num_records=800, num_products=8, num_stores=5)
    sales_df.to_csv(os.path.join(S.PATH_INPUT, "sales_data_case5_no_nation.csv"), index=False, sep=S.CSV_DELIMITER)

    ##CASE6##
    #duplicates are present
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    # Duplicate some rows
    duplicates = sales_df.sample(n=10, random_state=1)
    sales_df = pd.concat([sales_df, duplicates], ignore_index=True)
    sales_df.to_csv(os.path.join(S.PATH_INPUT, "US_sales_data_case6_with_duplicates.csv"), index=False, sep=S.CSV_DELIMITER)

    ##CASE7##
    #missing values are present
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    # Introduce missing values randomly in 'price' and 'quantity' columns
    for col in ['price', 'quantity']:
        indices_to_modify = random.sample(range(len(sales_df)), k=5)
        for idx in indices_to_modify:
            sales_df.at[idx, col] = pd.NA
    sales_df.to_csv(os.path.join(S.PATH_INPUT, "FR_sales_data_case7_with_missing_values.csv"), index=False, sep=S.CSV_DELIMITER)

    ##CASE8##
    # missing 'product_id' column
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    sales_df.drop(columns=['product_id'], inplace=True)
    sales_df.to_csv(os.path.join(S.PATH_INPUT, "FR_sales_data_case8_missing_product_id.csv"), index=False, sep=S.CSV_DELIMITER)

    ##CASE9##
    # Out-of-scale values for 'price' and 'quantity'
    sales_df = generate_sales_data(num_records=200, num_products=3, num_stores=3)
    # Set an exaggerated value for 'price'
    sales_df.at[random.randint(0, len(sales_df) - 1), 'price'] = 10000
    # Set an exaggerated value for 'quantity'
    sales_df.at[random.randint(0, len(sales_df) - 1), 'quantity'] = 10000
    sales_df.to_csv(os.path.join(S.PATH_INPUT, "FR_sales_data_case9_out_of_scale.csv"), index=False, sep=S.CSV_DELIMITER)
    ##CASE10##
    # Empty file with only column headers
    empty_df = pd.DataFrame(columns=["product_id", "price", "store_id", "sellout_price", "date", "quantity"])
    empty_df.to_csv(os.path.join(S.PATH_INPUT, "sales_data_case10_empty_file.csv"), index=False, sep=S.CSV_DELIMITER)
    # Empty file
    empty_df = pd.DataFrame()
    empty_df.to_csv(os.path.join(S.PATH_INPUT, "sales_data_case10_empty_file.csv"), index=False, sep=S.CSV_DELIMITER)
    
    # INVENTORY CASES
    print("\nGenerating inventory test cases...")
    
    ##INVENTORY CASE1 - FR##
    inventory_df = generate_inventory_data(num_records=1500, num_products=15, num_stores=4)
    inventory_df.to_csv(os.path.join(S.PATH_INPUT, "FR_inventory_data_case1_all_correct.csv"), index=False, sep=S.CSV_DELIMITER)
    
    ##INVENTORY CASE2 - US##
    inventory_df = generate_inventory_data(num_records=2000, num_products=20, num_stores=6)
    inventory_df.to_csv(os.path.join(S.PATH_INPUT, "US_inventory_data_case2_all_correct.csv"), index=False, sep=S.CSV_DELIMITER)
    
    print("Test files generated in:", S.PATH_INPUT)



