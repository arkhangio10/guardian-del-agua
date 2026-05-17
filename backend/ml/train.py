"""Train XGBoost impact prediction model on Loreto historical spill data."""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from xgboost import XGBRegressor

ML_DIR = Path(__file__).parent
DATA_PATH = ML_DIR / "loreto_historical.csv"
MODEL_PATH = ML_DIR / "impact_model.pkl"

CONTAMINATION_ENCODING = {"hydrocarbon": 0, "turbidity": 1, "algal_bloom": 2}
SEASON_ENCODING = {"dry": 0, "wet": 1}

FEATURES = [
    "contamination_type_enc",
    "volume_barrels",
    "river_flow_m3s",
    "distance_km",
    "pop_density_per_km2",
    "biodiversity_index",
    "season_enc",
]

TARGETS = ["people_affected_7d", "people_affected_30d", "fish_dieoff_pct", "recovery_days"]


def load_and_prepare(path: Path) -> tuple:
    df = pd.read_csv(path)
    df["contamination_type_enc"] = df["contamination_type"].map(CONTAMINATION_ENCODING).fillna(0)
    df["season_enc"] = df["season"].map(SEASON_ENCODING).fillna(1)
    X = df[FEATURES].values
    y = df[TARGETS].values
    return X, y


def train(X, y):
    model = MultiOutputRegressor(
        XGBRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=0,
        )
    )
    model.fit(X, y)
    return model


def evaluate(model, X_test, y_test):
    preds = model.predict(X_test)
    for i, target in enumerate(TARGETS):
        mae = mean_absolute_error(y_test[:, i], preds[:, i])
        print(f"  {target}: MAE = {mae:.1f}")


if __name__ == "__main__":
    print(f"Loading data from {DATA_PATH}...")
    X, y = load_and_prepare(DATA_PATH)
    print(f"  {len(X)} samples, {len(FEATURES)} features, {len(TARGETS)} targets")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("Training XGBoost model...")
    model = train(X_train, y_train)

    print("Evaluation (test set):")
    evaluate(model, X_test, y_test)

    joblib.dump(model, str(MODEL_PATH))
    print(f"\nModel saved to {MODEL_PATH}")
