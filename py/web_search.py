from duckduckgo_search import DDGS

results = DDGS().text("人工智能", max_results=5)
print(results)