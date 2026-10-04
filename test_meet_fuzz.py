"""会合规划的随机交叉验证：以不做支配剪枝的全标签搜索为预言机，
校验 Planner.meet 的取解键（共同到达, 总步行, 总候车, 班次ID, 会合站ID）
与暴力最优一致；暴力无解时 meet 必须 blocked，反之亦然。"""

import heapq
import random
import sys
from itertools import count

sys.path.insert(0, "/workspace")

from planner import Planner, normalize


def brute_labels(pl, origin, earliest, walk_cap=60):
    """全标签搜索（仅按 (到达,步行,候车) 精确去重），返回 {站点: [标签]}。"""
    if not pl.station_open(origin, earliest)[0]:
        return None
    buckets = {s: [] for s in pl.n["stations"]}
    seen = {s: set() for s in pl.n["stations"]}
    start = (earliest, 0, 0, ())
    buckets[origin].append(start)
    seen[origin].add((earliest, 0, 0))
    heap = [(earliest, 0, start)]
    cnt = count(1)
    while heap:
        _, _, (ready, walk, wait, chain) = heapq.heappop(heap)
        # 由 chain 末段还原所在站
        station = chain[-1]["to"] if chain else origin
        for nb, mins in pl.n["walk_edges"].get(station, ()):
            arr = ready + mins
            if walk + mins > walk_cap:
                continue
            if not pl.station_open(nb, arr)[0]:
                continue
            key = (arr, walk + mins, wait)
            if key in seen[nb]:
                continue
            seen[nb].add(key)
            lab = (arr, walk + mins, wait,
                   chain + ({"to": nb},))
            buckets[nb].append(lab)
            heapq.heappush(heap, (arr, next(cnt), lab))
        for tid, idx in pl.n["departures"].get(station, ()):
            trip = pl.n["trips"][tid]
            dep = trip["stops"][idx]["time"]
            if dep < ready:
                continue
            if not pl.station_open(station, dep)[0]:
                continue
            if not pl.route_open(trip["route"], dep)[0]:
                continue
            w2 = wait + (dep - ready)
            for j in range(idx + 1, len(trip["stops"])):
                if pl.segment_closure(tid, j - 1) is not None:
                    break
                tgt = trip["stops"][j]["station"]
                arr = trip["stops"][j]["time"]
                if not pl.station_open(tgt, arr)[0]:
                    continue
                key = (arr, walk, w2)
                if key in seen[tgt]:
                    continue
                seen[tgt].add(key)
                lab = (arr, walk, w2, chain + ({"to": tgt},))
                buckets[tgt].append(lab)
                heapq.heappush(heap, (arr, next(cnt), lab))
    return buckets


def brute_meet(pl, oa, ea, ob, eb, dest):
    la_all = brute_labels(pl, oa, ea)
    lb_all = brute_labels(pl, ob, eb)
    if la_all is None or lb_all is None:
        return None
    best = None
    for tid in pl.n["trip_order"]:
        trip = pl.n["trips"][tid]
        stops = trip["stops"]
        for j, st in enumerate(stops):
            if st["station"] != dest:
                continue
            arr_dest = st["time"]
            if not pl.station_open(dest, arr_dest)[0]:
                continue
            for i in range(j):
                meet, dep = stops[i]["station"], stops[i]["time"]
                if not pl.station_open(meet, dep)[0]:
                    continue
                if not pl.route_open(trip["route"], dep)[0]:
                    continue
                if any(pl.segment_closure(tid, k) is not None
                       for k in range(i, j)):
                    continue
                pick = []
                ok = True
                for labels in (la_all.get(meet, []), lb_all.get(meet, [])):
                    feas = [(w, wt - a) for (a, w, wt, _) in labels if a <= dep]
                    if not feas:
                        ok = False
                        break
                    pick.append(min(feas))
                if not ok:
                    continue
                walk = pick[0][0] + pick[1][0]
                wait = (pick[0][1] + dep) + (pick[1][1] + dep)
                key = (arr_dest, walk, wait, tid, meet)
                if best is None or key < best:
                    best = key
    return best


def rand_network(rng):
    stations = ["A", "B", "C", "E"]
    trips = []
    for t in range(rng.randint(3, 5)):
        seq = rng.sample(stations, rng.randint(2, 4))
        tm = rng.randint(6 * 60, 8 * 60)
        stops = []
        for s in seq:
            tm += rng.randint(3, 25)
            if tm >= 14 * 60:
                break
            stops.append({"station": s, "time": f"{tm // 60:02d}:{tm % 60:02d}"})
        if len(stops) >= 2:
            trips.append({"id": f"T{t}", "route": f"{t}路", "stops": stops})
    if not trips:
        return None
    transfers = []
    for _ in range(rng.randint(0, 3)):
        a, b = rng.sample(stations, 2)
        transfers.append({"from": a, "to": b, "minutes": rng.randint(2, 12)})
    suspensions = []
    for _ in range(rng.randint(0, 2)):
        kind = rng.choice(["station", "route", "segment"])
        start = rng.randint(6 * 60, 11 * 60)
        end = start + rng.randint(10, 90)
        fmt = lambda x: f"{x // 60:02d}:{x % 60:02d}"
        if kind == "station":
            suspensions.append({"kind": "station", "ref": rng.choice(stations),
                                "start": fmt(start), "end": fmt(end)})
        elif kind == "route":
            suspensions.append({"kind": "route",
                                "ref": rng.choice(trips)["route"],
                                "start": fmt(start), "end": fmt(end)})
        else:
            trip = rng.choice(trips)
            seq = [s["station"] for s in trip["stops"]]
            if len(seq) < 2:
                continue
            i, j = sorted(rng.sample(range(len(seq)), 2))
            suspensions.append({"kind": "segment", "route": trip["route"],
                                "from": seq[i], "to": seq[j],
                                "start": fmt(start), "end": fmt(end)})
    return {"stations": [{"id": s, "name": s} for s in stations],
            "trips": trips, "transfers": transfers,
            "suspensions": suspensions}


def main():
    rng = random.Random(20261004)
    checked = ok_cnt = blocked_cnt = 0
    for trial in range(600):
        data = rand_network(rng)
        if data is None:
            continue
        # 优先选「有班次经停且非首站」的站点作终点，提高有解覆盖率
        served = [s["station"] for t in data["trips"] for s in t["stops"][1:]]
        dest = rng.choice(served) if served and rng.random() < 0.8 \
            else rng.choice(["A", "B", "C", "E"])
        origins = [s for s in ("A", "B", "C", "E") if s != dest]
        oa, ob = rng.choice(origins), rng.choice(origins)
        ea = rng.randint(6 * 60, 9 * 60)
        eb = rng.randint(6 * 60, 9 * 60)
        try:
            net = normalize(data)
        except Exception:
            continue
        pl = Planner(net)
        oracle = brute_meet(pl, oa, ea, ob, eb, dest)
        got = pl.meet(oa, ea, ob, eb, dest)
        checked += 1
        if oracle is None:
            assert got["status"] == "blocked", (
                f"trial {trial}: 暴力无解但 meet 返回 {got['status']}\n"
                f"{got}\n{data}\n{oa},{ea},{ob},{eb},{dest}")
            blocked_cnt += 1
            continue
        assert got["status"] == "ok", (
            f"trial {trial}: 暴力有解 {oracle} 但 meet blocked\n"
            f"{got.get('blocker')}\n{data}\n{oa},{ea},{ob},{eb},{dest}")
        mu = got["meetup"]
        got_key = (mu["arrival"], mu["walking_minutes"],
                   mu["waiting_minutes"], mu["trip_id"], mu["meet_station"])
        assert got_key == oracle, (
            f"trial {trial}: 取解不一致\n meet={got_key}\n 暴力={oracle}\n"
            f"{data}\n{oa},{ea},{ob},{eb},{dest}")
        # 时间线内部一致性：两人候车合计、步行合计与汇总一致
        pa, pb = mu["persons"]
        assert (pa["waiting_minutes"] + pb["waiting_minutes"]
                == mu["waiting_minutes"])
        assert (pa["walking_minutes"] + pb["walking_minutes"]
                == mu["walking_minutes"])
        for p in (pa, pb):
            assert p["waiting_minutes"] == sum(
                l["minutes"] for l in p["legs"] if l["type"] == "wait")
            assert p["walking_minutes"] == sum(
                l["minutes"] for l in p["legs"] if l["type"] == "walk")
        ok_cnt += 1
    print(f"随机交叉验证通过：{checked} 例（有解 {ok_cnt}，无解 {blocked_cnt}）")


if __name__ == "__main__":
    main()
