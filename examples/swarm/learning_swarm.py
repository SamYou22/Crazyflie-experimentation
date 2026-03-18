# points_A.py
import numpy as np
from typing import List, Tuple


def _sample_leg_excluding_vertices(p0: np.ndarray, p1: np.ndarray,
                                   t_cross: float, n: int) -> np.ndarray:
    """
    Sample exactly n points along the straight segment p0->p1,
    excluding the endpoints t=0,1 and the crossbar location t=t_cross.
    Strategy:
      - Split [0,1] into [0, t_cross) and (t_cross, 1]
      - Allocate points proportionally to each sub-interval length
      - In each sub-interval, place points at bin midpoints to avoid vertices
    """
    if n <= 0:
        return np.zeros((0, 2))

    # Sub-interval lengths
    L1 = max(t_cross, 0.0)
    L2 = max(1.0 - t_cross, 0.0)
    total = L1 + L2
    if total <= 0:
        # Degenerate: the leg has zero length; just return nothing
        return np.zeros((0, 2))

    # Proportional split (then fix rounding)
    n1 = int(np.floor(n * (L1 / total))) if total > 0 else 0
    n2 = n - n1

    # To avoid starving one side due to rounding, adjust to ensure sum == n
    # (already ensured, but if L1==0, n1=0; likewise for L2==0)
    # Create samples:
    ts_list = []

    # Left sub-interval: [0, t_cross)
    if n1 > 0 and L1 > 0:
        dt = L1 / n1
        # midpoints of sub-bins: (k+0.5)*dt, k=0..n1-1
        ts = (np.arange(n1) + 0.5) * dt
        ts_list.append(ts)

    # Right sub-interval: (t_cross, 1]
    if n2 > 0 and L2 > 0:
        dt = L2 / n2
        # midpoints of (t_cross,1] bins: t_cross + (k+0.5)*dt
        ts = t_cross + (np.arange(n2) + 0.5) * dt
        ts_list.append(ts)

    if not ts_list:
        return np.zeros((0, 2))

    t_all = np.concatenate(ts_list)
    # Map to coordinates
    return (1.0 - t_all)[:, None] * p0 + t_all[:, None] * p1


def points_A(total_points: int,
             height: float = 0.30,
             width: float = None,
             crossbar_ratio: float = 0.5) -> np.ndarray:
    """
    Generate EXACTLY `total_points` unique (x,y) points for the letter 'A'
    under these rules:
      • 'A' has two slanted legs and one horizontal crossbar.
      • We place exactly 3 points on the crossbar: left-vertex, midpoint, right-vertex.
      • The remaining points are placed equidistantly along the two slanted legs,
        EXCLUDING the endpoints and EXCLUDING the crossbar intersection vertices (to avoid duplicates).

    Parameters
    ----------
    total_points : int
        Exact number of points to return (>= 3 recommended).
    height : float
        Final letter height (units: meters or your choice).
    width : float or None
        Final letter width; by default 0.8 * height for a decent proportion.
    crossbar_ratio : float
        y-position of the crossbar as a fraction of height (0..1). Typical ~0.5.

    Returns
    -------
    np.ndarray, shape (total_points, 2)
        The (x,y) coordinates of the points. Order is:
            [left-leg points (bottom->top, excluding vertices),
             crossbar-left vertex, crossbar-mid, crossbar-right vertex,
             right-leg points (bottom->top, excluding vertices)]
    """
    if total_points <= 0:
        return np.zeros((0, 2))

    if width is None:
        width = 0.8 * height  # simple proportion; tweak if you like

    # Geometry of 'A'
    # Bottom-left, apex, bottom-right
    BL = np.array([0.0, 0.0])
    AP = np.array([width / 2.0, height])
    BR = np.array([width, 0.0])

    # Crossbar y
    y_bar = np.clip(crossbar_ratio, 0.0, 1.0) * height

    # Parameter t along legs is linear in Y because legs are straight:
    # For left leg: y = t * height  =>  t_cross = y_bar / height
    # For right leg: same
    if height == 0:
        t_cross = 0.5
    else:
        t_cross = y_bar / height

    # Crossbar vertices on legs (by interpolation at t_cross)
    C_L = (1.0 - t_cross) * BL + t_cross * AP
    C_R = (1.0 - t_cross) * BR + t_cross * AP
    C_M = 0.5 * (C_L + C_R)

    # Reserve the 3 crossbar points
    reserved = 3
    if total_points < reserved:
        # If user asks fewer than 3, return a subset in a stable way:
        # prioritize the two crossbar vertices, then the midpoint if one more fits
        subset = [C_L, C_R, C_M][:total_points]
        return np.vstack(subset) if subset else np.zeros((0, 2))

    remain = total_points - reserved

    # Split remaining points across the two legs, as evenly as possible
    n_left = remain // 2
    n_right = remain - n_left

    # Sample legs, excluding endpoints and crossbar intersection
    left_pts = _sample_leg_excluding_vertices(BL, AP, t_cross, n_left)
    right_pts = _sample_leg_excluding_vertices(BR, AP, t_cross, n_right)

    # Concatenate in a stable, predictable order
    out_parts = [
        left_pts,
        C_L.reshape(1, 2),
        C_M.reshape(1, 2),
        C_R.reshape(1, 2),
        right_pts
    ]
    out = np.vstack([p for p in out_parts if len(p) > 0])

    # Safety: Make sure we return EXACTLY total_points and points are unique
    if len(out) != total_points:
        # Adjust if due to numerical edge cases
        # If off by one, duplicate the last point with a tiny inward nudge
        diff = total_points - len(out)
        if diff > 0:
            # Add tiny nudges along right leg direction (deterministic)
            if len(right_pts) > 0:
                dir_vec = (AP - BR)
            elif len(left_pts) > 0:
                dir_vec = (AP - BL)
            else:
                dir_vec = (C_R - C_L)
            dir_norm = dir_vec / (np.linalg.norm(dir_vec) + 1e-12)
            for k in range(diff):
                out = np.vstack([out, out[-1] - 1e-9 * (k + 1) * dir_norm])
        elif diff < 0:
            out = out[:total_points]

    # Global uniqueness (within a tiny tolerance)
    # If any duplicates remain (shouldn't), nudge slightly along x to make unique.
    seen = set()
    unique_out = []
    for i, p in enumerate(out):
        key = (round(p[0], 12), round(p[1], 12))
        if key in seen:
            p = p + np.array([1e-9 * (i + 1), 0.0])  # deterministic tiny offset in x
            key = (round(p[0], 12), round(p[1], 12))
        seen.add(key)
        unique_out.append(p)
    return np.vstack(unique_out)


# --------- quick demo ---------
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    for N in (12, 14, 16):
        P = points_A(N, height=0.30, width=None, crossbar_ratio=0.5)
        print(f"A: N={N}, got={len(P)} points")
        plt.figure(figsize=(4, 5))
        plt.plot(P[:, 0], P[:, 1], "o-", ms=4)
        plt.gca().set_aspect("equal", adjustable="box")
        plt.title(f"A with N={N}")
        plt.grid(True, alpha=0.3)
        plt.show()