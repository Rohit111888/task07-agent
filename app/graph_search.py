from app.build_graph import build_car_graph


KNOWN_BRANDS = [
    "ferrari", "porsche", "mercedes-benz", "mercedes", "bmw",
    "audi", "lamborghini", "rolls-royce", "land rover",
    "bentley", "mclaren", "aston martin"
]


def graph_ranked_search(query, top_k=5):
    """
    Search the automotive graph using keyword matching and rank
    results with PageRank-based graph centrality.
    """
    G, df = build_car_graph()

    query_lower = query.lower()
    query_words = query_lower.split()

    mentioned_brand = None
    for brand in KNOWN_BRANDS:
        if brand in query_lower:
            mentioned_brand = brand
            break

    results = []

    for node, data in G.nodes(data=True):
        brand = str(data["brand"]).lower()
        model = str(data["model"]).lower()
        generation = str(data["generation"]).lower()
        price_bracket = str(data["price_bracket"]).lower()

        if mentioned_brand:
            if mentioned_brand == "mercedes":
                if "mercedes" not in brand:
                    continue
            elif mentioned_brand not in brand:
                continue

        text = f"{brand} {model} {generation} {price_bracket}"

        keyword_score = 0
        for word in query_words:
            if word in text:
                keyword_score += 1

        # Give useful boosts
        if mentioned_brand and mentioned_brand in brand:
            keyword_score += 5

        if "performance" in query_lower and data["horsepower"] is not None:
            try:
                keyword_score += float(data["horsepower"]) / 1000
            except:
                pass

        final_score = (
            0.75 * keyword_score
            + 0.25 * data["pagerank"]
        )

        results.append({
            "brand": data["brand"],
            "model": data["model"],
            "generation": data["generation"],
            "price_bracket": data["price_bracket"],
            "horsepower": data["horsepower"],
            "pagerank": data["pagerank"],
            "degree_centrality": data["degree_centrality"],
            "betweenness_centrality": data["betweenness_centrality"],
            "final_score": final_score
        })

    results = sorted(results, key=lambda x: x["final_score"], reverse=True)

    return results[:top_k]


if __name__ == "__main__":
    query = input("Enter search query: ")
    results = graph_ranked_search(query)

    print("\nGraph-Ranked Search Results")
    print("-" * 40)

    for i, car in enumerate(results, start=1):
        print(f"{i}. {car['brand']} {car['model']} - {car['generation']}")
        print(f"   Price Segment: {car['price_bracket']}")
        print(f"   HP: {car['horsepower']}")
        print(f"   PageRank: {car['pagerank']:.6f}")
        print(f"   Final Score: {car['final_score']:.6f}")
        print()