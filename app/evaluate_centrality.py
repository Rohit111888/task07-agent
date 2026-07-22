"""Evaluate centrality measures for the automotive similarity graph."""

from app.build_graph import build_car_graph
import pandas as pd


def evaluate_centrality():
    """
    Compute PageRank, degree centrality, and betweenness centrality
    for all vehicles and export the comparison results.
    """
    G, df = build_car_graph()

    rows = []

    for node, data in G.nodes(data=True):
        rows.append(
    {
        "brand": data["brand"],
        "model": data["model"],
        "generation": data["generation"],
        "pagerank": data["pagerank"],
        "degree_centrality": data["degree_centrality"],
        "betweenness_centrality": data["betweenness_centrality"],
    }
)
        

    results = pd.DataFrame(rows)

    print("\nTOP 10 BY PAGERANK")
    print("-" * 60)
    print(
        results.sort_values(
            "pagerank",
            ascending=False
        ).head(10)
    )

    print("\nTOP 10 BY DEGREE CENTRALITY")
    print("-" * 60)
    print(
        results.sort_values(
            "degree_centrality",
            ascending=False
        ).head(10)
    )

    print("\nTOP 10 BY BETWEENNESS CENTRALITY")
    print("-" * 60)
    print(
        results.sort_values(
            "betweenness_centrality",
            ascending=False
        ).head(10)
    )

    comparison = (
        results.sort_values("pagerank", ascending=False)
        .head(20)
        .copy()
    )

    comparison.to_csv(
        "centrality_comparison.csv",
        index=False
    )

    print("\nSaved: centrality_comparison.csv")


if __name__ == "__main__":
    evaluate_centrality()