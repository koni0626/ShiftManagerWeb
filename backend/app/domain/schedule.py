from datetime import date


def minutes(value):
    return int(str(value)[:2]) * 60 + int(str(value)[3:5])


def overlap(a, b, c, d):
    return a < d and c < b


def issues(data):
    result = []
    visits = [v for v in data["visits"] if v["status"] != "cancelled"]
    staff = {x["id"]: x for x in data["staff"]}
    clients = {x["id"]: x for x in data["clients"]}
    services = {x["id"]: x for x in data["services"]}

    def add(ids, message, level="error"):
        result.append({"visit_ids": ids, "message": message, "level": level})

    for v in visits:
        ids = [v["id"]]
        c, service = clients[v["client_id"]], services[v["service_id"]]
        day, start, end = (
            date.fromisoformat(v["date"]),
            minutes(v["start"]),
            minutes(v["start"]) + v["duration"],
        )
        if not c["active"] or not service["active"]:
            add(ids, f"{c['label']}：利用者または業務が無効です")
        if len(v["staff_ids"]) < v["people"]:
            add(
                ids,
                f"{c['label']}：担当者が{v['people'] - len(v['staff_ids'])}人不足しています",
            )
        if (
            day.weekday() not in c["weekdays"]
            or start < minutes(c["start"])
            or end > minutes(c["end"])
        ):
            add(ids, f"{c['label']}：訪問可能な曜日・時間外です")
        for sid in v["staff_ids"]:
            p = staff[sid]
            if (
                not p["active"]
                or service["id"] not in p["service_ids"]
                or (p["job"] != "兼務" and p["job"] not in service["jobs"])
                or not set(service["qualifications"]).issubset(p["qualifications"])
            ):
                add(ids, f"{p['name']}：職種・業務・資格の条件を確認してください")
            belongs = any(
                x["staff_id"] == sid
                and x["branch_id"] == v["branch_id"]
                and x["valid_from"] <= v["date"]
                and (not x["valid_until"] or x["valid_until"] >= v["date"])
                for x in data["memberships"]
            )
            if not belongs:
                add(ids, f"{p['name']}：訪問日の営業所に所属していません")
            duty = next(
                (
                    x
                    for x in data["duties"]
                    if x["staff_id"] == sid and x["date"] == v["date"]
                ),
                {**p, "off": day.weekday() not in p["weekdays"]},
            )
            if (
                duty["off"]
                or start < minutes(duty["start"])
                or end > minutes(duty["end"])
            ):
                add(ids, f"{p['name']}：勤務時間外です")
            if duty["break_start"] and overlap(
                start, end, minutes(duty["break_start"]), minutes(duty["break_end"])
            ):
                add(ids, f"{p['name']}：休憩と重複しています")
            submission = next(
                (
                    x
                    for x in data["submissions"]
                    if x["staff_id"] == sid
                    and x["month"] == v["date"][:7]
                    and x["status"] == "submitted"
                ),
                None,
            )
            request = (
                next((x for x in submission["days"] if x["date"] == v["date"]), None)
                if submission
                else None
            )
            if request and request["kind"] == "unavailable":
                add(ids, f"{p['name']}：勤務不可の日です")
            elif request and (
                request["kind"] == "prefer_off"
                or start < minutes(request["start"])
                or end > minutes(request["end"])
            ):
                add(ids, f"{p['name']}：勤務希望と異なります", "warning")
            elif not submission:
                add(ids, f"{p['name']}：勤務希望が未提出です", "warning")

    for i, a in enumerate(visits):
        for b in visits[i + 1 :]:
            if a["date"] != b["date"]:
                continue
            shared = set(a["staff_ids"]) & set(b["staff_ids"])
            if overlap(
                minutes(a["start"]),
                minutes(a["start"]) + a["duration"],
                minutes(b["start"]),
                minutes(b["start"]) + b["duration"],
            ) and (shared or a["client_id"] == b["client_id"]):
                add([a["id"], b["id"]], "同じ担当者または利用者の訪問が重複しています")
    for sid, p in staff.items():
        assigned = [v for v in visits if sid in v["staff_ids"]]
        for day in set(v["date"] for v in assigned):
            route = sorted(
                [v for v in assigned if v["date"] == day], key=lambda x: x["start"]
            )
            if p["max_visits"] and len(route) > p["max_visits"]:
                add(
                    [v["id"] for v in route],
                    f"{p['name']}：1日の訪問件数が上限を超えています",
                )
            duty = next(
                (
                    x
                    for x in data["duties"]
                    if x["staff_id"] == sid and x["date"] == day
                ),
                p,
            )
            for a, b in zip(route, route[1:]):
                if a["client_id"] == b["client_id"]:
                    continue
                finish, begin = minutes(a["start"]) + a["duration"], minutes(b["start"])
                if begin < finish:
                    continue
                gap = begin - finish
                if duty["break_start"]:
                    bs, be = minutes(duty["break_start"]), minutes(duty["break_end"])
                    if overlap(finish, begin, bs, be):
                        gap = max(0, bs - finish, begin - be)
                if gap < data["scope"]["travel_minutes"]:
                    add(
                        [a["id"], b["id"]],
                        f"{p['name']}：移動時間{data['scope']['travel_minutes']}分を確保できません",
                    )
    return result
