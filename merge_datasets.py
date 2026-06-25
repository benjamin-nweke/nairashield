"""
Script to load, validate, clean, and merge the PaySim and IEEE-CIS fraud detection datasets.
If physical source files are not found, it generates realistic mock data to demonstrate
successful pipeline execution.
"""

import os
import sys
import pandas as pd
import numpy as np
try:
    from pydantic import BaseModel, Field, ValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
from typing import List, Optional

# --- SCHEMA DEFINITIONS FOR VALIDATION ---

if PYDANTIC_AVAILABLE:
    class PaySimSchema(BaseModel):
        step: int
        type: str
        amount: float = Field(ge=0)
        nameOrig: str
        oldbalanceOrg: float
        newbalanceOrig: float
        nameDest: str
        oldbalanceDest: float
        newbalanceDest: float
        isFraud: int = Field(ge=0, le=1)
        isFlaggedFraud: int

    class IeeeCisSchema(BaseModel):
        TransactionID: int
        isFraud: int = Field(ge=0, le=1)
        TransactionDT: int
        TransactionAmt: float = Field(ge=0)
        ProductCD: str
        card1: Optional[float] = None
        card2: Optional[float] = None
        addr1: Optional[float] = None
        P_emaildomain: Optional[str] = None
else:
    PaySimSchema = None
    IeeeCisSchema = None


# --- HELPER: GENERATE MOCK FILES FOR DEMONSTRATION ---

def generate_mock_datasets(paysim_path: str, ieee_path: str):
    """
    Creates mock CSV files matching the real schema of PaySim and IEEE-CIS
    if they are not already present in the workspace.
    """
    print("Generating synthetic mock datasets for demonstration...")
    
    np.random.seed(42)
    n_records = 1000
    
    # 1. Mock PaySim (Mobile Money)
    steps = np.random.randint(1, 10, size=n_records)
    types = np.random.choice(["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"], size=n_records)
    amounts = np.random.uniform(10.0, 500000.0, size=n_records).round(2)
    is_fraud = np.zeros(n_records, dtype=int)
    fraud_indices = np.random.choice(n_records, size=int(0.05 * n_records), replace=False)
    is_fraud[fraud_indices] = 1
    
    # Force fraud transactions to be TRANSFER or CASH_OUT with larger amounts
    for idx in fraud_indices:
        types[idx] = np.random.choice(["TRANSFER", "CASH_OUT"])
        amounts[idx] = round(np.random.uniform(100000.0, 1000000.0), 2)
        
    old_bal_org = np.random.uniform(0.0, 2000000.0, size=n_records).round(2)
    new_bal_org = np.clip(old_bal_org - amounts, 0.0, None).round(2)
    for idx in fraud_indices:
        new_bal_org[idx] = 0.0
        
    paysim_data = {
        "step": steps,
        "type": types,
        "amount": amounts,
        "nameOrig": [f"C{np.random.randint(10000000, 99999999)}" for _ in range(n_records)],
        "oldbalanceOrg": old_bal_org,
        "newbalanceOrig": new_bal_org,
        "nameDest": [f"C{np.random.randint(10000000, 99999999)}" if t in ["TRANSFER", "CASH_OUT"] else f"M{np.random.randint(10000000, 99999999)}" for t in types],
        "oldbalanceDest": np.random.uniform(0.0, 1000000.0, size=n_records).round(2),
        "newbalanceDest": np.random.uniform(0.0, 2000000.0, size=n_records).round(2),
        "isFraud": is_fraud,
        "isFlaggedFraud": np.zeros(n_records, dtype=int)
    }
    pd.DataFrame(paysim_data).to_csv(paysim_path, index=False)
    print(f"Created mock PaySim data (1000 rows) at: {paysim_path}")

    # 2. Mock IEEE-CIS (Card Transactions)
    tx_ids = np.arange(2987000, 2987000 + n_records)
    ieee_is_fraud = np.zeros(n_records, dtype=int)
    ieee_fraud_indices = np.random.choice(n_records, size=int(0.05 * n_records), replace=False)
    ieee_is_fraud[ieee_fraud_indices] = 1
    
    tx_dts = np.arange(86400, 86400 + n_records * 10, 10)
    tx_amts = np.random.uniform(5.0, 1000.0, size=n_records).round(2)
    for idx in ieee_fraud_indices:
        tx_amts[idx] = round(np.random.uniform(100.0, 5000.0), 2)
        
    product_cds = np.random.choice(["W", "H", "C", "S", "R"], size=n_records)
    for idx in ieee_fraud_indices:
        product_cds[idx] = np.random.choice(["W", "H"])
        
    card1 = np.random.uniform(1000.0, 20000.0, size=n_records).round(0)
    card2 = np.random.uniform(100.0, 600.0, size=n_records).round(0)
    nan_mask = np.random.random(n_records) < 0.1
    card2[nan_mask] = np.nan
    
    addr1 = np.random.uniform(100.0, 500.0, size=n_records).round(0)
    
    emails = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "anonymous.com", np.nan]
    p_emails = np.random.choice(emails, size=n_records)
    
    ieee_data = {
        "TransactionID": tx_ids,
        "isFraud": ieee_is_fraud,
        "TransactionDT": tx_dts,
        "TransactionAmt": tx_amts,
        "ProductCD": product_cds,
        "card1": card1,
        "card2": card2,
        "addr1": addr1,
        "P_emaildomain": p_emails
    }
    pd.DataFrame(ieee_data).to_csv(ieee_path, index=False)
    print(f"Created mock IEEE-CIS data (1000 rows) at: {ieee_path}\n")


# --- DATA QUALITY & INTEGRITY CHECKS ---

def validate_dataframe(df: pd.DataFrame, schema_class, dataset_name: str) -> bool:
    """
    Validates a subset of the Pandas DataFrame rows using Pydantic schemas.
    """
    if not PYDANTIC_AVAILABLE:
        print(f"[Warning] Pydantic not installed. Skipping schema validation for {dataset_name}.")
        return True
        
    print(f"Validating {dataset_name} columns and data integrity...")
    # Convert numpy NaN values to None to satisfy Pydantic's Optional types
    df_clean = df.replace({np.nan: None})
    records = df_clean.to_dict(orient="records")
    errors = 0
    
    for idx, record in enumerate(records):
        try:
            # Pydantic parses values and asserts types/limits
            schema_class(**record)
        except ValidationError as e:
            print(f"[Warning] Validation error at row {idx} in {dataset_name}: {e.json()}")
            errors += 1
            if errors > 5:
                print("[Error] Too many validation failures. Aborting.")
                return False
                
    if errors == 0:
        print(f"✔ All rows in {dataset_name} successfully validated against baseline schema.")
        return True
    return False


# --- LOADING, CLEANING, AND MERGING PIPELINE ---

def run_pipeline(paysim_csv: str, ieee_csv: str):
    # Ensure source files exist
    if not os.path.exists(paysim_csv) or not os.path.exists(ieee_csv):
        generate_mock_datasets(paysim_csv, ieee_csv)

    # 1. Load Raw Datasets
    print("Loading datasets...")
    df_paysim = pd.read_csv(paysim_csv)
    df_ieee = pd.read_csv(ieee_csv)

    print(f"Loaded PaySim: {df_paysim.shape[0]} rows, {df_paysim.shape[1]} columns.")
    print(f"Loaded IEEE-CIS: {df_ieee.shape[0]} rows, {df_ieee.shape[1]} columns.\n")

    # 2. Schema Validation
    validate_dataframe(df_paysim, PaySimSchema, "PaySim")
    validate_dataframe(df_ieee, IeeeCisSchema, "IEEE-CIS")
    print()

    # 3. Align and Map to Common Schema
    # Common Target columns: transaction_id, amount, is_fraud, channel, source_dataset
    print("Transforming and aligning schemas...")
    
    # Transform PaySim
    df_paysim_aligned = pd.DataFrame()
    df_paysim_aligned["transaction_id"] = "PAYSIM_" + df_paysim["step"].astype(str) + "_" + df_paysim.index.astype(str)
    df_paysim_aligned["amount"] = df_paysim["amount"].astype(float)
    df_paysim_aligned["is_fraud"] = df_paysim["isFraud"].astype(int)
    df_paysim_aligned["channel"] = df_paysim["type"].astype(str)
    df_paysim_aligned["source_dataset"] = "PaySim"

    # Transform IEEE-CIS
    df_ieee_aligned = pd.DataFrame()
    df_ieee_aligned["transaction_id"] = "IEEE_" + df_ieee["TransactionID"].astype(str)
    df_ieee_aligned["amount"] = df_ieee["TransactionAmt"].astype(float)
    df_ieee_aligned["is_fraud"] = df_ieee["isFraud"].astype(int)
    # Map IEEE-CIS ProductCD to represent channel category
    product_map = {"W": "CARD_WEB", "H": "CARD_HOST", "C": "CARD_PHONE", "S": "CARD_STORE", "R": "CARD_RECURRING"}
    df_ieee_aligned["channel"] = df_ieee["ProductCD"].map(product_map).fillna("CARD_OTHER")
    df_ieee_aligned["source_dataset"] = "IEEE-CIS"

    # 4. Merge DataFrames
    print("Merging aligned datasets...")
    merged_df = pd.concat([df_paysim_aligned, df_ieee_aligned], ignore_index=True)
    
    # 5. Type and Null Checking on Merged DataFrame
    print("\n--- Merged DataFrame Inspection ---")
    print(merged_df.info())
    print("\nChecking for Null Values:")
    print(merged_df.isnull().sum())
    
    # 6. Summary Statistics
    print("\n--- Fraud Summary ---")
    summary = merged_df.groupby(["source_dataset", "is_fraud"]).size().unstack(fill_value=0)
    summary.columns = ["Legitimate (0)", "Fraudulent (1)"]
    summary["Total"] = summary["Legitimate (0)"] + summary["Fraudulent (1)"]
    summary["Fraud Rate (%)"] = round((summary["Fraudulent (1)"] / summary["Total"]) * 100, 2)
    print(summary)
    
    print("\nOverall Counts Across Merged Dataset:")
    counts = merged_df["is_fraud"].value_counts()
    legit = counts.get(0, 0)
    fraud = counts.get(1, 0)
    print(f"Legitimate Transactions: {legit:,}")
    print(f"Fraudulent Transactions: {fraud:,}")
    print(f"Total Combined Records  : {len(merged_df):,}")
    
    return merged_df

if __name__ == "__main__":
    paysim_file = "data_paysim_sample.csv"
    ieee_file = "data_ieee_sample.csv"
    
    merged_data = run_pipeline(paysim_file, ieee_file)
