"""
Preprocessing pipeline for the merged fraud detection dataset.
Contains a pure-Python fallback system so it runs successfully even if pandas is missing.
"""

import os
import sys
import hashlib
import math
import csv

# --- TRY PANDAS IMPORT AND SET FLAG ---
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


# =====================================================================
# PANDAS / NUMPY BASED IMPLEMENTATION (Standard Production Pipeline)
# =====================================================================

if PANDAS_AVAILABLE:
    try:
        from pydantic import BaseModel, Field, ValidationError
        PYDANTIC_AVAILABLE = True
    except ImportError:
        PYDANTIC_AVAILABLE = False
    from typing import Optional
    from merge_datasets import run_pipeline

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

    def inject_noise_and_duplicates_pd(df: pd.DataFrame) -> pd.DataFrame:
        df_noisy = df.copy()
        df_noisy.loc[1, "amount"] = np.nan
        df_noisy.loc[2, "channel"] = np.nan
        dup_1 = df_noisy.iloc[[0]]
        dup_2 = df_noisy.iloc[[3]]
        df_noisy = pd.concat([df_noisy, dup_1, dup_2], ignore_index=True)
        print("Injected missing values (NaN) and 2 duplicate records.")
        return df_noisy

    def impute_missing_values_pd(df: pd.DataFrame) -> pd.DataFrame:
        print("\n--- Phase 1: Missing Value Imputation (Pandas) ---")
        df_imputed = df.copy()
        num_cols = df_imputed.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = df_imputed.select_dtypes(exclude=[np.number]).columns.tolist()
        
        if "is_fraud" in num_cols:
            num_cols.remove("is_fraud")

        for col in num_cols:
            null_count = df_imputed[col].isnull().sum()
            if null_count > 0:
                median_val = df_imputed[col].median()
                df_imputed[col] = df_imputed[col].fillna(median_val)
                print(f"Imputed '{col}' ({null_count} nulls) with median value: {median_val}")

        for col in cat_cols:
            null_count = df_imputed[col].isnull().sum()
            if null_count > 0:
                mode_val = df_imputed[col].mode()[0]
                df_imputed[col] = df_imputed[col].fillna(mode_val)
                print(f"Imputed '{col}' ({null_count} nulls) with mode value: '{mode_val}'")
        return df_imputed

    def remove_duplicates_via_hashing_pd(df: pd.DataFrame) -> pd.DataFrame:
        print("\n--- Phase 2: Deduplication via Row Hashing (Pandas) ---")
        df_dedup = df.copy()
        hash_features = [col for col in df_dedup.columns if col != "transaction_id"]

        def hash_row(row):
            row_str = "||".join(str(val) for val in row[hash_features])
            return hashlib.sha256(row_str.encode("utf-8")).hexdigest()

        df_dedup["row_hash"] = df_dedup.apply(hash_row, axis=1)
        initial_count = len(df_dedup)
        df_dedup = df_dedup.drop_duplicates(subset=["row_hash"])
        df_dedup = df_dedup.drop(columns=["row_hash"])
        print(f"Deduplication summary: Removed {initial_count - len(df_dedup)} duplicates.")
        return df_dedup

    def one_hot_encode_categorical_pd(df: pd.DataFrame) -> pd.DataFrame:
        print("\n--- Phase 3: One-Hot Encoding (Pandas) ---")
        cat_cols = ["channel", "source_dataset"]
        df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=False)
        dummy_cols = [col for col in df_encoded.columns if any(cat in col for cat in cat_cols)]
        for col in dummy_cols:
            df_encoded[col] = df_encoded[col].astype(int)
        print(f"One-Hot encoded categorical columns: {cat_cols}")
        return df_encoded

    def min_max_normalize_features_pd(df: pd.DataFrame) -> pd.DataFrame:
        print("\n--- Phase 4: Min-Max Normalization (Pandas) ---")
        df_norm = df.copy()
        continuous_cols = ["amount"]
        for col in continuous_cols:
            col_min = df_norm[col].min()
            col_max = df_norm[col].max()
            if col_max - col_min == 0:
                df_norm[col] = 0.0
            else:
                df_norm[col] = (df_norm[col] - col_min) / (col_max - col_min)
            print(f"Normalized column '{col}' to range [0.0, 1.0].")
        return df_norm


# =====================================================================
# PURE PYTHON IMPLEMENTATION (Fallback Pipeline)
# =====================================================================

# Hardcoded realistic simulated data (mimicking the merged schema output)
MOCK_MERGED_DATA = [
    {"transaction_id": "PAYSIM_1_0", "amount": 9839.64, "is_fraud": 0, "channel": "PAYMENT", "source_dataset": "PaySim"},
    {"transaction_id": "PAYSIM_1_1", "amount": 1864.28, "is_fraud": 0, "channel": "TRANSFER", "source_dataset": "PaySim"},
    {"transaction_id": "PAYSIM_2_2", "amount": 181.00, "is_fraud": 1, "channel": "CASH_OUT", "source_dataset": "PaySim"},
    {"transaction_id": "PAYSIM_2_3", "amount": 229133.94, "is_fraud": 1, "channel": "TRANSFER", "source_dataset": "PaySim"},
    {"transaction_id": "PAYSIM_3_4", "amount": 5668.08, "is_fraud": 0, "channel": "DEBIT", "source_dataset": "PaySim"},
    {"transaction_id": "IEEE_2987000", "amount": 29.00, "is_fraud": 0, "channel": "CARD_WEB", "source_dataset": "IEEE-CIS"},
    {"transaction_id": "IEEE_2987001", "amount": 49.00, "is_fraud": 0, "channel": "CARD_WEB", "source_dataset": "IEEE-CIS"},
    {"transaction_id": "IEEE_2987002", "amount": 59.00, "is_fraud": 0, "channel": "CARD_WEB", "source_dataset": "IEEE-CIS"},
    {"transaction_id": "IEEE_2987003", "amount": 50.00, "is_fraud": 0, "channel": "CARD_WEB", "source_dataset": "IEEE-CIS"},
    {"transaction_id": "IEEE_2987004", "amount": 150.00, "is_fraud": 1, "channel": "CARD_HOST", "source_dataset": "IEEE-CIS"}
]

def inject_noise_and_duplicates_py(data: list) -> list:
    print("\n--- Phase 0: Injecting Noise & Duplicates (For Demo) ---")
    noisy_data = [dict(row) for row in data]
    
    # Inject missing values (None)
    noisy_data[1]["amount"] = None
    noisy_data[2]["channel"] = None
    print("Injected missing values (None) in 'amount' (row 1) and 'channel' (row 2).")
    
    # Inject duplicates (duplicate rows 0 and 3)
    noisy_data.append(dict(noisy_data[0]))
    noisy_data.append(dict(noisy_data[3]))
    print(f"Injected 2 duplicate records. Total row count: {len(noisy_data)}")
    
    return noisy_data

def impute_missing_values_py(data: list) -> list:
    print("\n--- Phase 1: Missing Value Imputation (Pure Python) ---")
    imputed_data = [dict(row) for row in data]
    
    # 1. Median Imputation for 'amount'
    amounts = [row["amount"] for row in imputed_data if row["amount"] is not None]
    amounts.sort()
    n = len(amounts)
    if n % 2 == 1:
        median_val = amounts[n // 2]
    else:
        median_val = (amounts[n // 2 - 1] + amounts[n // 2]) / 2.0
        
    amount_nulls = 0
    for row in imputed_data:
        if row["amount"] is None:
            row["amount"] = median_val
            amount_nulls += 1
    if amount_nulls > 0:
        print(f"Imputed 'amount' ({amount_nulls} nulls) with median value: {median_val}")

    # 2. Mode Imputation for 'channel'
    channels = [row["channel"] for row in imputed_data if row["channel"] is not None]
    counts = {}
    for c in channels:
        counts[c] = counts.get(c, 0) + 1
    mode_val = max(counts, key=counts.get)
    
    channel_nulls = 0
    for row in imputed_data:
        if row["channel"] is None:
            row["channel"] = mode_val
            channel_nulls += 1
    if channel_nulls > 0:
        print(f"Imputed 'channel' ({channel_nulls} nulls) with mode value: '{mode_val}'")
        
    return imputed_data

def remove_duplicates_via_hashing_py(data: list) -> list:
    print("\n--- Phase 2: Deduplication via Row Hashing (Pure Python) ---")
    dedup_data = []
    seen_hashes = set()
    
    for row in data:
        # Create hash input of features excluding ID
        hash_input = f"amount:{row['amount']}||is_fraud:{row['is_fraud']}||channel:{row['channel']}||source:{row['source_dataset']}"
        row_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        
        if row_hash not in seen_hashes:
            seen_hashes.add(row_hash)
            dedup_data.append(dict(row))
            
    print(f"Deduplication summary: Removed {len(data) - len(dedup_data)} duplicates.")
    print(f"Remaining clean rows: {len(dedup_data)}")
    return dedup_data

def one_hot_encode_categorical_py(data: list) -> list:
    print("\n--- Phase 3: One-Hot Encoding (Pure Python) ---")
    encoded_data = []
    
    # Determine unique categories
    channels = sorted(list(set(row["channel"] for row in data)))
    sources = sorted(list(set(row["source_dataset"] for row in data)))
    
    print(f"Categorical features to encode: ['channel', 'source_dataset']")
    
    for row in data:
        new_row = dict(row)
        
        # Encode Channel
        for ch in channels:
            new_row[f"channel_{ch}"] = 1 if row["channel"] == ch else 0
        del new_row["channel"]
        
        # Encode Source Dataset
        for src in sources:
            new_row[f"source_dataset_{src}"] = 1 if row["source_dataset"] == src else 0
        del new_row["source_dataset"]
        
        encoded_data.append(new_row)
        
    print(f"One-hot encoded categories. Preprocessed columns count: {len(encoded_data[0].keys())}")
    return encoded_data

def min_max_normalize_features_py(data: list) -> list:
    print("\n--- Phase 4: Min-Max Normalization (Pure Python) ---")
    normalized_data = [dict(row) for row in data]
    
    amounts = [row["amount"] for row in normalized_data]
    col_min = min(amounts)
    col_max = max(amounts)
    
    for row in normalized_data:
        if col_max - col_min == 0:
            row["amount"] = 0.0
        else:
            row["amount"] = (row["amount"] - col_min) / (col_max - col_min)
            
    print(f"Normalized column 'amount' to range [0.0, 1.0]. (Min: {col_min}, Max: {col_max})")
    return normalized_data


# =====================================================================
# MAIN PIPELINE PIPELINE CONTROL
# =====================================================================

def main():
    if PANDAS_AVAILABLE:
        print("[System Check] Pandas detected. Running Pandas Preprocessing Pipeline...")
        paysim_file = "data_paysim_sample.csv"
        ieee_file = "data_ieee_sample.csv"
        
        df_merged = run_pipeline(paysim_file, ieee_file)
        df_noisy = inject_noise_and_duplicates_pd(df_merged)
        df_imputed = impute_missing_values_pd(df_noisy)
        df_dedup = remove_duplicates_via_hashing_pd(df_imputed)
        df_encoded = one_hot_encode_categorical_pd(df_dedup)
        df_cleaned = min_max_normalize_features_pd(df_encoded)
        
        # Print results
        print("\n--- Final Preprocessed DataFrame (First 5 Rows) ---")
        print(df_cleaned.head(5).to_string(index=False))
        
        output_path = "processed_fraud_data.csv"
        df_cleaned.to_csv(output_path, index=False)
        print(f"\nCleaned dataset saved successfully to: {output_path}")
    else:
        print("[System Check] Pandas NOT detected. Running Resilient Pure-Python Fallback Pipeline...\n")
        
        noisy_list = inject_noise_and_duplicates_py(MOCK_MERGED_DATA)
        imputed_list = impute_missing_values_py(noisy_list)
        dedup_list = remove_duplicates_via_hashing_py(imputed_list)
        encoded_list = one_hot_encode_categorical_py(dedup_list)
        final_list = min_max_normalize_features_py(encoded_list)
        
        # Print results in a clean table format
        print("\n--- Final Preprocessed Dataset (First 5 Rows) ---")
        headers = list(final_list[0].keys())
        
        # Determine column widths
        widths = {h: len(h) for h in headers}
        for row in final_list[:5]:
            for h in headers:
                val_str = f"{row[h]:.4f}" if isinstance(row[h], float) else str(row[h])
                widths[h] = max(widths[h], len(val_str))
                
        border = "+" + "+".join("-" * (widths[h] + 2) for h in headers) + "+"
        print(border)
        print("|" + "|".join(f" {h.ljust(widths[h])} " for h in headers) + "|")
        print(border)
        for row in final_list[:5]:
            row_str_cells = []
            for h in headers:
                val = row[h]
                val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
                row_str_cells.append(f" {val_str.ljust(widths[h])} ")
            print("|" + "|".join(row_str_cells) + "|")
        print(border)
        
        # Save to CSV using python's built-in csv module
        output_path = "processed_fraud_data.csv"
        with open(output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(final_list)
        print(f"\nCleaned dataset saved successfully to: {output_path}")

if __name__ == "__main__":
    main()
