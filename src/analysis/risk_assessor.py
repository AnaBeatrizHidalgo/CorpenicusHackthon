# src/analysis/risk_assessor.py
import logging
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

def calculate_risk_score(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates a normalized risk score, handling edge cases where
    feature values are constant or NaN.
    """
    logging.info("Calculating risk score for each census tract...")
    
    risk_factors = {
        'ndvi_mean': 0.20, 't2m_mean': 0.40, 'tp_mean': 0.30,
        'vv_mean': 0.05, 'vh_mean': 0.05
    }
    
    df = features_df.copy()
    if 'CD_SETOR' in df.columns:
        df.set_index('CD_SETOR', inplace=True)
    
    # --- Data Cleaning and Normalization ---
    for col in risk_factors:
        if col not in df.columns:
            logging.warning(f"Risk factor column '{col}' not found. Skipping.")
            df[f'{col}_norm'] = 0 # Assign a neutral value if column is missing
            continue
        
        # Fill NaN values with the column's mean
        if df[col].isnull().any():
            mean_val = df[col].mean()
            if pd.isna(mean_val):  # If mean is also NaN (all values are NaN)
                mean_val = 0
            df[col] = df[col].fillna(mean_val)

        # If after filling, the column is STILL all NaN (because it was empty), fill with 0
        if df[col].isnull().all():
            df[f'{col}_norm'] = 0
            logging.warning(f"Column '{col}' is entirely empty. Treating as 0 risk.")
            continue
        
        # Check if all values are the same (no variance)
        if df[col].nunique() <= 1:
            df[f'{col}_norm'] = 0.5  # Neutral value for no variance
            logging.warning(f"Column '{col}' has no variance. Using neutral value.")
            continue
            
        # Normalize the column from 0 to 1
        try:
            scaler = MinMaxScaler()
            df[f'{col}_norm'] = scaler.fit_transform(df[[col]]).flatten()
        except Exception as e:
            logging.error(f"Error normalizing column '{col}': {str(e)}")
            df[f'{col}_norm'] = 0

    # --- Risk Score Calculation ---
    df['risk_score'] = 0
    for col, weight in risk_factors.items():
        if f'{col}_norm' in df.columns:
            if col == 'ndvi_mean':
                # Inverted U-shaped curve for NDVI (medium values = higher risk)
                df['risk_score'] += (-4 * df[f'{col}_norm']**2 + 4 * df[f'{col}_norm']) * weight
            else:
                df['risk_score'] += df[f'{col}_norm'] * weight
    
    # Ensure risk_score is between 0 and 1
    df['risk_score'] = df['risk_score'].clip(0, 1)
    
    # Fill any remaining NaN values in risk_score
    df['risk_score'] = df['risk_score'].fillna(0.5)  # Neutral risk for undefined cases
    
    # --- ROBUST RISK LEVEL CLASSIFICATION ---
    # Check for valid scores before attempting to create bins
    valid_scores = df['risk_score'].dropna()
    
    if valid_scores.empty:
        # Case 1: All scores are NaN
        df['risk_level'] = 'Indeterminado'
        logging.warning("All risk scores are NaN. Risk level is Indeterminate.")
    elif valid_scores.nunique() < 3:
        # Case 2: Not enough unique score values to create 3 bins.
        # Assign a level based on the average score.
        mean_score = valid_scores.mean()
        if mean_score > 0.6:
            level = 'Alto'
        elif mean_score > 0.3:
            level = 'Médio'
        else:
            level = 'Baixo'
        df['risk_level'] = level
        logging.warning(f"Not enough unique risk scores to create multiple categories. Assigning single risk level: {level}")
    else:
        try:
            # Case 3: Enough unique scores to create quantile-based bins.
            # Using qcut is safer as it handles duplicate bin edges.
            df['risk_level'] = pd.qcut(
                df['risk_score'], 
                q=[0, 0.33, 0.66, 1.0], 
                labels=['Baixo', 'Médio', 'Alto'],
                duplicates='drop'
            )
            # Convert categorical to string to avoid GeoJSON issues later
            df['risk_level'] = df['risk_level'].astype(str)
        except Exception as e:
            logging.error(f"Error in risk level classification: {str(e)}")
            # Fallback to simple thresholding
            df['risk_level'] = pd.cut(
                df['risk_score'],
                bins=[0, 0.33, 0.66, 1.0],
                labels=['Baixo', 'Médio', 'Alto'],
                include_lowest=True,
                right=True
            ).astype(str)

    logging.info("Risk score calculation complete.")
    
    # Ensure all columns are in appropriate formats
    result_df = df.reset_index()
    
    # Convert any remaining categorical columns to string
    for col in result_df.columns:
        if hasattr(result_df[col], 'cat'):
            result_df[col] = result_df[col].astype(str)
    
    return result_df