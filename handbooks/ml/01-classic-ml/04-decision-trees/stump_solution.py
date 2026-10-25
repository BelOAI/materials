import sys

values = list(map(int, sys.stdin.buffer.read().split()))
n = values[0]
pairs = sorted(zip(values[1::2], values[2::2]))
total = sum(y for _, y in pairs)

if pairs[0][0] == pairs[-1][0]:
    print(f"0.0000000000 {total / n:.10f} {pairs[0][0]:.10f}")
else:
    left_sum = 0
    best_score = -1.0
    best = None
    for i in range(n - 1):
        left_sum += pairs[i][1]
        if pairs[i][0] == pairs[i + 1][0]:
            continue
        left_count = i + 1
        right_count = n - left_count
        right_sum = total - left_sum
        score = left_sum**2 / left_count + right_sum**2 / right_count
        if score > best_score:
            best_score = score
            best = (
                left_sum / left_count,
                right_sum / right_count,
                (pairs[i][0] + pairs[i + 1][0]) / 2,
            )
    a, b, c = best
    print(f"{a:.10f} {b:.10f} {c:.10f}")
