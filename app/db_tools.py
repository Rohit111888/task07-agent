import pandas as pd


from pathlib import Path

CSV_PATH = Path(__file__).parent / "final_csv.csv"

def load_data():
    return pd.read_csv(CSV_PATH)


def query_cars(
    brand=None,
    min_hp=None,
    max_hp=None,
    fuel_type=None,
    top_n=10
):
    df = load_data()

    if brand:
        df = df[
            df["brand"]
            .astype(str)
            .str.contains(brand, case=False, na=False)
        ]

    if min_hp is not None:
        df = df[df["horsepower"] >= min_hp]

    if max_hp is not None:
        df = df[df["horsepower"] <= max_hp]

    if fuel_type:
        df = df[
            df["fuel_type"]
            .astype(str)
            .str.contains(fuel_type, case=False, na=False)
        ]

    columns = [
        "brand",
        "model",
        "generation",
        "horsepower",
        "top_speed",
        "price_usd"
    ]

    existing_cols = [c for c in columns if c in df.columns]

    return df[existing_cols].head(top_n)


if __name__ == "__main__":
    results = query_cars(
        brand="Ferrari",
        min_hp=700
    )

    print(results)