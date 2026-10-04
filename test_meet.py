"""两人同车会合（/api/meet 对应的 Planner.plan_meeting）行为验证脚本。"""

import json
import sys

sys.path.insert(0, "/workspace")

from planner import SAMPLE_DATA, PlanError, Planner, normalize


def m(hhmm):
    h, mm = map(int, hhmm.split(":"))
    return h * 60 + mm


passed = failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}  {extra}")


def meet(data, o1, o2, dest, e1="08:00", e2="08:00"):
    people = [
        {"origin": o1, "earliest": m(e1), "label": "同行人甲"},
        {"origin": o2, "earliest": m(e2), "label": "同行人乙"},
    ]
    return Planner(normalize(data)).plan_meeting(people, dest)


# --------------------------------------------------------------------- #
# 小网络构造器
# --------------------------------------------------------------------- #
T1_MD = {"id": "T1", "route": "1路", "stops": [
    {"station": "M", "time": "08:22"},
    {"station": "D", "time": "08:40"}]}
T3_MD = {"id": "T3", "route": "1路", "stops": [
    {"station": "M", "time": "08:50"},
    {"station": "D", "time": "09:05"}]}
T2_AM = {"id": "T2", "route": "2路", "stops": [
    {"station": "A", "time": "08:05"},
    {"station": "M", "time": "08:21"}]}
STATIONS_4 = [{"id": "A", "name": "甲起点"},
              {"id": "B", "name": "乙起点"},
              {"id": "M", "name": "会合站"},
              {"id": "D", "name": "终点"}]


def tiny_net():
    """A、B 两人起点；M 会合站；D 终点。T1 08:22 M->D；T2 A 08:05->M 08:21。"""
    return {"stations": STATIONS_4, "trips": [T1_MD, T2_AM],
            "transfers": [], "suspensions": []}


print("== 1. 基本同车会合：各自前段 + 只出现一次的同乘段 ==")
data = tiny_net()
data["transfers"] = [{"from": "B", "to": "M", "minutes": 5}]
r = meet(data, "A", "B", "D")
check("状态 ok", r["status"] == "ok", json.dumps(r, ensure_ascii=False))
mm = r["meeting"]
check("会合站 M、共同班次 T1、08:40 到达",
      mm["meeting_station"] == "M" and mm["trip_id"] == "T1"
      and mm["arrival"] == m("08:40"), json.dumps(mm, ensure_ascii=False))
a, b = mm["people"]
check("甲前段 T2 08:21 到 M，步行 0",
      a["arrive_meeting"] == m("08:21") and a["walking_minutes"] == 0)
check("乙步行 5 分钟 08:05 到 M",
      b["arrive_meeting"] == m("08:05") and b["walking_minutes"] == 5)
check("候车分别计入：甲等 6（等 T2 5 + M 等 T1 1）、乙等 17",
      a["waiting_minutes"] == 6 and b["waiting_minutes"] == 17,
      json.dumps(mm["people"], ensure_ascii=False))
check("合计候车 23、合计步行 5",
      mm["waiting_minutes"] == 23 and mm["walking_minutes"] == 5)
check("同乘段只出现一次且为 M->D",
      mm["shared_leg"]["trip_id"] == "T1"
      and mm["shared_leg"]["from"] == "M" and mm["shared_leg"]["to"] == "D"
      and mm["shared_leg"].get("shared") is True)
check("两人前段都不含同乘段 M->D",
      all(not any(l.get("trip_id") == "T1" for l in p["legs"])
          for p in mm["people"]))
check("每人时间线末尾都排到共同班次发车（含 M 的候车段）",
      all(any(l["type"] == "wait" and l["station"] == "M"
              and l["end"] == m("08:22") for l in p["legs"])
          for p in mm["people"]))
check("rides = 两人前段班次数(1+0) + 同乘 1 = 2", mm["rides"] == 2)

print("== 2. 较晚到会合站但步行更少、仍赶得上的前段应胜出 ==")
# 甲从 P 到 M：步行 2 分钟 08:02 到（最快，步行 2）或乘 T2 08:20 到（步行 0）。
# 两方案都赶得上 T1 08:22，应选乘车前段（更晚到但步行更少）。
data2 = {
    "stations": [{"id": "O"}, {"id": "P"}, {"id": "M"}, {"id": "D"}],
    "trips": [
        {"id": "T1", "route": "1路", "stops": [
            {"station": "M", "time": "08:22"},
            {"station": "D", "time": "08:40"}]},
        {"id": "T2", "route": "2路", "stops": [
            {"station": "O", "time": "08:05"},
            {"station": "P", "time": "08:10"},
            {"station": "M", "time": "08:20"}]}],
    "transfers": [{"from": "P", "to": "M", "minutes": 2},
                  {"from": "O", "to": "P", "minutes": 10}],
    "suspensions": [],
}
r2 = meet(data2, "P", "O", "D")
p_a = r2["meeting"]["people"][0]
check("甲选更晚(08:20)但步行 0 的乘车前段，而非 08:02 步行前段",
      p_a["arrive_meeting"] == m("08:20") and p_a["walking_minutes"] == 0,
      json.dumps(p_a, ensure_ascii=False))
check("甲前段时间线为 候车P->乘T2->候车M",
      [(l["type"]) for l in p_a["legs"]] == ["wait", "ride", "wait"])

# 共同班次提前到 08:15 发车，乘车前段赶不上 → 必须选步行前段
data2b = json.loads(json.dumps(data2))
data2b["trips"][0]["stops"][0]["time"] = "08:15"
r2b = meet(data2b, "P", "O", "D")
p_a = r2b["meeting"]["people"][0]
check("共同班次提前到 08:15 时，甲回退选 08:02 步行前段（乘车前段已赶不上）",
      r2b["status"] == "ok" and p_a["arrive_meeting"] == m("08:02")
      and p_a["walking_minutes"] == 2, json.dumps(r2b, ensure_ascii=False))

print("== 3. 字典序：共同到达 → 总步行 → 总候车 → 班次 ID → 会合站 ID ==")
data3 = {
    "stations": [{"id": "A"}, {"id": "B"}, {"id": "M"}, {"id": "X"},
                 {"id": "D"}],
    "trips": [
        T3_MD, T2_AM,
        {"id": "TQ", "route": "9路", "stops": [
            {"station": "X", "time": "08:30"},
            {"station": "D", "time": "08:35"}]}],
    "transfers": [{"from": "B", "to": "M", "minutes": 5},
                  {"from": "A", "to": "X", "minutes": 6},
                  {"from": "B", "to": "X", "minutes": 8}],
    "suspensions": [],
}
r3 = meet(data3, "A", "B", "D")
check("到达时刻优先：选 X@TQ 08:35 到（步行 14）而非 M@T3 09:05（步行 5）",
      r3["meeting"]["meeting_station"] == "X"
      and r3["meeting"]["arrival"] == m("08:35")
      and r3["meeting"]["walking_minutes"] == 14,
      json.dumps(r3["meeting"], ensure_ascii=False))

# 到达相同 → 总步行优先：让 TQ 也 09:05 到
data3b = json.loads(json.dumps(data3))
data3b["trips"][2]["stops"][1]["time"] = "09:05"
r3b = meet(data3b, "A", "B", "D")
check("到达相同选步行更少的 M@T3（5<14）",
      r3b["meeting"]["meeting_station"] == "M"
      and r3b["meeting"]["trip_id"] == "T3"
      and r3b["meeting"]["walking_minutes"] == 5,
      json.dumps(r3b["meeting"], ensure_ascii=False))

# 到达/步行/候车都相同 → 班次 ID 字典序
data3c = tiny_net()
data3c["transfers"] = [{"from": "B", "to": "M", "minutes": 5}]
data3c["trips"].append({"id": "ZBUS", "route": "1路", "stops": [
    {"station": "M", "time": "08:22"},
    {"station": "D", "time": "08:40"}]})
r3c = meet(data3c, "A", "B", "D")
check("同分时班次 ID 小者胜（T1 < ZBUS）",
      r3c["meeting"]["trip_id"] == "T1", json.dumps(r3c["meeting"], ensure_ascii=False))

# 到达、步行相同 → 总候车更少者胜
data3d = {
    "stations": [{"id": "A"}, {"id": "B"}, {"id": "M"}, {"id": "N"},
                 {"id": "D"}],
    "trips": [
        {"id": "TM", "route": "1路", "stops": [
            {"station": "M", "time": "08:40"},
            {"station": "D", "time": "09:00"}]},
        {"id": "TN", "route": "2路", "stops": [
            {"station": "N", "time": "08:30"},
            {"station": "D", "time": "09:00"}]},
        {"id": "TA", "route": "3路", "stops": [
            {"station": "A", "time": "08:05"},
            {"station": "M", "time": "08:20"},
            {"station": "N", "time": "08:25"}]}],
    "transfers": [{"from": "B", "to": "M", "minutes": 5},
                  {"from": "B", "to": "N", "minutes": 5},
                  {"from": "M", "to": "N", "minutes": 3}],
    "suspensions": [],
}
# M 会合：甲 08:20 到等 20，乙 08:05 到等 35 -> 候车 55，步行 5
# N 会合：甲乘 TA 08:25 到 N（候车 10），乙走 B->N 08:05 等 25 -> 候车 35
r3d = meet(data3d, "A", "B", "D")
check("到达/步行相同选总候车更少的 N@TN（35<55）",
      r3d["meeting"]["meeting_station"] == "N"
      and r3d["meeting"]["trip_id"] == "TN"
      and r3d["meeting"]["waiting_minutes"] == 35,
      json.dumps(r3d["meeting"], ensure_ascii=False))

print("== 4. 步行换乘时刻 / 站点停运 / 整线停运 / 区段封锁 ==")
data4 = tiny_net()
data4["transfers"] = [{"from": "B", "to": "M", "minutes": 22}]
r4 = meet(data4, "A", "B", "D")
check("乙步行 08:22 准点到 M，赶得上 T1", r4["status"] == "ok"
      and r4["meeting"]["trip_id"] == "T1", json.dumps(r4, ensure_ascii=False))

# 区段封锁同乘段 M->D（覆盖 T1 不覆盖 T3）→ 改乘 T3
data4b = {"stations": STATIONS_4, "trips": [T1_MD, T3_MD, T2_AM],
          "transfers": [{"from": "B", "to": "M", "minutes": 5}],
          "suspensions": [{"kind": "segment", "route": "1路", "from": "M",
                           "to": "D", "start": "08:20", "end": "08:45",
                           "label": "封锁早班"}]}
r4b = meet(data4b, "A", "B", "D")
check("同乘段被区段封锁 → 跳过 T1 选 T3",
      r4b["status"] == "ok" and r4b["meeting"]["trip_id"] == "T3"
      and r4b["meeting"]["arrival"] == m("09:05"),
      json.dumps(r4b, ensure_ascii=False))

# 整线停运窗口覆盖 T1 发车 → 跳过 T1
data4c = json.loads(json.dumps(data4b))
data4c["suspensions"] = [{"kind": "route", "ref": "1路",
                          "start": "08:00", "end": "08:30"}]
r4c = meet(data4c, "A", "B", "D")
check("整线停运覆盖 T1 发车 → 选 T3", r4c["meeting"]["trip_id"] == "T3")

# 终点 D 在 T1 到达时封站 → T1 不可在 D 下车，选 T3
data4d = json.loads(json.dumps(data4b))
data4d["suspensions"] = [{"kind": "station", "ref": "D",
                          "start": "08:35", "end": "08:45"}]
r4d = meet(data4d, "A", "B", "D")
check("终点站到达时封站 → 选 T3", r4d["meeting"]["trip_id"] == "T3")

# 会合站 M 在 T1 发车时封站（两人步行早已在站）→ T1 不能上车，选 T3
data4e = {"stations": STATIONS_4, "trips": [T1_MD, T3_MD, T2_AM],
          "transfers": [{"from": "A", "to": "M", "minutes": 10},
                        {"from": "B", "to": "M", "minutes": 5}],
          "suspensions": [{"kind": "station", "ref": "M",
                           "start": "08:20", "end": "08:25"}]}
r4e = meet(data4e, "A", "B", "D")
check("会合站在共同班次发车时封站 → 选 T3",
      r4e["meeting"]["trip_id"] == "T3", json.dumps(r4e, ensure_ascii=False))

# 前段乘车受区段封锁截断：T2 的 X->M 封锁，甲乘到 X 后步行 X->M 会合
data4f = {
    "stations": [{"id": "A"}, {"id": "B"}, {"id": "X"}, {"id": "M"},
                 {"id": "D"}],
    "trips": [
        {"id": "T1", "route": "1路", "stops": [
            {"station": "M", "time": "08:50"},
            {"station": "D", "time": "09:05"}]},
        {"id": "T2", "route": "2路", "stops": [
            {"station": "A", "time": "08:05"},
            {"station": "X", "time": "08:21"},
            {"station": "M", "time": "08:25"}]}],
    "transfers": [{"from": "B", "to": "M", "minutes": 5},
                  {"from": "X", "to": "M", "minutes": 3}],
    "suspensions": [{"kind": "segment", "route": "2路", "from": "X",
                     "to": "M", "start": "00:00", "end": "23:59",
                     "label": "2路区间施工"}],
}
r4f = meet(data4f, "A", "B", "D")
a_legs = r4f["meeting"]["people"][0]["legs"]
fr = [l for l in a_legs if l["type"] == "ride"][0]
check("前段乘车在封锁段起点 X 截断并带 truncated 标注",
      fr["to"] == "X" and fr.get("truncated") and "区段停运" in fr["truncation"],
      json.dumps(fr, ensure_ascii=False))
check("截断后步行 X->M 完成会合，合计步行 = 甲3 + 乙5 = 8",
      any(l["type"] == "walk" and l["from"] == "X" and l["to"] == "M"
          for l in a_legs) and r4f["meeting"]["walking_minutes"] == 8)

# 前段步行到达会合站时该站封站，甲无其他路径 → cannot_meet
data4g = {
    "stations": STATIONS_4,
    "trips": [{"id": "T1", "route": "1路", "stops": [
        {"station": "M", "time": "08:50"},
        {"station": "D", "time": "09:05"}]}],
    "transfers": [{"from": "A", "to": "M", "minutes": 10},
                  {"from": "B", "to": "M", "minutes": 5}],
    "suspensions": [{"kind": "station", "ref": "M",
                     "start": "08:05", "end": "08:15"}],
}
r4g = meet(data4g, "A", "B", "D")
check("步行进入封站导致无法会合 → blocked/cannot_meet 且说明无法到达会合站",
      r4g["status"] == "blocked"
      and r4g["blocker"]["kind"] == "cannot_meet"
      and "无法到达会合站" in r4g["blocker"]["message"],
      json.dumps(r4g.get("blocker"), ensure_ascii=False))

print("== 5. 找不到共同班次：返回原因，绝不把单方直达当同行 ==")
data5 = tiny_net()
data5["transfers"] = [{"from": "B", "to": "M", "minutes": 25}]
r5 = meet(data5, "A", "B", "D")
check("状态 blocked 且 kind=cannot_meet",
      r5["status"] == "blocked" and r5["blocker"]["kind"] == "cannot_meet",
      json.dumps(r5, ensure_ascii=False))
msg5 = r5["blocker"]["message"]
check("消息指出乙晚 3 分钟赶不上 T1",
      "同行人乙" in msg5 and "晚 3 分钟" in msg5 and "T1" in msg5, msg5)
check("消息声明单独到达不计为同行", "单独到达" in msg5)

# 一人完全无法到达会合站
data5b = {"stations": STATIONS_4, "trips": [T1_MD, T2_AM],
          "transfers": [], "suspensions": []}
r5b = meet(data5b, "A", "B", "D")
check("乙与 M 无连通 → blocked/cannot_meet 指出无法到达会合站",
      r5b["status"] == "blocked"
      and r5b["blocker"]["kind"] == "cannot_meet"
      and "无法到达会合站" in r5b["blocker"]["message"],
      json.dumps(r5b.get("blocker"), ensure_ascii=False))

# 没有任何班次能直达终点
data5c = tiny_net()
data5c["stations"].append({"id": "Z", "name": "无人区"})
r5c = meet(data5c, "A", "B", "Z")
check("终点无班次直达 → no_shared_service",
      r5c["status"] == "blocked"
      and r5c["blocker"]["kind"] == "no_shared_service",
      json.dumps(r5c.get("blocker"), ensure_ascii=False))

# 即使甲可乘 T2 到 M，但无去 D 的车（删 T1），也不能把任何单方路线当同行
data5d = tiny_net()
data5d["trips"] = [T2_AM]
r5d = meet(data5d, "A", "B", "D")
check("无共同班次时即使某方能独自出行仍 blocked",
      r5d["status"] == "blocked")

print("== 6. 起点封站与输入校验 ==")
data6 = json.loads(json.dumps(data4b))
data6["suspensions"].append({"kind": "station", "ref": "A",
                             "start": "00:00", "end": "23:59"})
r6 = meet(data6, "A", "B", "D")
check("甲起点全天封站 → blocked/origin_closed 且标记 person=A",
      r6["status"] == "blocked"
      and r6["blocker"]["kind"] == "origin_closed"
      and r6["blocker"].get("person") == "A",
      json.dumps(r6.get("blocker"), ensure_ascii=False))


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


p6 = Planner(normalize(tiny_net()))
expect_err("共同终点不存在",
           lambda: p6.plan_meeting(
               [{"origin": "A", "earliest": m("08:00")},
                {"origin": "B", "earliest": m("08:00")}], "ZZ"),
           "终点站不存在")
expect_err("某人起点不存在",
           lambda: p6.plan_meeting(
               [{"origin": "ZZ", "earliest": m("08:00")},
                {"origin": "B", "earliest": m("08:00")}], "D"),
           "起点站不存在")
expect_err("只有一人",
           lambda: p6.plan_meeting(
               [{"origin": "A", "earliest": m("08:00")}], "D"),
           "恰好两人")
expect_err("三个人",
           lambda: p6.plan_meeting(
               [{"origin": "A", "earliest": m("08:00")},
                {"origin": "B", "earliest": m("08:00")},
                {"origin": "M", "earliest": m("08:00")}], "D"),
           "恰好两人")
expect_err("缺少起点",
           lambda: p6.plan_meeting(
               [{"origin": "", "earliest": m("08:00")},
                {"origin": "B", "earliest": m("08:00")}], "D"),
           "缺少起点站")

print("== 7. 同班次驶入会合站 & 示例网络 ==")
# 甲乘共同班次 T1 的前半段 A->M，乙步行到 M，两人在 M 会合后同乘 M->D
data7 = {
    "stations": STATIONS_4,
    "trips": [{"id": "T1", "route": "1路", "stops": [
        {"station": "A", "time": "08:05"},
        {"station": "M", "time": "08:20"},
        {"station": "D", "time": "08:40"}]}],
    "transfers": [{"from": "B", "to": "M", "minutes": 15}],
    "suspensions": [],
}
r7 = meet(data7, "A", "B", "D")
mm7 = r7["meeting"]
a7 = mm7["people"][0]
check("甲乘同一班次 T1 驶入会合站 M（前段 A->M，同乘段 M->D 不重复）",
      mm7["meeting_station"] == "M" and mm7["trip_id"] == "T1"
      and [l for l in a7["legs"] if l["type"] == "ride"][0]["to"] == "M"
      and mm7["shared_leg"]["from"] == "M",
      json.dumps(mm7, ensure_ascii=False))

# 内置示例：S2 与 S4 各自 08:00 出发，S4 会合同乘 K2，08:35 到 S6
net = normalize(SAMPLE_DATA)
r7c = Planner(net).plan_meeting(
    [{"origin": "S2", "earliest": m("08:00"), "label": "同行人甲"},
     {"origin": "S4", "earliest": m("08:00"), "label": "同行人乙"}], "S6")
mm = r7c["meeting"]
check("示例：S4 会合同乘 K2 于 08:35 到 S6",
      mm["meeting_station"] == "S4" and mm["trip_id"] == "K2"
      and mm["arrival"] == m("08:35"), json.dumps(mm, ensure_ascii=False))
check("示例：总步行 4 / 总候车 29；甲步行 4；乙候车 25",
      mm["walking_minutes"] == 4 and mm["waiting_minutes"] == 29
      and mm["people"][0]["walking_minutes"] == 4
      and mm["people"][1]["waiting_minutes"] == 25)
check("示例：同乘段只出现一次 S4->S6",
      mm["shared_leg"]["from"] == "S4" and mm["shared_leg"]["to"] == "S6"
      and sum(1 for p in mm["people"]
              for l in p["legs"]
              if l.get("trip_id") == "K2" and l.get("to") == "S6") == 0)

# 两人都从 S1 08:00 出发到 S6 -> S1 会合乘 K2
r7d = Planner(net).plan_meeting(
    [{"origin": "S1", "earliest": m("08:00")},
     {"origin": "S1", "earliest": m("08:00")}], "S6")
check("示例：同起点 S1 会合乘 K2 直达",
      r7d["meeting"]["meeting_station"] == "S1"
      and r7d["meeting"]["trip_id"] == "K2")

# S8 无任何出发班次且无步行连接，与 S1 无法会合到 S6
r7e = Planner(net).plan_meeting(
    [{"origin": "S1", "earliest": m("08:00")},
     {"origin": "S8", "earliest": m("08:00")}], "S6")
check("示例：S8 无法到达任何会合站 → blocked/cannot_meet",
      r7e["status"] == "blocked"
      and r7e["blocker"]["kind"] == "cannot_meet",
      json.dumps(r7e.get("blocker"), ensure_ascii=False))

print(f"\n通过 {passed}，失败 {failed}")
sys.exit(1 if failed else 0)
