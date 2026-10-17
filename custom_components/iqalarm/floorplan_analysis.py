"""Local, bounded room-area proposals from structural lines in a floorplan.

Proposals are geometry only. They never create rooms, change security rules or
claim to recognize room names. Open areas can be separated with the manual tool.
"""

from collections import defaultdict, deque
from math import hypot
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

MAX_SIDE = 640


def _area(points: list[tuple[float, float]]) -> float:
    return (
        abs(
            sum(
                a[0] * b[1] - a[1] * b[0]
                for a, b in zip(points, points[1:] + points[:1], strict=True)
            )
        )
        / 2
    )


def _simplify_line(points, tolerance):
    if len(points) <= 2:
        return points
    first, last = points[0], points[-1]
    dx, dy = last[0] - first[0], last[1] - first[1]
    length = hypot(dx, dy)
    if length == 0:
        return [first, last]
    distances = [
        abs(dy * (p[0] - first[0]) - dx * (p[1] - first[1])) / length for p in points[1:-1]
    ]
    distance = max(distances, default=0)
    if distance <= tolerance:
        return [first, last]
    split = distances.index(distance) + 1
    return _simplify_line(points[: split + 1], tolerance)[:-1] + _simplify_line(
        points[split:], tolerance
    )


def _polygon(cells: list[int], width: int) -> list[tuple[int, int]]:
    occupied = set(cells)
    edges = defaultdict(list)
    for index in cells:
        x, y = index % width, index // width
        if index - width not in occupied:
            edges[(x, y)].append((x + 1, y))
        if x == width - 1 or index + 1 not in occupied:
            edges[(x + 1, y)].append((x + 1, y + 1))
        if index + width not in occupied:
            edges[(x + 1, y + 1)].append((x, y + 1))
        if x == 0 or index - 1 not in occupied:
            edges[(x, y + 1)].append((x, y))
    loops = []
    while edges:
        start = next(iter(edges))
        point = start
        loop = []
        while point in edges:
            loop.append(point)
            following = edges[point].pop()
            if not edges[point]:
                del edges[point]
            point = following
            if point == start:
                break
        if point == start and len(loop) >= 4:
            # Remove collinear pixel steps before polygon simplification.
            corners = [
                p
                for i, p in enumerate(loop)
                if (p[0] - loop[i - 1][0], p[1] - loop[i - 1][1])
                != (loop[(i + 1) % len(loop)][0] - p[0], loop[(i + 1) % len(loop)][1] - p[1])
            ]
            if len(corners) >= 3:
                loops.append(corners)
    if not loops:
        return []
    outline = max(loops, key=_area)
    # Split a closed ring into two open chains so RDP retains its topology.
    split = max(
        range(1, len(outline)),
        key=lambda i: hypot(outline[i][0] - outline[0][0], outline[i][1] - outline[0][1]),
    )
    tolerance = max(1, width * 0.002)
    for _ in range(8):
        result = (
            _simplify_line(outline[: split + 1], tolerance)[:-1]
            + _simplify_line(outline[split:] + [outline[0]], tolerance)[:-1]
        )
        if len(result) <= 64:
            return result if len(result) >= 3 else []
        tolerance *= 1.6
    return []


def analyze_image(path: Path, gap: int = 18) -> dict:
    """Find bounded areas; at most 30 suggestions, each with at most 64 vertices."""
    if type(gap) is not int or not 0 <= gap <= 40:
        raise ValueError("Türöffnungs-Ausgleich muss zwischen 0 und 40 liegen")
    with Image.open(path) as source:
        if source.width * source.height > 32_000_000:
            raise ValueError("Grundriss zu groß")
        image = source.convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    width, height = image.size
    if min(width, height) < 24:
        return {"candidates": [], "analysis_width": width, "analysis_height": height}
    # Retain dark structural lines and saturated wall fills. Thin lettering is
    # removed before small door gaps are closed, limiting furniture fragments.
    dark = image.convert("L").point(lambda value: 255 if value < 125 else 0)
    solid = dark.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    raw = dark.tobytes()
    lines = bytearray(width * height)
    minimum_run = max(6, width // 90)
    for vertical in (False, True):
        count, length = (width, height) if vertical else (height, width)
        for line in range(count):
            run = []
            for offset in range(length + 1):
                index = offset * width + line if vertical else line * width + offset
                if offset < length and raw[index]:
                    run.append(index)
                else:
                    if len(run) >= minimum_run:
                        for pixel in run:
                            lines[pixel] = 255
                    run = []
    solid = ImageChops.lighter(solid, Image.frombytes("L", (width, height), bytes(lines)))
    hsv = image.convert("HSV")
    saturated = hsv.getchannel("S").point(lambda value: 255 if value > 130 else 0)
    not_white = hsv.getchannel("V").point(lambda value: 255 if value < 245 else 0)
    walls = ImageChops.lighter(solid, ImageChops.darker(saturated, not_white))
    if gap:
        size = gap // 2 * 2 + 1
        walls = walls.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    blocked = walls.tobytes()
    visited = bytearray(width * height)
    minimum = max(80, int(width * height * 0.003))
    candidates = []
    for first in range(width * height):
        if visited[first] or blocked[first]:
            continue
        queue = deque([first])
        visited[first] = 1
        cells = []
        border = False
        while queue:
            index = queue.popleft()
            cells.append(index)
            x, y = index % width, index // width
            border |= x in (0, width - 1) or y in (0, height - 1)
            for neighbor in (
                index - width,
                index + width,
                index - 1 if x else -1,
                index + 1 if x < width - 1 else -1,
            ):
                if 0 <= neighbor < len(visited) and not visited[neighbor] and not blocked[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
        if border or not minimum <= len(cells) <= width * height * 0.65:
            continue
        points = _polygon(cells, width)
        if len(points) < 3 or _area(points) < minimum:
            continue
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        if max(xs) - min(xs) > width * 0.94 or max(ys) - min(ys) > height * 0.94:
            continue
        candidates.append(
            {
                "points": [[round(x / width, 5), round(y / height, 5)] for x, y in points],
                "area": round(_area(points) / (width * height), 5),
                "center": [
                    round(sum(i % width for i in cells) / len(cells) / width, 5),
                    round(sum(i // width for i in cells) / len(cells) / height, 5),
                ],
            }
        )
    candidates.sort(key=lambda item: item["area"], reverse=True)
    return {
        "candidates": [
            {"id": str(i + 1), **candidate} for i, candidate in enumerate(candidates[:30])
        ],
        "analysis_width": width,
        "analysis_height": height,
    }
