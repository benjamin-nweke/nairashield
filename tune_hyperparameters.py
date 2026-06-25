"""
Hyperparameter tuning script for XGBoost and LightGBM models in NairaShield.
Uses Optuna (Bayesian optimization) when available. Falls back to a robust,
high-performance Stratified K-Fold randomized search optimizer (100 trials)
if Optuna is missing, ensuring functionality in offline environments.
Optimizes validation F1-score and saves the best parameters to a JSON config file.
"""

import os
import json
import numpy as np
import pandas as pd
import xgboost as xgb
import lightgbm as lgb
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold
from imblearn.over_sampling import SMOTE

try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

def load_and_split_data():
    csv_filename = "processed_fraud_data.csv"
    if not os.path.exists(csv_filename):
        raise FileNotFoundError(f"Missing processed dataset '{csv_filename}'. Please run preprocess_pipeline.py first.")
    
    target_col = "is_fraud"
    df = pd.read_csv(csv_filename)
    X = df.drop(columns=["transaction_id", target_col])
    y = df[target_col]
    
    # 80/20 Train/Test Split matching train_models.py
    np.random.seed(42)
    shuffled_indices = np.random.permutation(len(df))
    split_idx = int(len(df) * 0.8)
    
    train_idx = shuffled_indices[:split_idx]
    test_idx = shuffled_indices[split_idx:]
    
    X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
    X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
    
    return X_train, y_train, X_test, y_test

def tune_xgboost(X_train, y_train):
    if OPTUNA_AVAILABLE:
        print("\n[Optuna] Tuning XGBoost Hyperparameters (100 Trials)...")
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 500),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.5, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1.0, 20.0),
                'random_state': 42,
                'use_label_encoder': False,
                'eval_metric': 'logloss',
                'n_jobs': -1
            }
            
            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            f1_scores = []
            
            for train_idx, val_idx in skf.split(X_train, y_train):
                X_tr, y_tr = X_train.iloc[train_idx], y_train.iloc[train_idx]
                X_val, y_val = X_train.iloc[val_idx], y_train.iloc[val_idx]
                
                k_neigh = min(2, sum(y_tr == 1) - 1)
                if k_neigh >= 1:
                    smote = SMOTE(random_state=42, k_neighbors=k_neigh)
                    X_tr_res, y_tr_res = smote.fit_resample(X_tr, y_tr)
                else:
                    X_tr_res, y_tr_res = X_tr, y_tr
                    
                model = xgb.XGBClassifier(**params)
                model.fit(X_tr_res, y_tr_res)
                preds = model.predict(X_val)
                f1_scores.append(f1_score(y_val, preds, zero_division=0))
                
            return np.mean(f1_scores)

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=100)
        print(f"[OK] XGBoost Optimization Complete. Best Cross-Validation F1-Score: {study.best_value:.4f}")
        return study.best_params
    else:
        print("\n[Fallback Optimizer] Optuna missing. Running 100-Trial Randomized Search for XGBoost...")
        np.random.seed(42)
        best_f1 = -1.0
        best_params = {}
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        
        for trial_idx in range(100):
            params = {
                'n_estimators': int(np.random.randint(50, 501)),
                'max_depth': int(np.random.randint(3, 11)),
                'learning_rate': float(10 ** np.random.uniform(np.log10(0.01), np.log10(0.3))),
                'subsample': float(np.random.uniform(0.5, 1.0)),
                'colsample_bytree': float(np.random.uniform(0.5, 1.0)),
                'min_child_weight': int(np.random.randint(1, 11)),
                'scale_pos_weight': float(np.random.uniform(1.0, 20.0)),
                'random_state': 42,
                'use_label_encoder': False,
                'eval_metric': 'logloss',
                'n_jobs': -1
            }
            
            f1_scores = []
            for train_idx, val_idx in skf.split(X_train, y_train):
                X_tr, y_tr = X_train.iloc[train_idx], y_train.iloc[train_idx]
                X_val, y_val = X_train.iloc[val_idx], y_train.iloc[val_idx]
                
                k_neigh = min(2, sum(y_tr == 1) - 1)
                if k_neigh >= 1:
                    smote = SMOTE(random_state=42, k_neighbors=k_neigh)
                    X_tr_res, y_tr_res = smote.fit_resample(X_tr, y_tr)
                else:
                    X_tr_res, y_tr_res = X_tr, y_tr
                    
                model = xgb.XGBClassifier(**params)
                model.fit(X_tr_res, y_tr_res)
                preds = model.predict(X_val)
                f1_scores.append(f1_score(y_val, preds, zero_division=0))
                
            mean_f1 = np.mean(f1_scores)
            if (trial_idx + 1) % 10 == 0:
                print(f"  |-- Trial {trial_idx + 1}/100 | Current Best F1-Score: {max(best_f1, mean_f1):.4f}")
                
            if mean_f1 > best_f1:
                best_f1 = mean_f1
                best_params = params
                
        print(f"[OK] XGBoost Optimization Complete. Best Cross-Validation F1-Score: {best_f1:.4f}")
        return best_params

def tune_lightgbm(X_train, y_train):
    if OPTUNA_AVAILABLE:
        print("\n[Optuna] Tuning LightGBM Hyperparameters (100 Trials)...")
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 500),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'num_leaves': trial.suggest_int('num_leaves', 15, 255),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.5, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
                'min_child_samples': trial.suggest_int('min_child_samples', 5, 50),
                'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1.0, 20.0),
                'random_state': 42,
                'verbose': -1,
                'n_jobs': -1
            }
            
            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            f1_scores = []
            
            for train_idx, val_idx in skf.split(X_train, y_train):
                X_tr, y_tr = X_train.iloc[train_idx], y_train.iloc[train_idx]
                X_val, y_val = X_train.iloc[val_idx], y_train.iloc[val_idx]
                
                k_neigh = min(2, sum(y_tr == 1) - 1)
                if k_neigh >= 1:
                    smote = SMOTE(random_state=42, k_neighbors=k_neigh)
                    X_tr_res, y_tr_res = smote.fit_resample(X_tr, y_tr)
                else:
                    X_tr_res, y_tr_res = X_tr, y_tr
                    
                model = lgb.LGBMClassifier(**params)
                model.fit(X_tr_res, y_tr_res)
                preds = model.predict(X_val)
                f1_scores.append(f1_score(y_val, preds, zero_division=0))
                
            return np.mean(f1_scores)

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=100)
        print(f"[OK] LightGBM Optimization Complete. Best Cross-Validation F1-Score: {study.best_value:.4f}")
        return study.best_params
    else:
        print("\n[Fallback Optimizer] Optuna missing. Running 100-Trial Randomized Search for LightGBM...")
        np.random.seed(101) # different seed for LightGBM
        best_f1 = -1.0
        best_params = {}
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        
        for trial_idx in range(100):
            params = {
                'n_estimators': int(np.random.randint(50, 501)),
                'max_depth': int(np.random.randint(3, 11)),
                'num_leaves': int(np.random.randint(15, 256)),
                'learning_rate': float(10 ** np.random.uniform(np.log10(0.01), np.log10(0.3))),
                'subsample': float(np.random.uniform(0.5, 1.0)),
                'colsample_bytree': float(np.random.uniform(0.5, 1.0)),
                'min_child_samples': int(np.random.randint(5, 51)),
                'scale_pos_weight': float(np.random.uniform(1.0, 20.0)),
                'random_state': 42,
                'verbose': -1,
                'n_jobs': -1
            }
            
            f1_scores = []
            for train_idx, val_idx in skf.split(X_train, y_train):
                X_tr, y_tr = X_train.iloc[train_idx], y_train.iloc[train_idx]
                X_val, y_val = X_train.iloc[val_idx], y_train.iloc[val_idx]
                
                k_neigh = min(2, sum(y_tr == 1) - 1)
                if k_neigh >= 1:
                    smote = SMOTE(random_state=42, k_neighbors=k_neigh)
                    X_tr_res, y_tr_res = smote.fit_resample(X_tr, y_tr)
                else:
                    X_tr_res, y_tr_res = X_tr, y_tr
                    
                model = lgb.LGBMClassifier(**params)
                model.fit(X_tr_res, y_tr_res)
                preds = model.predict(X_val)
                f1_scores.append(f1_score(y_val, preds, zero_division=0))
                
            mean_f1 = np.mean(f1_scores)
            if (trial_idx + 1) % 10 == 0:
                print(f"  |-- Trial {trial_idx + 1}/100 | Current Best F1-Score: {max(best_f1, mean_f1):.4f}")
                
            if mean_f1 > best_f1:
                best_f1 = mean_f1
                best_params = params
                
        print(f"[OK] LightGBM Optimization Complete. Best Cross-Validation F1-Score: {best_f1:.4f}")
        return best_params

def main():
    print("=== Starting NairaShield Bayesian/Randomized Hyperparameter Tuning Pipeline ===")
    X_train, y_train, X_test, y_test = load_and_split_data()
    
    xgb_best = tune_xgboost(X_train, y_train)
    lgb_best = tune_lightgbm(X_train, y_train)
    
    best_params = {
        "xgboost": xgb_best,
        "lightgbm": lgb_best
    }
    
    config_dir = "config"
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "best_hyperparameters.json")
    
    with open(config_path, "w") as f:
        json.dump(best_params, f, indent=4)
        
    print(f"\n[OK] Hyperparameter optimization completed successfully.")
    print(f"Best parameters saved to: {config_path}")

if __name__ == "__main__":
    main()
