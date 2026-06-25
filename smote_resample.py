"""
Script to apply SMOTE (Synthetic Minority Over-sampling Technique)
to the training split of the fraud detection dataset.
Supports both pandas/imblearn and pure-Python zero-dependency fallbacks.
"""

import os
import random
import math
import csv

# --- CHECK DEPENDENCIES ---
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from imblearn.over_sampling import SMOTE
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False


# =====================================================================
# PURE PYTHON IMPLEMENTATION OF SMOTE (Zero-Dependency Fallback)
# =====================================================================

def simple_smote_py(X_minority: list, target_count: int, k: int = 3) -> list:
    """
    Custom lightweight SMOTE implementation.
    Generates synthetic samples by interpolating between minority class neighbors.
    """
    synthetic_samples = []
    num_samples_to_generate = target_count - len(X_minority)
    
    if num_samples_to_generate <= 0 or not X_minority:
        return []
        
    for _ in range(num_samples_to_generate):
        # 1. Choose a random minority sample
        sample = random.choice(X_minority)
        
        # 2. Compute Euclidean distance to all other minority samples
        distances = []
        for other in X_minority:
            if other == sample:
                continue
            # Euclidean distance formula
            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(sample, other)))
            distances.append((dist, other))
            
        distances.sort(key=lambda x: x[0])
        
        # 3. Get k-nearest neighbors
        k_neighbors = distances[:k]
        
        if k_neighbors:
            # Pick a random neighbor
            neighbor = random.choice(k_neighbors)[1]
            # Interpolate: synthetic = sample + ratio * (neighbor - sample)
            ratio = random.random()
            synthetic = [s + ratio * (n - s) for s, n in zip(sample, neighbor)]
            synthetic_samples.append(synthetic)
        else:
            # If no other neighbors exist, copy with slight noise jitter
            synthetic = [s + random.uniform(-0.01, 0.01) for s in sample]
            synthetic_samples.append(synthetic)
            
    return synthetic_samples


# =====================================================================
# PRE-SPLITTING AND RESAMPLING FLOW
# =====================================================================

def run_smote_pipeline():
    csv_filename = "processed_fraud_data.csv"
    if not os.path.exists(csv_filename):
        print(f"[Error] Missing processed dataset '{csv_filename}'. Please run preprocess_pipeline.py first.")
        return

    # Define target variable name and numerical feature keys
    target_col = "is_fraud"
    
    if PANDAS_AVAILABLE:
        print("[System Check] Pandas detected. Running Pandas SMOTE Pipeline...")
        
        # Load dataset
        df = pd.read_csv(csv_filename)
        
        # Separate features and target label
        X = df.drop(columns=["transaction_id", target_col])
        y = df[target_col]
        
        # 1. Split into Train (80%) and Test (20%) using random state
        train_df = df.sample(frac=0.8, random_state=42)
        test_df = df.drop(train_df.index)
        
        X_train = train_df.drop(columns=["transaction_id", target_col])
        y_train = train_df[target_col]
        
        X_test = test_df.drop(columns=["transaction_id", target_col])
        y_test = test_df[target_col]
        
        # Print distributions before resampling
        print("\n--- Train/Test Split (Before SMOTE) ---")
        print(f"Train Set Total Count: {len(train_df)}")
        print(f"  - Legitimate (0): {sum(y_train == 0)}")
        print(f"  - Fraudulent (1): {sum(y_train == 1)}  ({sum(y_train == 1)/len(y_train)*100:.1f}%)")
        print(f"Test Set Total Count : {len(test_df)}")
        print(f"  - Legitimate (0): {sum(y_test == 0)}")
        print(f"  - Fraudulent (1): {sum(y_test == 1)}  ({sum(y_test == 1)/len(y_test)*100:.1f}%)")
        
        # 2. Resample the training partition
        if IMBLEARN_AVAILABLE:
            print("\nApplying imbalanced-learn SMOTE...")
            smote = SMOTE(random_state=42, k_neighbors=min(2, sum(y_train == 1) - 1))
            X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
        else:
            print("\n[Imblearn Missing] Running Custom Matrix SMOTE...")
            # Extract minority indices
            minority_coords = X_train[y_train == 1].values.tolist()
            majority_count = sum(y_train == 0)
            
            # Generate synthetic coordinates
            syn_samples = simple_smote_py(minority_coords, target_count=majority_count, k=2)
            
            # Create synthetic DataFrame
            syn_df = pd.DataFrame(syn_samples, columns=X_train.columns)
            syn_df[target_col] = 1
            
            # Concatenate resampled frames
            resampled_train = pd.concat([train_df, syn_df], ignore_index=True)
            X_train_res = resampled_train.drop(columns=["transaction_id", target_col], errors="ignore")
            y_train_res = resampled_train[target_col]

        # Print distributions after resampling
        print("\n--- Training Set Class Distribution (After SMOTE) ---")
        print(f"Resampled Train Count: {len(X_train_res)}")
        print(f"  - Legitimate (0): {sum(y_train_res == 0)}")
        print(f"  - Fraudulent (1): {sum(y_train_res == 1)}  ({sum(y_train_res == 1)/len(y_train_res)*100:.1f}%)")
        
        # Save splits
        train_res = pd.concat([X_train_res, y_train_res], axis=1)
        test_final = pd.concat([X_test, y_test], axis=1)
        train_res.to_csv("train_smote.csv", index=False)
        test_final.to_csv("test.csv", index=False)
        
    else:
        print("[System Check] Pandas NOT detected. Running Resilient Pure-Python Split & Resampling...\n")
        
        # Load dataset using built-in csv
        with open(csv_filename, mode="r", newline="", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            
        # Extract headers (excluding ID and Target)
        headers = [h for h in reader[0].keys() if h not in ["transaction_id", target_col]]
        
        # Split data randomly (80% Train, 20% Test)
        random.seed(42)
        random.shuffle(reader)
        split_idx = int(len(reader) * 0.8)
        train_raw = reader[:split_idx]
        test_raw = reader[split_idx:]
        
        # Categorize training samples
        train_legit = [r for r in train_raw if int(r[target_col]) == 0]
        train_fraud = [r for r in train_raw if int(r[target_col]) == 1]
        
        # Print distributions before resampling
        print("\n--- Train/Test Split (Before SMOTE) ---")
        print(f"Train Set Total Count: {len(train_raw)}")
        print(f"  - Legitimate (0): {len(train_legit)}")
        print(f"  - Fraudulent (1): {len(train_fraud)}  ({len(train_fraud)/len(train_raw)*100:.1f}%)")
        print(f"Test Set Total Count : {len(test_raw)}")
        print(f"  - Legitimate (0): {sum(1 for r in test_raw if int(r[target_col]) == 0)}")
        print(f"  - Fraudulent (1): {sum(1 for r in test_raw if int(r[target_col]) == 1)}  ({sum(1 for r in test_raw if int(r[target_col]) == 1)/len(test_raw)*100:.1f}%)")
        
        # Extract minority coordinates for SMOTE
        minority_coords = []
        for r in train_fraud:
            minority_coords.append([float(r[h]) for h in headers])
            
        # Run custom SMOTE
        target_count = len(train_legit)
        syn_features = simple_smote_py(minority_coords, target_count=target_count, k=2)
        
        # Reconstruct rows
        resampled_train_list = []
        # Add original majority and minority rows
        for r in train_raw:
            row_dict = {h: float(r[h]) for h in headers}
            row_dict[target_col] = int(r[target_col])
            resampled_train_list.append(row_dict)
            
        # Add synthetic minority rows
        for features in syn_features:
            row_dict = {h: f for h, f in zip(headers, features)}
            row_dict[target_col] = 1
            resampled_train_list.append(row_dict)
            
        # Print distributions after resampling
        res_legit = sum(1 for r in resampled_train_list if r[target_col] == 0)
        res_fraud = sum(1 for r in resampled_train_list if r[target_col] == 1)
        print("\n--- Training Set Class Distribution (After SMOTE) ---")
        print(f"Resampled Train Count: {len(resampled_train_list)}")
        print(f"  - Legitimate (0): {res_legit}")
        print(f"  - Fraudulent (1): {res_fraud}  ({res_fraud/len(resampled_train_list)*100:.1f}%)")
        
        # Save splits
        with open("train_smote.csv", mode="w", newline="", encoding="utf-8") as out_train:
            writer = csv.DictWriter(out_train, fieldnames=headers + [target_col])
            writer.writeheader()
            writer.writerows(resampled_train_list)
            
        with open("test.csv", mode="w", newline="", encoding="utf-8") as out_test:
            test_rows = []
            for r in test_raw:
                row_dict = {h: float(r[h]) for h in headers}
                row_dict[target_col] = int(r[target_col])
                test_rows.append(row_dict)
            writer = csv.DictWriter(out_test, fieldnames=headers + [target_col])
            writer.writeheader()
            writer.writerows(test_rows)

    print("\nFile Output Confirmation:")
    print("[OK] Resampled training set saved to: train_smote.csv")
    print("[OK] Unbalanced validation test set saved to: test.csv")

if __name__ == "__main__":
    run_smote_pipeline()
