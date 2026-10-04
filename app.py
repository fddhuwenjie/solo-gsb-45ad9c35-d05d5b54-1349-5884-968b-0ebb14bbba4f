"""公交时刻换乘规划台 —— Flask 后端。"""

from flask import Flask, jsonify, request, send_from_directory

from planner import (
    PREFERENCE_LABELS,
    PlanError,
    SAMPLE_DATA,
    Planner,
    normalize,
    parse_time,
)

app = Flask(__name__, static_folder="static", static_url_path="")


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/meta")
def meta():
    return jsonify({"preferences": [
        {"id": pid, "label": label}
        for pid, label in PREFERENCE_LABELS.items()
    ]})


@app.get("/api/sample")
def sample():
    return jsonify(SAMPLE_DATA)


@app.post("/api/plan")
def plan():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error",
                        "message": "请求体必须是 JSON 对象"}), 400

    query = payload.get("query") or {}
    data = payload.get("data") or {}

    try:
        network = normalize(data)
        origin = str(query.get("origin", "")).strip()
        destination = str(query.get("destination", "")).strip()
        earliest = parse_time(query.get("earliest", "00:00"), "最早出发时刻")
        preference = str(query.get("preference", "fastest")).strip()
        result = Planner(network).plan(origin, destination, earliest,
                                       preference)
    except PlanError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    return jsonify(result)


@app.post("/api/continue")
def continue_trip():
    """途中停运 / 班次调整后的行程续程。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error",
                        "message": "请求体必须是 JSON 对象"}), 400

    original = payload.get("itinerary") or payload.get("original")
    data = payload.get("data") or {}
    cont = payload.get("continue") or {}

    try:
        network = normalize(data)
        completed_index = cont.get("completed_index")
        if isinstance(completed_index, str) and completed_index.strip().isdigit():
            completed_index = int(completed_index.strip())
        current_time = parse_time(cont.get("current_time", cont.get("now")),
                                  "当前时刻")
        destination = cont.get("destination")
        if destination is not None:
            destination = str(destination).strip() or None
        preference = str(cont.get("preference", "fastest")).strip()
        result = Planner(network).continue_trip(
            original, destination, completed_index, current_time, preference)
    except PlanError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    return jsonify(result)


@app.post("/api/meet")
def meet():
    """两人同车会合：各自前段 → 同一会合站同一班次 → 直达共同终点。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error",
                        "message": "请求体必须是 JSON 对象"}), 400

    data = payload.get("data") or {}
    query = payload.get("query")
    if not isinstance(query, dict):
        query = {}

    # 支持 {"query": {"people": [...]}} 与 {"people": [...]} 两种位置
    raw_people = query.get("people", payload.get("people"))
    has_people_list = isinstance(raw_people, list)
    if has_people_list and len(raw_people) != 2:
        return jsonify({"status": "error",
                        "message": "同车会合需要恰好两人的起点与最早出发时刻"}), 400
    destination = query.get("destination") or payload.get("destination")

    def one_person(item, fallback_origin, no):
        if not isinstance(item, dict):
            item = {}
        origin = item.get("origin", fallback_origin)
        earliest = item.get("earliest", "00:00")
        return {
            "origin": str(origin or "").strip(),
            "earliest": earliest,
            "label": str(item.get("label", "")).strip() or None,
            "_no": no,
        }

    people = []
    if has_people_list:
        for k, item in enumerate(raw_people):
            if not isinstance(item, dict):
                return jsonify(
                    {"status": "error",
                     "message": f"第 {k + 1} 人的信息格式不合法"}), 400
            people.append(one_person(item, None, k + 1))
    else:
        # 兼容平铺字段：origin1/origin2（或 origin_a/origin_b）
        o1 = query.get("origin1", query.get("origin_a",
                      payload.get("origin1")))
        o2 = query.get("origin2", query.get("origin_b",
                      payload.get("origin2")))
        e1 = query.get("earliest1", query.get("earliest_a",
                       payload.get("earliest1", "00:00")))
        e2 = query.get("earliest2", query.get("earliest_b",
                       payload.get("earliest2", "00:00")))
        people = [
            {"origin": str(o1 or "").strip(), "earliest": e1,
             "label": None, "_no": 1},
            {"origin": str(o2 or "").strip(), "earliest": e2,
             "label": None, "_no": 2},
        ]
        people[0]["label"] = str(query.get("label1", "") or "").strip() or None
        people[1]["label"] = str(query.get("label2", "") or "").strip() or None

    if not str(destination or "").strip():
        return jsonify({"status": "error",
                        "message": "缺少共同终点站"}), 400
    for person in people:
        if not person["origin"]:
            return jsonify({"status": "error",
                            "message": f"第 {person['_no']} 人缺少起点站"}), 400

    try:
        network = normalize(data)
        parsed_people = []
        for person in people:
            earliest = parse_time(person["earliest"] or "00:00",
                                  f"第 {person['_no']} 人最早出发时刻")
            entry = {"origin": person["origin"], "earliest": earliest}
            if person["label"]:
                entry["label"] = person["label"]
            parsed_people.append(entry)
        result = Planner(network).plan_meeting(
            parsed_people, str(destination).strip())
    except PlanError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
