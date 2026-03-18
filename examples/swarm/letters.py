from learning_swarm import letter_to_points
import matplotlib.pyplot as plt


for ch, H, N in [("A", 0.30, 6), ("A", 0.30, 10), ("E", 0.30, 6), ("R", 0.30, 9)]:
    strokes = letter_to_points(ch, target_height=H, total_points=N)
    total = sum(len(s) for s in strokes)
    print(f"{ch}: requested={N}, got={total}, per-stroke={[len(s) for s in strokes]}")

    plt.figure(figsize=(4,4))
    for s in strokes:
        if len(s) == 1:
            plt.scatter(s[:,0], s[:,1], s=40)
        else:
            plt.plot(s[:,0], s[:,1], '-o', ms=3)
    plt.gca().set_aspect('equal', adjustable='box')
    plt.title(f"{ch}: {N} unique points")
    plt.grid(True, alpha=0.3)
    plt.show()
