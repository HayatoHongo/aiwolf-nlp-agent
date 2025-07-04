from collections import Counter

with open("results.txt", encoding="utf-8") as f:
    results = [line.strip() for line in f if line.strip()]

counter = Counter(results)
total = sum(counter.values())
for k, v in counter.items():
    print(f"{k}胜利: {v}次 ({v/total*100:.1f}%)")
