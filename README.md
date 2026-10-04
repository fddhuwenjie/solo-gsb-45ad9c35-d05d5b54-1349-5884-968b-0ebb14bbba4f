# 公交时刻换乘规划台

基于 **Python Flask + 原生 JavaScript / HTML / CSS** 的公交时刻换乘规划工具。
用户录入站点、带发车时刻的线路班次、站内（站间）步行换乘时间与临时停运区间，
选择起终点、最早出发时刻和「最快 / 少换乘 / 少步行」偏好，系统在**时间依赖图**上
搜索可行行程，并逐段展示班次、等待与换乘细节；另支持**两人同车会合**规划：
两人先到同一会合站赶上同一班次，再同乘该班次直达共同终点。

## 一条命令启动

```bash
docker compose up --build
```

然后浏览器访问：

> **http://localhost:8000**

- 端口：宿主机 **8000** → 容器 **8000**（在 `docker-compose.yml` 的 `ports` 中修改）

停止：`Ctrl+C`（后台模式用 `docker compose down`）。

### 不用 Docker 时

```bash
pip install -r requirements.txt
python app.py
# 同样访问 http://localhost:8000
```

## 使用说明

页面左侧为四块可编辑输入，右侧为规划与结果：

1. **站点**：站点 ID（如 `S1`）与名称。
2. **线路班次**：班次 ID、线路名与逐站经停时刻（每行 `站点ID HH:MM`，时刻须严格递增）。
   每个班次即一趟车，只可在不早于到站时刻的车站上车，沿停站顺序单向乘坐。
3. **步行换乘**：两站间步行分钟数，双向生效；换乘时必须先走完该步行时间才能在邻站乘车。
4. **临时停运区间**：
   - **站点停运**：时间窗内该站不能上、下车，途经班次自动**跳站通过**；
   - **线路整线停运**：时间窗内发车的该线路**整个班次被跳过**；
   - **线路区段停运**：给出线路名、经停顺序中的起止站点与时间窗，
     该线路起止站之间的站段在窗内封锁。班次跨过封锁站段时**不整班取消、
     也不穿越封锁**：乘车段最远生成到封锁段起点站（结果时间线会标注
     「在此终止」），之后由步行或其他班次接续；封锁区段之外的上、下车
     不受影响（例如可在区段终点之后重新上车，甚至步行绕过封锁后
     在更靠后的经停站重新登上同一班次）。

在「⑤ 行程规划」中选择起点、终点、最早出发时刻与偏好后点击 **规划行程**；
在「🤝 两人同车会合」中填写两人起点、各自最早出发时刻与共同终点后点击
**规划同车会合**。
**修改任何输入后可再次点击直接重算**，页面会提示“结果待重算”。
工具栏支持载入示例、清空、导入 / 导出 JSON。

### 行程途中停运 / 班次调整后的续程

规划结果下方的「⑦ 行程续程」面板支持在**行程途中发生停运或班次调整**后接续出行：

1. 先在左侧修改站点、线路班次或临时停运信息（更新后的网络）；
2. 在「最后完成段」下拉中选定已规划时间线上**最后完成的乘车或步行段**
   （候车段不可选），页面会把当前时刻自动填为该段到达时刻，可再向后调；
3. 选择余程偏好后点击 **发起续程**。

续程规则：

- **已走事实不抹掉**：完成段及其之前的候车记录原样沿用，只核对站点与时间
  连续性；即使该班次之后被删除 / 调整、路段被新增停运封锁，完成部分仍按
  原时间线展示（带「已完成」标记）；
- **当前时刻不得早于**最后完成段的到达时刻，完成段到达至当前时刻之间的
  在站等待计入整程候车；
- 自所在站与当前时刻在**更新后的网络**上搜索余程，整程的换乘次数、步行与
  候车分钟统一累计；
- 若步行绕行后重新登上同一班次，只允许乘坐**尚未乘过的站段**，不得回到
  已乘过的站段（例如已乘 A→B，就不能走回 A 再乘 A→B；但可以在 B 重新
  登车继续乘 B→E，或步行绕过后在更靠后的经停站重乘同一班次）；
- **接续无解**时仍完整展示完成部分（含等待至当前时刻），并给出余程的
  首个阻塞原因；未走路段一律不会被标记为完成。

续程结果本身也可再次作为原行程继续续程；重新点击「规划行程」则按当前
网络从头规划。

### 两人同车会合（🤝）

右栏「🤝 两人同车会合」面板分别填写**同行人甲、同行人乙**的起点站与最早出发
时刻，以及两人的**共同终点站**，点击 **规划同车会合**。搜索的行程形态固定为：

1. 两人各走自己的前段（乘车 / 步行，逐段遵守步行换乘时间、站点停运、
   整线停运与区段封锁），先到**同一个会合站**；
2. 两人在会合站赶上**同一班次**；
3. 由该班次**直达**共同终点（同乘段在结果中只展示一次）。

结果区并排展示两人会合前各自的乘车、步行与候车时间线，最后单列同乘段；
等待共同班次发车的那段候车**分别计入两人**的候车统计。

取解字典序（从主到次）：

> **共同到达时刻 → 两人总步行分钟 → 两人总候车分钟 → 共同班次 ID → 会合站 ID**

固定某趟共同班次及其发车时刻后，每个人的前段独立按
「本人总步行 → 本人总候车（含等待该班次）」挑选。因此**较晚到会合站、
但步行更少且仍赶得上同一班次的前段，会胜过本人最快到达的前段**。

找不到双方都赶得上的共同班次时，状态为 `blocked`，原因会具体指出谁无法
到达会合站（含其前段搜索中时间最早的阻塞约束）或谁差多少分钟赶不上车；
**任何一方单独到达终点的路线都不计为同行**。

### 偏好与字典序取解

| 偏好 | 字典序（从主到次） |
|---|---|
| 最快到达 | 到达时刻 → 换乘次数 → 总步行分钟 |
| 最少换乘 | 换乘次数 → 到达时刻 → 总步行分钟 |
| 最少步行 | 总步行分钟 → 到达时刻 → 换乘次数 |

搜索采用多标签（帕累托）时间依赖 Dijkstra：标签在每个站点按所选三元组互相支配剪枝，
三元组完全相同的标签只保留最先产生的一个，因此同分时结果稳定、可复现。
「换乘次数」= 乘坐的班次数 − 1（只坐一趟车即为 0 次换乘）。

### 无解与“首个阻塞约束”

不存在可行行程时，系统返回搜索中遇到的**首个阻塞约束**，按事件发生时刻（最早为先）
排序，消息会具体指出原因，例如：

- 起点站在出发时刻即处于停运时段，无法出发；
- 某班次被线路停运区间覆盖，整班被跳过；
- 班次前方站段被线路区段停运封锁，只能提前下车（消息会指出具体线路、
  受阻站段与最远可下车的车站）；
- 步行到达邻站时该站恰好封站，不能进入换乘；
- 班次到达某站时该站封站，只能跳站通过；
- 最早出发时刻之后已无班次，或起终点之间不存在连通路径。

结果区逐段（`等 / 走 / 乘`）展示时间线：站内候车区间、步行换乘起讫与耗时、
每个班次的线路、班次号、上/下车站点及发车、到达时刻。

## 接口

- `GET /` — 页面
- `GET /api/sample` — 内置示例数据
- `POST /api/plan` — 单人规划
- `POST /api/continue` — 行程途中停运 / 班次调整后的续程
- `POST /api/meet` — 两人同车会合规划

`/api/plan` 请求体：

```json
{
  "query": {"origin": "S1", "destination": "S6",
            "earliest": "08:00", "preference": "fastest"},
  "data": {
    "stations": [{"id": "S1", "name": "东郊枢纽"}],
    "trips": [{"id": "K1", "route": "1路",
               "stops": [{"station": "S1", "time": "08:05"}]}],
    "transfers": [{"from": "S2", "to": "S1", "minutes": 4}],
    "suspensions": [{"kind": "station", "ref": "S7",
                     "start": "00:00", "end": "23:59", "label": "施工封站"},
                    {"kind": "segment", "route": "2路", "from": "S4",
                     "to": "S6", "start": "08:50", "end": "09:10",
                     "label": "区间临时管制"}]
  }
}
```

`preference` 取值：`fastest` / `transfers` / `walking`；
停运 `kind` 取值：
- `station` — 站点停运，`ref` 为站点 ID；
- `route` — 线路整线停运，`ref` 为线路名；
- `segment` — 线路区段停运，字段为 `route`（线路名）、`from` / `to`
  （经停顺序中的起止站点，`from` 必须排在 `to` 之前）、`start` / `end`
  （时间窗）。站段运行区间与时间窗（闭区间）相交即视为封锁。

时间均为当日 `HH:MM`，不含跨夜班次。

成功返回 `{"status": "ok", "itinerary": {...}}`，
无解返回 `{"status": "blocked", "blocker": {"message": "首个阻塞约束…"}}`，
输入不合法返回 HTTP 400 与 `{"status": "error", "message": "..."}`。

### 调用示例

```bash
# 内置示例数据
curl http://localhost:8000/api/sample

# 规划：2 路 S4→S6 站段 08:50–09:10 区段停运，K2b 只能在 S4 前下车
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "query": {"origin": "S1", "destination": "S6",
              "earliest": "08:30", "preference": "fastest"},
    "data": {
      "stations": [{"id": "S1", "name": "东郊枢纽"},
                   {"id": "S4", "name": "人民广场"},
                   {"id": "S5", "name": "大学城"},
                   {"id": "S6", "name": "火车北站"}],
      "trips": [{"id": "K2b", "route": "2路", "stops": [
                   {"station": "S1", "time": "08:38"},
                   {"station": "S4", "time": "08:55"},
                   {"station": "S6", "time": "09:05"}]},
                 {"id": "K4", "route": "4路", "stops": [
                   {"station": "S5", "time": "09:05"},
                   {"station": "S6", "time": "09:12"}]}],
      "transfers": [{"from": "S4", "to": "S5", "minutes": 7}],
      "suspensions": [{"kind": "segment", "route": "2路",
                       "from": "S4", "to": "S6",
                       "start": "08:50", "end": "09:10",
                       "label": "区间临时管制"}]
    }
  }'
```

响应（节选）：K2b 在 S4 截断并标注原因，随后步行至 S5 换乘 K4——

```json
{"status": "ok", "itinerary": {"arrival": 552, "legs": [
  {"type": "ride", "trip_id": "K2b", "route": "2路", "from": "S1", "to": "S4",
   "depart": 518, "arrive": 535, "truncated": true,
   "truncation": "受 2路 区段停运（人民广场→火车北站 08:50–09:10）影响，本次乘车在 人民广场 终止，需步行或换乘其他班次继续。"},
  {"type": "walk", "from": "S4", "to": "S5", "depart": 535, "arrive": 542},
  {"type": "ride", "trip_id": "K4", "route": "4路", "from": "S5", "to": "S6",
   "depart": 545, "arrive": 552}]}}
```

若无解（例如把上例的步行换乘删掉），返回的首个阻塞约束会指向实际线路站段：

```json
{"status": "blocked", "blocker": {"kind": "segment_suspended",
  "route": "2路", "seg_from": "S4", "seg_to": "S6", "trip_id": "K2b",
  "time": 535,
  "message": "班次 K2b（2路）于 08:55 到达 人民广场 后，前方 人民广场→火车北站 站段被线路区段停运封锁（2路 人民广场→火车北站 08:50–09:10，区间临时管制）…"}}
```

### `/api/continue` 续程接口

请求体：

```json
{
  "itinerary": { ... },          // 原 /api/plan（或上次 /api/continue）返回的 itinerary
  "data": { ... },               // 更新后的网络：站点 / 班次 / 步行 / 停运
  "continue": {
    "completed_index": 1,        // 原时间线 legs 中最后完成的乘车/步行段下标（候车段不可选）
    "current_time": "09:00",     // 当前时刻，不得早于该完成段的到达时刻
    "preference": "fastest",     // 余程偏好；可选，缺省 fastest
    "destination": "S6"          // 余程终点；可选，缺省沿用原 itinerary.destination
  }
}
```

返回与 `/api/plan` 同构的 `ok` / `blocked` / `error`，其中 `itinerary` 额外
携带续程信息：

- `continuation: true`、`resume_station` / `resume_time`：续程起点与当前时刻；
- `completed_count`：时间线前段中被锁定为「已完成」的段数（含完成段之后
  至当前时刻的在站等待），这些段带 `"completed": true`；
- `rides` / `transfers` / `walking_minutes` / `waiting_minutes` 为**整程**
  累计（已完成部分 + 余程）；
- 接续无解时状态为 `blocked`：`blocker` 给出余程首个阻塞约束，
  `itinerary` 仍包含完成部分（`arrival` 为 `null`，未走路段不会出现）。

#### 续程调用示例

先规划，拿到原时间线（示例网络中 K2b 因 2路 S4→S6 区段停运，在 S4 截断，
步行到 S5 换 K4）：

```bash
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{"query": {"origin": "S1", "destination": "S6",
                 "earliest": "08:30", "preference": "fastest"},
       "data": <内置示例 /api/sample 的 JSON>}'
```

途中情况变化：人已乘 K2b 到达 S4（legs 下标 1 的乘车段），当前时刻 09:00；
此时 4路 又全线停运。把更新后的停运与**原 itinerary** 一起提交：

```bash
curl -X POST http://localhost:8000/api/continue \
  -H "Content-Type: application/json" \
  -d '{
    "itinerary": {"origin": "S1", "destination": "S6", "earliest": 510,
      "preference": "fastest", "arrival": 552,
      "rides": 2, "transfers": 1, "walking_minutes": 7, "waiting_minutes": 7,
      "legs": [
        {"type": "wait", "station": "S1", "start": 510, "end": 518, "minutes": 8},
        {"type": "ride", "trip_id": "K2b", "route": "2路",
         "from": "S1", "to": "S4", "depart": 518, "arrive": 535,
         "minutes": 17, "truncated": true,
         "truncation": "受 2路 区段停运（人民广场→火车北站 08:50–09:10）影响，本次乘车在 人民广场 终止，需步行或换乘其他班次继续。"},
        {"type": "walk", "from": "S4", "to": "S5",
         "depart": 535, "arrive": 542, "minutes": 7},
        {"type": "wait", "station": "S5", "start": 542, "end": 545, "minutes": 3},
        {"type": "ride", "trip_id": "K4", "route": "4路",
         "from": "S5", "to": "S6", "depart": 545, "arrive": 552, "minutes": 7}]},
    "data": { "...": "在示例数据基础上新增 {\"kind\":\"route\",\"ref\":\"4路\",\"start\":\"00:00\",\"end\":\"23:59\"}" },
    "continue": {"completed_index": 1, "current_time": "09:00",
                 "preference": "fastest"}
  }'
```

返回（节选）：K2b 的 S1→S4 乘车段与 S1 候车段原样保留为已完成，08:55→09:00
在 S4 的等待计入整程候车；余程按更新后的网络重新搜索。若余程无解（例如
4路停运且无其他接续），返回：

```json
{"status": "blocked",
 "blocker": {"kind": "route_suspended", "trip_id": "K4", "time": 545,
             "message": "班次 K4（4路）原定于 09:05 从 大学城 发车，但线路在临时停运区间00:00–23:59内，该班次被跳过。"},
 "itinerary": {"continuation": true, "resume_station": "S4",
               "resume_time": 540, "completed_count": 3, "arrival": null,
               "rides": 1, "transfers": 0,
               "walking_minutes": 0, "waiting_minutes": 13,
               "legs": [
                 {"type": "wait", "station": "S1", "start": 510, "end": 518,
                  "minutes": 8, "completed": true},
                 {"type": "ride", "trip_id": "K2b", "route": "2路",
                  "from": "S1", "to": "S4", "depart": 518, "arrive": 535,
                  "truncated": true, "completed": true},
                 {"type": "wait", "station": "S4", "start": 535, "end": 540,
                  "minutes": 5, "completed": true}]}}
```

常见 400 错误：完成段下标越界 / 指向候车段、当前时刻早于最后到达时刻、
完成前缀站点或时间不连续、完成段引用了更新后网络中不存在的站点。

### `/api/meet` 两人同车会合接口

请求体：

```json
{
  "query": {
    "destination": "S6",
    "people": [
      {"origin": "S2", "earliest": "08:00", "label": "同行人甲"},
      {"origin": "S4", "earliest": "08:00", "label": "同行人乙"}
    ]
  },
  "data": { ... }
}
```

- `destination`：两人的共同终点站；
- `people`：**恰好两人**，各自 `origin`（起点站）与 `earliest`（最早出发
  时刻，缺省 `00:00`），`label` 可选（缺省「同行人甲 / 同行人乙」，会出现在
  时间线与阻塞消息中）。
- 也支持平铺写法（顶层或 `query` 内）：`origin1` / `earliest1`（或
  `origin_a` / `earliest_a`）、`origin2` / `earliest2` 与 `destination`。

成功返回 `{"status": "ok", "meeting": {...}}`，其中 `meeting` 结构：

- `meeting_station` / `trip_id` / `route` / `meeting_departure` /
  `arrival`：会合站、共同班次、共同班次在会合站的发车时刻与共同到达时刻；
- `people[2]`：各自的前段结果，含 `origin` / `earliest` /
  `arrive_meeting`（到会合站时刻）、`rides` / `transfers` /
  `walking_minutes` / `waiting_minutes` 与 `legs` 时间线。各人 `legs`
  一直排到共同班次发车，因此**等待共同班次的候车段在两人时间线中各出现
  一次**；区段封锁导致的前段截断乘车段照常带 `truncated` 标注；
- `shared_leg`：会合后的同乘段（`meet_station → destination`，
  带 `"shared": true`），**只出现一次**，不计入任何一人的前段；
- 顶层 `walking_minutes` / `waiting_minutes` 为**两人合计**，
  `rides` 为两人前段班次数加同乘段一趟。

无解时：

- `{"status": "blocked", "blocker": {"kind": "cannot_meet", ...}}` —
  不存在双方都赶得上的共同班次，消息会列出各自动态（无法到达会合站时
  附带其前段搜索中时间最早的阻塞约束），并明确说明单独到达不计为同行；
- `kind: "no_shared_service"` — 没有任何班次能在当前停运约束下直达
  共同终点；
- `kind: "origin_closed"`（带 `person`: `A`/`B`）— 某人起点站在其最早
  出发时刻即处于停运时段。

输入不合法（人数不为 2、缺少起点 / 终点、站点或时刻非法等）返回 HTTP 400。

#### 同车会合调用示例

以内置示例数据（`GET /api/sample`）为例：甲从 S2（东郊路）、乙从 S4
（人民广场）各自不早于 08:00 出发，共同终点 S6（火车北站）。甲步行 4
分钟到 S1 乘 K2 并于 08:25 到达 S4，乙自 08:00 起在 S4 候车；两人
08:25 在 S4 会合同乘 K2 于 08:35 直达 S6（甲到会合站即发车，不再产生
候车段）：

```bash
curl -X POST http://localhost:8000/api/meet \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "destination": "S6",
      "people": [
        {"origin": "S2", "earliest": "08:00", "label": "同行人甲"},
        {"origin": "S4", "earliest": "08:00", "label": "同行人乙"}
      ]
    },
    "data": <内置示例 /api/sample 的 JSON>
  }'
```

响应（节选）：

```json
{"status": "ok", "meeting": {
  "meeting_station": "S4", "trip_id": "K2", "route": "2路",
  "meeting_departure": 505, "arrival": 515,
  "walking_minutes": 4, "waiting_minutes": 29,
  "people": [
    {"tag": "A", "label": "同行人甲", "origin": "S2", "earliest": 480,
     "arrive_meeting": 505, "rides": 1, "walking_minutes": 4,
     "waiting_minutes": 4, "legs": [
       {"type": "walk", "from": "S2", "to": "S1",
        "depart": 480, "arrive": 484, "minutes": 4},
       {"type": "wait", "station": "S1", "start": 484, "end": 488,
        "minutes": 4},
       {"type": "ride", "trip_id": "K2", "route": "2路",
        "from": "S1", "to": "S4", "depart": 488, "arrive": 505,
        "minutes": 17}]},
    {"tag": "B", "label": "同行人乙", "origin": "S4", "earliest": 480,
     "arrive_meeting": 480, "rides": 0, "walking_minutes": 0,
     "waiting_minutes": 25, "legs": [
       {"type": "wait", "station": "S4", "start": 480, "end": 505,
        "minutes": 25}]}
  ],
  "shared_leg": {"type": "ride", "trip_id": "K2", "route": "2路",
                 "from": "S4", "to": "S6", "depart": 505, "arrive": 515,
                 "minutes": 10, "shared": true}}}
```

其中 `waiting_minutes` 合计 29 = 甲前段候车 4 分钟（S1 等 K2）+ 乙
候车 25 分钟（在 S4 等共同班次）；各人到会合站后等待共同班次的时间分别
计入本人。若双方无法赶上任何同一班次，例如：

```json
{"status": "blocked", "blocker": {
  "kind": "cannot_meet", "trip_id": "K2", "station": "S4", "time": 505,
  "message": "两人无法乘上同一班次同车到达 火车北站：同行人甲最早于 09:12 才到 人民广场，赶不上班次 K2（2路）08:25 的发车（晚 47 分钟）。（任一方单独到达终点的路线均不计为同行。）"}}
```

## 目录结构

```
.
├── app.py               # Flask 路由与静态页面（/api/plan、/api/continue、/api/meet）
├── planner.py           # 时间依赖图、停运判定、多标签搜索、阻塞约束归因、同车会合
├── static/
│   ├── index.html       # 页面结构
│   ├── style.css        # 样式
│   └── app.js           # 原生 JS：录入、重算、单人/续程/同车会合结果渲染
├── test_segment.py      # 区段停运行为验证
├── test_continue.py     # 行程续程行为验证
├── test_meet.py         # 两人同车会合行为验证
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```
