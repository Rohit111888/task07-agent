"""Build the automotive similarity graph used by graph-ranked search."""

import pandas as pd
import networkx as nx
from pathlib import Path

CSV_PATH = Path(__file__).parent / "final_csv.csv"

def build_car_graph(csv_path=CSV_PATH):
    """
    Build the automotive similarity graph from the cleaned dataset and
    compute PageRank, degree centrality, and betweenness centrality.
    """
    df = pd.read_csv(csv_path)

    possible_price_cols = ["price_usd", "price_dollars", "price_eur"]

    price_col = None
    for col in possible_price_cols:
        if col in df.columns:
            price_col = col
            break

    if price_col is None:
        raise ValueError(f"No price column found. Available columns: {list(df.columns)}")

    print(f"Using price column: {price_col}")

    df = df.dropna(subset=["brand", "model", price_col]).copy()

    df["brand"] = df["brand"].astype(str).str.strip()
    df["model"] = df["model"].astype(str).str.strip()
    df[price_col] = pd.to_numeric(df[price_col], errors="coerce")

    if "horsepower" in df.columns:
        df["horsepower"] = pd.to_numeric(df["horsepower"], errors="coerce")

    df = df.dropna(subset=[price_col]).copy()
    df = df.drop_duplicates(
    subset=["brand", "model", "generation"]
).copy()
    # Creates balanced price groups instead of fixed dollar brackets
    df["price_bracket"] = pd.qcut(
        df[price_col],
        q=5,
        labels=["relatively_low", "lower_segment", "medium_range", "high_segment", "relatively_high"],
        duplicates="drop",
    )

    print(f"Loaded {len(df)} vehicles")

    G = nx.Graph()

    for idx, row in df.iterrows():
        G.add_node(
            idx,
            brand=row["brand"],
            model=row["model"],
            generation=row.get("generation", ""),
            price=row[price_col],
            price_bracket=str(row["price_bracket"]),
            horsepower=row.get("horsepower", None),
        )

    indices = list(df.index)

    for idx_i in range(len(indices)):
        for idx_j in range(idx_i + 1, len(indices)):
            i = indices[idx_i]
            j = indices[idx_j]

            weight = 0

            same_brand = df.loc[i, "brand"] == df.loc[j, "brand"]
            same_price = df.loc[i, "price_bracket"] == df.loc[j, "price_bracket"]

            hp_i = df.loc[i, "horsepower"] if "horsepower" in df.columns else None
            hp_j = df.loc[j, "horsepower"] if "horsepower" in df.columns else None

            similar_hp = (
                pd.notna(hp_i)
                and pd.notna(hp_j)
                and abs(float(hp_i) - float(hp_j)) <= 50
            )

            # Rule 1: same brand connection
            if same_brand:
                weight += 3

            # Rule 2: same price segment AND similar performance
            if same_price and similar_hp:
                weight += 2

            if weight > 0:
                G.add_edge(i, j, weight=weight)

    pagerank = nx.pagerank(G, weight="weight")
    degree = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G, weight="weight")

    nx.set_node_attributes(G, pagerank, "pagerank")
    nx.set_node_attributes(G, degree, "degree_centrality")
    nx.set_node_attributes(G, betweenness, "betweenness_centrality")

    return G, df


if __name__ == "__main__":
    G, df = build_car_graph()

    print("\nGraph created successfully")
    print("-" * 40)
    print("Nodes:", G.number_of_nodes())
    print("Edges:", G.number_of_edges())
    print(f"Density: {nx.density(G):.4f}")

    avg_degree = sum(dict(G.degree()).values()) / G.number_of_nodes()
    print(f"Average Degree: {avg_degree:.2f}")

    print("\nPrice bracket counts:")
    print(df["price_bracket"].value_counts())

    top_nodes = sorted(
        G.nodes(data=True),
        key=lambda x: x[1]["pagerank"],
        reverse=True,
    )[:10]

    print("\nTop 10 vehicles by PageRank:")
    for node, data in top_nodes:
        print(
            data["brand"],
            data["model"],
            data["price_bracket"],
            "HP:",
            data["horsepower"],
            "PageRank:",
            round(data["pagerank"], 6),
        )