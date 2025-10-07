# @title Advanced Bowling Performance Model (Opponent-Aware, Improved)

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error
import joblib
import warnings
warnings.filterwarnings('ignore')

# 1 SAFE UTILITIES

def safe_convert_season(x):
    try:
        return int(str(x).split('/')[0])
    except Exception:
        return 2023

# 2 ICC RATINGS TABLES (snapshot-style, used as prior)

odi_ratings = {
    "India": 122, "New Zealand": 111, "Australia": 109, "Sri Lanka": 103,
    "Pakistan": 101, "South Africa": 98, "Afghanistan": 95, "England": 86,
    "West Indies": 79, "Bangladesh": 76, "Zimbabwe": 54, "Ireland": 52,
    "Scotland": 46, "United States": 44, "Netherlands": 40, "Oman": 35,
    "Nepal": 27, "Namibia": 21, "Canada": 16, "United Arab Emirates": 11
}

t20_ratings = {
    "India": 272, "Australia": 267, "England": 258, "New Zealand": 251,
    "South Africa": 240, "West Indies": 237, "Pakistan": 234, "Sri Lanka": 230,
    "Bangladesh": 223, "Afghanistan": 220, "Ireland": 201, "Zimbabwe": 199,
    "Netherlands": 182, "Scotland": 182, "Namibia": 181,
    "United Arab Emirates": 178, "Nepal": 176, "United States": 175,
    "Canada": 154, "Oman": 150, "Uganda": 142, "PNG": 136,
    "Papua New Guinea": 136
}

# 3 FEATURE ENGINEERING - FIXED VERSION

def create_bowling_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(['player_id', 'date'])

    # --- Base performance metrics (no leakage) ---
    df['dot_ball_percentage'] = df['dot_balls'] / (df['balls_bowled'] + 0.1)
    df['economy_pressure'] = (df['economy_rate'] > 7.0).astype(int)

    # --- Lagged historical performance (shifted) ---
    df['wickets_avg_10_lagged'] = df.groupby('player_id')['wickets_taken'].transform(
        lambda x: x.shift(1).rolling(10, min_periods=1).mean()
    )
    df['economy_avg_10_lagged'] = df.groupby('player_id')['economy_rate'].transform(
        lambda x: x.shift(1).rolling(10, min_periods=1).mean()
    )
    df['recent_form_lagged'] = df.groupby('player_id')['wickets_taken'].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
        - x.shift(1).rolling(10, min_periods=1).mean()
    )

    # --- FIXED: Historical averages vs opponent (last 10 matches, properly lagged) ---
    def rolling_opponent_avg(group):
        return group.shift(1).rolling(10, min_periods=1).mean()
    
    df['vs_opponent_avg_10_lagged'] = df.groupby(['player_id', 'opponent_team'])['wickets_taken'].transform(
        rolling_opponent_avg
    )

    # --- Career expectation (lagged rolling mean instead of expanding) ---
    df['expected_wickets'] = df.groupby('player_id')['wickets_taken'].transform(
        lambda x: x.shift(1).rolling(15, min_periods=1).mean()  # Rolling 15 instead of expanding
    )

    # --- Form metrics ---
    df['avg_wkts_last_5'] = df.groupby('player_id')['wickets_taken'].transform(
        lambda x: x.shift(1).rolling(5, min_periods=1).mean()
    )
    df['form_score'] = df['recent_form_lagged']

    # --- Venue context: average wickets at venue ---
    venue_avg = (
        df.groupby('venue')['wickets_taken']
          .mean()
          .reset_index()
          .rename(columns={'wickets_taken': 'venue_avg_wickets'})
    )
    df = df.merge(venue_avg, on='venue', how='left')

    # --- Season & match importance ---
    df['season_numeric'] = df['season'].apply(safe_convert_season)
    df['match_importance'] = df['match_type'].map({'T20': 1, 'ODI': 2}).fillna(1)

    #  Opponent Weakness & ICC Strength (Continuous, No Tiering)

    # (A) Empirical: how many wickets teams typically lose
    opp_weakness = df.groupby('opponent_team')['wickets_taken'].mean()
    df['opponent_weakness_data'] = df['opponent_team'].map(opp_weakness)
    df['opponent_weakness_data'] = df['opponent_weakness_data'].fillna(opp_weakness.mean())

    # (B) ICC-based prior strength
    def map_team_strength(row):
        team = str(row['opponent_team'])
        mtype = str(row['match_type']).upper()
        if mtype == 'ODI':
            return odi_ratings.get(team, np.mean(list(odi_ratings.values())))
        else:
            return t20_ratings.get(team, np.mean(list(t20_ratings.values())))
    df['opponent_strength_rating'] = df.apply(map_team_strength, axis=1)

    # (C) Normalize ICC strength within format
    df['icc_strength_scaled'] = df.groupby('match_type')['opponent_strength_rating'] \
        .transform(lambda x: (x - x.min()) / (x.max() - x.min() + 1e-6))

    # (D) Normalize empirical weakness
    opp_weak_norm = (df['opponent_weakness_data'] - df['opponent_weakness_data'].min()) / (
        (df['opponent_weakness_data'].max() - df['opponent_weakness_data'].min()) + 1e-6
    )

    # (E) Continuous opponent strength signal:
    df['opponent_strength_continuous'] = (
        0.7 * (1 - df['icc_strength_scaled']) +
        0.3 * opp_weak_norm
    )

    # Alias: this is our main difficulty signal
    df['opponent_difficulty'] = df['opponent_strength_continuous']

    # (F) Global opponent stats across all bowlers
    team_stats = (
        df.groupby('opponent_team')['wickets_taken']
          .agg(['mean', 'std'])
          .rename(columns={'mean': 'team_wkts_avg', 'std': 'team_wkts_std'})
          .reset_index()
    )
    df = df.merge(team_stats, on='opponent_team', how='left')
    df['team_wkts_avg'] = df['team_wkts_avg'].fillna(df['team_wkts_avg'].mean())
    df['team_wkts_std'] = df['team_wkts_std'].fillna(0.0)

    #  Interaction Features

    df['form_vs_strength'] = df['form_score'] * df['opponent_difficulty']
    df['venue_strength_combo'] = df['venue_avg_wickets'] * df['opponent_difficulty']

    return df

# 4 DATA PREPARATION

print(" Creating enhanced bowling features...")
df_enhanced = create_bowling_features(df)
df_enhanced = df_enhanced.replace([np.inf, -np.inf], np.nan).fillna(0)

# 5 FEATURE SET - UPDATED

enhanced_features = [
    # player vs opponent / form - UPDATED
    'vs_opponent_avg_10_lagged',  # REPLACED: 'vs_opponent_avg_historical' / because it was not giving proper result
    'avg_wkts_last_5',
    'wickets_avg_10_lagged',
    'recent_form_lagged',
    'form_score',
    'expected_wickets',
    'economy_avg_10_lagged',

    # venue
    'venue_avg_wickets',

    # opponent difficulty signals
    'opponent_weakness_data',
    'opponent_strength_rating',
    'icc_strength_scaled',
    'opponent_strength_continuous',
    'opponent_difficulty',
    'team_wkts_avg',
    'team_wkts_std',

    # interactions
    'form_vs_strength',
    'venue_strength_combo',

    # global context
    'season_numeric',
    'match_importance',
]

# One-hot encode categoricals
df_enhanced = pd.get_dummies(
    df_enhanced,
    columns=['venue', 'opponent_team', 'match_type'],
    drop_first=True
)

# Sanitize column names
df_enhanced.columns = (
    df_enhanced.columns
      .str.replace('[,()"\'\\/]', '', regex=True)
      .str.replace(' ', '_')
      .str.replace('__', '_')
)

print(f" Enhanced features: {len(df_enhanced.columns)} columns")

target = 'wickets_taken'

X = df_enhanced[
    [c for c in df_enhanced.columns
     if c in enhanced_features or c.startswith(('venue_', 'opponent_team_', 'match_type_'))]
]
y = df_enhanced[target]
groups = df_enhanced['player_id']

print(f" Dataset shape: {X.shape}")

# 6 LIGHTGBM CONFIGURATION - OPTIMIZED

params_optimized = {
    'objective': 'regression_l1',   # Predict continuous wickets using MAE loss
    'metric': 'mae',                # Evaluate using MAE
    'learning_rate': 0.006,         # Small learning rate for stable training wickets taken:0 heavily influced
    'num_leaves': 95,               # Model complexity (more leaves = more power)
    'min_data_in_leaf': 30,         # Minimum samples per leaf (reduces overfitting)
    'max_depth': 10,                # Limit tree depth
    'subsample': 0.75,              # Use 75% of rows per tree
    'colsample_bytree': 0.75,       # Use 75% of features per tree
    'reg_alpha': 0.15,              # L1 regularization: Forces the model to ignore unimportant features
    'reg_lambda': 0.25,             # L2 regularization: Reduces the impact of extreme values
    'min_split_gain': 0.008,        # Minimum gain required for a split
    'feature_fraction': 0.8,        # Use 80% of features per split
    'bagging_fraction': 0.8,        # Bagging: 80% of data per iteration
    'bagging_freq': 1,              # Apply bagging every iteration
    'verbose': 1                    # Show training logs
}


# 7 GROUP K-FOLD TRAINING WITH DIAGNOSTICS

gkf = GroupKFold(n_splits=5)
mae_scores, models, best_iters = [], [], []

print(f"\n Starting LightGBM training ({X.shape[1]} features)...")

for fold, (tr_idx, va_idx) in enumerate(gkf.split(X, y, groups)):
    print(f"\n===== Fold {fold + 1} =====")
    X_tr, X_va = X.iloc[tr_idx], X.iloc[va_idx]
    y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]

    d_tr = lgb.Dataset(X_tr, y_tr)
    d_va = lgb.Dataset(X_va, y_va, reference=d_tr)

    model = lgb.train(
        params_optimized,
        d_tr,
        num_boost_round=2000,
        valid_sets=[d_tr, d_va],
        valid_names=['train', 'valid'],
        callbacks=[
            lgb.early_stopping(stopping_rounds=150, verbose=False),
            lgb.log_evaluation(period=100),
        ],
    )

    # Get predictions for both train and validation
    train_preds = model.predict(X_tr, num_iteration=model.best_iteration)
    val_preds = model.predict(X_va, num_iteration=model.best_iteration)
    
    train_mae = mean_absolute_error(y_tr, train_preds)
    val_mae = mean_absolute_error(y_va, val_preds)
    
    mae_scores.append(val_mae)
    best_iters.append(model.best_iteration)
    models.append(model)

    print(f" Fold {fold + 1} MAE: {val_mae:.3f} (best iter: {model.best_iteration})")
    print(f" Train MAE: {train_mae:.3f} | Overfit gap: {train_mae - val_mae:.3f}")

print(f"\n Average MAE: {np.mean(mae_scores):.3f}  {np.std(mae_scores):.3f}")
print(f" Best iterations: {best_iters}")

# 8 FINAL MODEL TRAINING

best_rounds = int(np.mean(best_iters))
print(f"\n Training final model on full dataset for {best_rounds} rounds...")

final_model = lgb.train(
    params_optimized,
    lgb.Dataset(X, y),
    num_boost_round=best_rounds,
    callbacks=[lgb.log_evaluation(period=100)],
)

final_model.save_model("/content/final_bowling_lgbm.txt")
joblib.dump(final_model, "/content/final_bowling_lgbm.pkl")

print("\n Final model trained and saved successfully!")

# 9 FEATURE IMPORTANCE

print("\n Top 20 Feature Importance:")
imp = final_model.feature_importance(importance_type='gain')
names = final_model.feature_name()
fi_df = (
    pd.DataFrame({'feature': names, 'importance': imp})
      .sort_values('importance', ascending=False)
      .head(20)
)
print(fi_df.to_string(index=False))