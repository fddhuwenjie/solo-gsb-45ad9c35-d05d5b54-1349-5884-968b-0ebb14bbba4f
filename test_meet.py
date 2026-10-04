"""两人同车会合（Planner.meet / /api/meet）行为验证脚本。"""

import json
import sys

sys.path.insert(0, "/workspace")

from planner import SAMPLE_DATA, PlanError, Planner, normalize


def m(hhmm):
    h, mm = map(int, hhmm.split(":"))
    return h * 60 + mm


def make_data(**over):
    base = {
        "stations": [{"id": s, "name": n} for s, n in [
            ("A", "甲城站"), ("B", "乙城站"), ("C", "会合广场"),
            ("D", "终点枢纽"), ("E", "东湖站"), ("X", "西大桥")]],
        "trips": [],
        "transfers": [],
        "suspensions": [],
    }
    base.update(over)
    return base


def meet(data, oa="A", ea="08:00", ob="B", eb="08:00", dest="D"):
    net = normalize(data)
    return Planner(net).meet(oa, m(ea), ob, m(eb), dest)


passed = failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}  {extra}")


print("== 1. 基本会合：各自乘车到会合站，同乘一班直达终点 ==")
data = make_data(trips=[
    {"id": "T1", "route": "1路", "stops": [
        {"station": "C", "time": "08:30"}, {"station": "D", "time": "09:00"}]},
    {"id": "T2", "route": "2路", "stops": [
        {"station": "B", "time": "08:05"}, {"station": "C", "time": "08:20"}]},
    {"id": "T3", "route": "3路", "stops": [
        {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:15"}]},
])
r = meet(data)
check("会合成功", r["status"] == "ok", json.dumps(r, ensure_ascii=False))
mu = r.get("meetup", {})
check("会合站 C、共同班次 T1、09:00 到达",
      mu.get("meet_station") == "C" and mu.get("trip_id") == "T1"
      and mu.get("board_time") == m("08:30") and mu.get("arrival") == m("09:00"),
      json.dumps(mu, ensure_ascii=False))
pa, pb = mu["persons"]
check("甲前段：T3 A→C，等到 08:30（候车 15 分钟计入甲）",
      [l["type"] for l in pa["legs"]] == ["ride", "wait"]
      and pa["legs"][0]["trip_id"] == "T3"
      and pa["legs"][1].get("await_shared") is True
      and pa["waiting_minutes"] == 15 and pa["arrival_at_meet"] == m("08:15"),
      json.dumps(pa, ensure_ascii=False))
check("乙前段：候车 5 + T2，等到 08:30（候车共 15 分钟计入乙）",
      [l["type"] for l in pb["legs"]] == ["wait", "ride", "wait"]
      and pb["waiting_minutes"] == 15,
      json.dumps(pb, ensure_ascii=False))
check("同乘段只出现一次：C→D，shared 标记",
      mu["shared"]["type"] == "ride" and mu["shared"]["from"] == "C"
      and mu["shared"]["to"] == "D" and mu["shared"].get("shared") is True
      and mu["shared"]["trip_id"] == "T1")
check("两人时间线中不含同乘段（各自的段都不越过了会合站）",
      all(l.get("to") != "D" for l in pa["legs"] if l["type"] == "ride")
      and all(l.get("to") != "D" for l in pb["legs"] if l["type"] == "ride"))
check("总候车 = 两人分别计入之和 = 30，总步行 = 0",
      mu["waiting_minutes"] == 30 and mu["walking_minutes"] == 0
      and mu["waiting_minutes"]
      == pa["waiting_minutes"] + pb["waiting_minutes"])

print("== 2. 较晚到会合站但步行更少的前段优先（而非最快前段）==")
data = make_data(
    trips=[
        {"id": "T1", "route": "1路", "stops": [
            {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
        {"id": "T9", "route": "9路", "stops": [
            {"station": "A", "time": "08:40"}, {"station": "C", "time": "08:50"}]},
    ],
    transfers=[{"from": "A", "to": "C", "minutes": 30}],
)
r = meet(data, oa="A", ea="08:00", ob="C", eb="08:00")
mu = r.get("meetup", {})
pa = mu["persons"][0]
# 甲最快前段是步行 30 分钟 08:30 到 C；乘 T9 则 08:50 才到但步行 0 —— 应选后者
check("甲选乘 T9（08:50 到）而非步行（08:30 到）",
      r["status"] == "ok" and pa["arrival_at_meet"] == m("08:50")
      and any(l["type"] == "ride" and l["trip_id"] == "T9" for l in pa["legs"])
      and not any(l["type"] == "walk" for l in pa["legs"]),
      json.dumps(pa, ensure_ascii=False))
check("甲步行 0、候车 50（08:00→08:40 等 40 + 08:50→09:00 等 10）",
      pa["walking_minutes"] == 0 and pa["waiting_minutes"] == 50,
      json.dumps(pa, ensure_ascii=False))
check("乙起点即会合站：只等共同班次",
      mu["persons"][1]["origin"] == "C"
      and [l["type"] for l in mu["persons"][1]["legs"]] == ["wait"]
      and mu["persons"][1]["legs"][0].get("await_shared") is True
      and mu["persons"][1]["waiting_minutes"] == 60,
      json.dumps(mu["persons"][1], ensure_ascii=False))

print("== 3. 字典序：共同到达 → 总步行 → 总候车 → 班次 ID → 会合站 ID ==")
# 3a. 共同到达更早者优先，哪怕步行更多
data = make_data(
    trips=[
        {"id": "T1", "route": "1路", "stops": [
            {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
        {"id": "T2", "route": "2路", "stops": [
            {"station": "E", "time": "09:00"}, {"station": "D", "time": "09:20"}]},
        {"id": "T3", "route": "3路", "stops": [
            {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
        {"id": "T5", "route": "5路", "stops": [
            {"station": "B", "time": "08:00"}, {"station": "C", "time": "08:10"}]},
        {"id": "T6", "route": "6路", "stops": [
            {"station": "B", "time": "08:00"}, {"station": "E", "time": "08:45"}]},
    ],
    transfers=[{"from": "C", "to": "E", "minutes": 10}],
)
r = meet(data)
mu = r.get("meetup", {})
check("到达更早的 T2（09:20）胜出让甲步行 10 分钟的方案",
      r["status"] == "ok" and mu.get("trip_id") == "T2"
      and mu.get("meet_station") == "E" and mu.get("arrival") == m("09:20")
      and mu.get("walking_minutes") == 10,
      json.dumps(mu, ensure_ascii=False))

# 3b. 到达相同：总步行更少者优先
data = make_data(
    trips=[
        {"id": "T1", "route": "1路", "stops": [
            {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
        {"id": "T2", "route": "2路", "stops": [
            {"station": "E", "time": "09:10"}, {"station": "D", "time": "09:30"}]},
        {"id": "T3", "route": "3路", "stops": [
            {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
        {"id": "T5", "route": "5路", "stops": [
            {"station": "B", "time": "08:00"}, {"station": "C", "time": "08:10"}]},
        {"id": "T6", "route": "6路", "stops": [
            {"station": "B", "time": "08:00"}, {"station": "E", "time": "08:45"}]},
    ],
    transfers=[{"from": "C", "to": "E", "minutes": 10}],
)
r = meet(data)
mu = r.get("meetup", {})
check("同为 09:30 到达：步行 0 的 T1@C 胜过步行 10 的 T2@E",
      r["status"] == "ok" and mu.get("trip_id") == "T1"
      and mu.get("meet_station") == "C" and mu.get("walking_minutes") == 0,
      json.dumps(mu, ensure_ascii=False))

# 3c. 到达、步行都相同：总候车更少者优先
data = make_data(trips=[
    {"id": "T1", "route": "1路", "stops": [
        {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
    {"id": "T2", "route": "1路", "stops": [
        {"station": "C", "time": "09:20"}, {"station": "D", "time": "09:30"}]},
    {"id": "T3", "route": "3路", "stops": [
        {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
    {"id": "T5", "route": "5路", "stops": [
        {"station": "B", "time": "08:00"}, {"station": "C", "time": "08:10"}]},
])
r = meet(data)
mu = r.get("meetup", {})
check("同为 09:30 到达、步行 0：候车 90 的 T1(09:00) 胜过候车 130 的 T2(09:20)",
      r["status"] == "ok" and mu.get("trip_id") == "T1"
      and mu.get("waiting_minutes") == 90,
      json.dumps(mu, ensure_ascii=False))

# 3d. 班次 ID 同分：取班次 ID 较小者
data = make_data(trips=[
    {"id": "TB", "route": "1路", "stops": [
        {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
    {"id": "TA", "route": "1路", "stops": [
        {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
    {"id": "T3", "route": "3路", "stops": [
        {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
    {"id": "T5", "route": "5路", "stops": [
        {"station": "B", "time": "08:00"}, {"station": "C", "time": "08:10"}]},
])
r = meet(data)
check("全同分：取班次 ID 较小者 TA", r.get("meetup", {}).get("trip_id") == "TA",
      json.dumps(r.get("meetup", {}), ensure_ascii=False))

# 3e. 会合站 ID 同分：取会合站 ID 较小者（两人都在 C，T1 经 C、E 到 D）
data = make_data(trips=[
    {"id": "T1", "route": "1路", "stops": [
        {"station": "C", "time": "09:00"}, {"station": "E", "time": "09:10"},
        {"station": "D", "time": "09:30"}]},
])
r = meet(data, oa="C", ea="08:00", ob="C", eb="08:00")
mu = r.get("meetup", {})
check("同班次同到达同候车：取会合站 ID 较小者 C（而非 E）",
      r["status"] == "ok" and mu.get("meet_station") == "C"
      and mu.get("board_time") == m("09:00"),
      json.dumps(mu, ensure_ascii=False))

print("== 4. 会合前段与同乘段都遵守停运约束 ==")
# 4a. 会合站在共同班次发车时封站 → 该候选不可用
data = make_data(
    trips=[
        {"id": "T1", "route": "1路", "stops": [
            {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
        {"id": "T2", "route": "2路", "stops": [
            {"station": "C", "time": "09:10"}, {"station": "D", "time": "09:40"}]},
        {"id": "T3", "route": "3路", "stops": [
            {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
    ],
    suspensions=[{"kind": "station", "ref": "C",
                  "start": "08:55", "end": "09:05", "label": "临时封站"}],
)
r = meet(data, oa="A", ob="C")
mu = r.get("meetup", {})
check("会合站 09:00 封站：改用 09:10 的 T2",
      r["status"] == "ok" and mu.get("trip_id") == "T2"
      and mu.get("arrival") == m("09:40"),
      json.dumps(r, ensure_ascii=False))

# 4b. 共同班次所属线路整线停运 → 整班跳过
data = make_data(
    trips=[
        {"id": "T1", "route": "1路", "stops": [
            {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
        {"id": "T2", "route": "2路", "stops": [
            {"station": "C", "time": "09:10"}, {"station": "D", "time": "09:40"}]},
        {"id": "T3", "route": "3路", "stops": [
            {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
    ],
    suspensions=[{"kind": "route", "ref": "1路",
                  "start": "08:00", "end": "23:59", "label": "全线停运"}],
)
r = meet(data, oa="A", ob="C")
check("1路整线停运：共同班次改用 2路 T2",
      r["status"] == "ok" and r["meetup"]["trip_id"] == "T2",
      json.dumps(r, ensure_ascii=False))

# 4c. 同乘区间被区段停运封锁 → 该班次不能作共同班次
data = make_data(
    trips=[
        {"id": "T1", "route": "1路", "stops": [
            {"station": "C", "time": "09:00"}, {"station": "X", "time": "09:10"},
            {"station": "D", "time": "09:20"}]},
        {"id": "T2", "route": "2路", "stops": [
            {"station": "C", "time": "09:05"}, {"station": "D", "time": "09:35"}]},
        {"id": "T3", "route": "3路", "stops": [
            {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
    ],
    suspensions=[{"kind": "segment", "route": "1路", "from": "X", "to": "D",
                  "start": "00:00", "end": "23:59", "label": "区间封锁"}],
)
r = meet(data, oa="A", ob="C")
check("T1 同乘区间 X→D 被封锁：改用 T2",
      r["status"] == "ok" and r["meetup"]["trip_id"] == "T2"
      and r["meetup"]["arrival"] == m("09:35"),
      json.dumps(r, ensure_ascii=False))
data_no_t2 = make_data(
    trips=[
        {"id": "T1", "route": "1路", "stops": [
            {"station": "C", "time": "09:00"}, {"station": "X", "time": "09:10"},
            {"station": "D", "time": "09:20"}]},
        {"id": "T3", "route": "3路", "stops": [
            {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
    ],
    suspensions=[{"kind": "segment", "route": "1路", "from": "X", "to": "D",
                  "start": "00:00", "end": "23:59", "label": "区间封锁"}],
)
r = meet(data_no_t2, oa="A", ob="C")
check("唯一共同班次被区段封锁 → blocked 且归因区段停运",
      r["status"] == "blocked" and r["blocker"]["kind"] == "no_shared_ride"
      and r["blocker"].get("cause") == "segment_suspended"
      and "meetup" not in r,
      json.dumps(r, ensure_ascii=False))

# 4d. 甲的前段被区段停运截断：步行绕行后到会合站
data = make_data(
    trips=[
        {"id": "T1", "route": "1路", "stops": [
            {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
        {"id": "T9", "route": "9路", "stops": [
            {"station": "A", "time": "08:00"}, {"station": "B", "time": "08:10"},
            {"station": "C", "time": "08:20"}]},
    ],
    transfers=[{"from": "B", "to": "C", "minutes": 12}],
    suspensions=[{"kind": "segment", "route": "9路", "from": "B", "to": "C",
                  "start": "00:00", "end": "23:59", "label": "区间施工"}],
)
r = meet(data, oa="A", ob="C")
mu = r.get("meetup", {})
pa = mu.get("persons", [{}])[0]
check("甲前段：T9 在 B 截断（带截断说明），步行 B→C 赴约",
      r["status"] == "ok" and mu.get("meet_station") == "C"
      and [l["type"] for l in pa["legs"]] == ["ride", "walk", "wait"]
      and pa["legs"][0].get("truncated") is True
      and pa["legs"][1]["from"] == "B" and pa["legs"][1]["to"] == "C"
      and pa["walking_minutes"] == 12,
      json.dumps(pa, ensure_ascii=False))

# 4e. 步行到达邻站遇封站窗口：较早到 E 反而走不进 B，较晚前段不得被误剪
data = make_data(
    stations=[{"id": s, "name": s} for s in ("B", "C", "E")],
    trips=[
        {"id": "T0", "route": "0路", "stops": [
            {"station": "C", "time": "06:55"}, {"station": "E", "time": "07:19"}]},
        {"id": "T4", "route": "4路", "stops": [
            {"station": "C", "time": "07:11"}, {"station": "E", "time": "07:29"}]},
        {"id": "T3", "route": "3路", "stops": [
            {"station": "B", "time": "08:22"}, {"station": "E", "time": "08:41"}]},
    ],
    transfers=[{"from": "E", "to": "B", "minutes": 4}],
    suspensions=[{"kind": "station", "ref": "B",
                  "start": "06:32", "end": "07:27", "label": "早间封站"}],
)
# 甲 06:29 从 C：T0 到 E(07:19) 步行进 B 会撞上封站(07:23<07:27)，
# 只有 T4 到 E(07:29) 再步行才能在 07:33 进入 B 赶上 T3
r = meet(data, oa="C", ea="06:29", ob="B", eb="07:48", dest="E")
mu = r.get("meetup", {})
check("封站窗口下较晚前段不被误剪：甲乘 T4 步行进 B，同乘 T3",
      r["status"] == "ok" and mu.get("meet_station") == "B"
      and mu.get("trip_id") == "T3" and mu.get("arrival") == m("08:41"),
      json.dumps(r, ensure_ascii=False))
pa = mu.get("persons", [{}])[0]
check("甲前段为 T4（非更早的 T0），07:33 到 B，候车 42+49=91",
      [l["type"] for l in pa["legs"]] == ["wait", "ride", "walk", "wait"]
      and pa["legs"][1]["trip_id"] == "T4"
      and pa["arrival_at_meet"] == m("07:33")
      and pa["waiting_minutes"] == 91,
      json.dumps(pa, ensure_ascii=False))
check("两人总候车 91+34=125", mu.get("waiting_minutes") == 125,
      json.dumps(mu, ensure_ascii=False))

print("== 5. 前段与同乘段为同一班次（不下车继续乘）==")
data = make_data(trips=[
    {"id": "T1", "route": "1路", "stops": [
        {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:30"},
        {"station": "D", "time": "09:00"}]},
])
r = meet(data, oa="A", ob="C")
mu = r.get("meetup", {})
check("甲乘 T1 到 C 不下车，乙在 C 上车，同乘段 C→D",
      r["status"] == "ok" and mu.get("meet_station") == "C"
      and mu.get("trip_id") == "T1"
      and [l["type"] for l in mu["persons"][0]["legs"]] == ["ride"]
      and mu["persons"][0]["arrival_at_meet"] == m("08:30")
      and mu["persons"][0]["waiting_minutes"] == 0
      and mu["persons"][1]["waiting_minutes"] == 30,
      json.dumps(mu, ensure_ascii=False))

print("== 6. 未能同行：返回原因，绝不把单人路线当作同行 ==")
# 6a. 乙赶到会合站时共同班次已发车
data = make_data(trips=[
    {"id": "T1", "route": "1路", "stops": [
        {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
    {"id": "T3", "route": "3路", "stops": [
        {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
    {"id": "T4", "route": "4路", "stops": [
        {"station": "B", "time": "08:00"}, {"station": "C", "time": "09:30"}]},
])
r = meet(data)
check("乙赶不上共同班次 → blocked/no_common_trip，消息指明乙与班次",
      r["status"] == "blocked" and r["blocker"]["kind"] == "no_common_trip"
      and "乙" in r["blocker"]["message"]
      and "T1" in r["blocker"]["message"]
      and "赶不上" in r["blocker"]["message"] and "meetup" not in r,
      json.dumps(r, ensure_ascii=False))
solo = Planner(normalize(data)).plan("A", "D", m("08:00"), "fastest")
check("甲单独其实能到终点（会合失败不是网络无解）",
      solo["status"] == "ok" and solo["itinerary"]["arrival"] == m("09:30"))
check("会合结果不把甲的单人路线当同行方案返回",
      "meetup" not in r and r["status"] == "blocked")

# 6b. 乙的起点完全无班次 → 无法到达任何会合站
data = make_data(trips=[
    {"id": "T1", "route": "1路", "stops": [
        {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
    {"id": "T3", "route": "3路", "stops": [
        {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
])
r = meet(data)
check("乙无法到达会合站 → blocked，消息说明乙无法从乙城站出发",
      r["status"] == "blocked" and r["blocker"]["kind"] == "no_common_trip"
      and "乙" in r["blocker"]["message"]
      and "无法从" in r["blocker"]["message"],
      json.dumps(r, ensure_ascii=False))

# 6c. 终点站没有任何班次
r = meet(make_data(trips=[
    {"id": "T3", "route": "3路", "stops": [
        {"station": "A", "time": "08:00"}, {"station": "C", "time": "08:20"}]},
]), dest="D")
check("终点无班次 → no_service",
      r["status"] == "blocked" and r["blocker"]["kind"] == "no_service"
      and "没有任何经停班次" in r["blocker"]["message"],
      json.dumps(r, ensure_ascii=False))

# 6d. 甲的起点站在最早出发时刻封站
data = make_data(
    trips=[
        {"id": "T1", "route": "1路", "stops": [
            {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
        {"id": "T3", "route": "3路", "stops": [
            {"station": "A", "time": "08:20"}, {"station": "C", "time": "08:40"}]},
    ],
    suspensions=[{"kind": "station", "ref": "A",
                  "start": "07:00", "end": "09:00", "label": "封站"}],
)
r = meet(data, oa="A", ob="C")
check("甲起点封站 → origin_closed 且指明甲",
      r["status"] == "blocked" and r["blocker"]["kind"] == "origin_closed"
      and r["blocker"].get("person") == "甲"
      and "未能同行" in r["blocker"]["message"],
      json.dumps(r, ensure_ascii=False))

print("== 7. 输入校验 ==")


def expect_err(name, fn, frag):
    global passed, failed
    try:
        fn()
    except PlanError as exc:
        if frag in str(exc):
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name}  {exc}")
        return
    failed += 1
    print(f"  ✗ {name}  未报错")


simple = make_data(trips=[
    {"id": "T1", "route": "1路", "stops": [
        {"station": "C", "time": "09:00"}, {"station": "D", "time": "09:30"}]},
])
expect_err("甲起点与终点相同",
           lambda: Planner(normalize(simple)).meet("D", 0, "B", 0, "D"),
           "甲的起点站与终点站相同")
expect_err("乙起点与终点相同",
           lambda: Planner(normalize(simple)).meet("A", 0, "D", 0, "D"),
           "乙的起点站与终点站相同")
expect_err("甲起点不存在",
           lambda: Planner(normalize(simple)).meet("ZZ", 0, "B", 0, "D"),
           "甲的起点站不存在")
expect_err("终点不存在",
           lambda: Planner(normalize(simple)).meet("A", 0, "B", 0, "ZZ"),
           "终点站不存在")

print("== 8. 内置示例网络：S1/S2 → S6 ==")
r = Planner(normalize(SAMPLE_DATA)).meet("S1", m("08:00"), "S2", m("08:00"),
                                         "S6")
mu = r.get("meetup", {})
check("示例：乙步行到 S1 与甲会合，同乘 K2 直达 S6（08:35）",
      r["status"] == "ok" and mu.get("meet_station") == "S1"
      and mu.get("trip_id") == "K2" and mu.get("arrival") == m("08:35")
      and mu.get("walking_minutes") == 4
      and mu.get("waiting_minutes") == 12,
      json.dumps(mu, ensure_ascii=False))
check("示例：K2b 因 2路 S4→S6 区段停运不能作共同班次（未选 09:05 方案）",
      mu.get("trip_id") != "K2b")

print(f"\n通过 {passed}，失败 {failed}")
sys.exit(1 if failed else 0)
