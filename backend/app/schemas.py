from datetime import date, time
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Name = Annotated[str, Field(min_length=1, max_length=100)]
Id = Annotated[str, Field(min_length=36, max_length=36)]
Clock = Annotated[time, Field()]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    login_id: Name
    password: Annotated[str, Field(min_length=1, max_length=200)]


class Setup(Input):
    token: Annotated[str, Field(min_length=20, max_length=200)]
    password: Annotated[str, Field(min_length=12, max_length=200)]


class Password(Input):
    current_password: str
    password: Annotated[str, Field(min_length=12, max_length=200)]


class Version(Input):
    expected_version: int = Field(ge=1)


class Editable(Input):
    expected_version: int | None = Field(default=None, ge=1)


class CompanyInput(Editable):
    name: Name
    contact: str = Field(default="", max_length=200)


class OwnerInput(Input):
    company_id: Id
    name: Name
    login_id: Name


class BranchInput(Editable):
    name: Name
    address: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=50)
    active: bool = True


class WorkingInput(Editable):
    start: time = time(9)
    end: time = time(18)
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], max_length=7)

    @model_validator(mode="after")
    def check_hours(self):
        if self.start >= self.end or self.start.second or self.end.second:
            raise ValueError("開始・終了時刻を分単位で指定してください")
        if any(d < 0 or d > 6 for d in self.weekdays) or len(set(self.weekdays)) != len(
            self.weekdays
        ):
            raise ValueError("曜日が不正です")
        return self


class StaffInput(WorkingInput):
    name: Name
    job: Literal["ケアマネジャー", "ヘルパー", "兼務", "未設定"] = "ヘルパー"
    branch_ids: list[Id] = Field(min_length=1, max_length=100)
    service_ids: list[Id] = Field(default_factory=list, max_length=100)
    qualifications: list[Name] = Field(default_factory=list, max_length=100)
    break_start: time | None = None
    break_end: time | None = None
    max_visits: int = Field(default=8, ge=0, le=100)
    active: bool = True

    @model_validator(mode="after")
    def check_break(self):
        if (self.break_start is None) != (self.break_end is None):
            raise ValueError("休憩の開始・終了を両方指定してください")
        if self.break_start is not None and not (
            self.start <= self.break_start < self.break_end <= self.end
        ):
            raise ValueError("休憩時間が勤務枠外です")
        return self


class ServiceInput(Editable):
    name: Name
    duration: int = Field(default=60, ge=5, le=720)
    people: int = Field(default=1, ge=1, le=20)
    jobs: list[Name] = Field(
        default_factory=lambda: ["ヘルパー"], min_length=1, max_length=10
    )
    qualifications: list[Name] = Field(default_factory=list, max_length=100)
    active: bool = True


class ClientInput(WorkingInput):
    name: Name
    label: Name
    branch_ids: list[Id] = Field(min_length=1, max_length=100)
    address: str = Field(default="", max_length=300)
    building: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=50)
    guide: str = Field(default="", max_length=2000)
    private_note: str = Field(default="", max_length=2000)
    active: bool = True


class Coordinates(Version):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class VisitInput(Editable):
    branch_id: Id
    client_id: Id
    service_id: Id
    date: date
    start: time
    duration: int = Field(ge=5, le=720)
    people: int = Field(default=1, ge=1, le=20)
    staff_ids: list[Id] = Field(default_factory=list, max_length=20)
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def check(self):
        if (
            self.start.hour * 60 + self.start.minute + self.duration > 1440
            or self.start.second
        ):
            raise ValueError("日をまたぐ訪問は登録できません")
        if len(self.staff_ids) != len(set(self.staff_ids)):
            raise ValueError("担当者が重複しています")
        return self


class Position(Version):
    target_date: date
    target_start: time | None = None
    source_staff_id: str = ""
    target_staff_id: str = ""


class MemberInput(Input):
    staff_id: Id
    login_id: Name


class OwnerProfileLink(Version):
    staff_id: Id


class MemberStatus(Input):
    active: bool


class RequestDay(Input):
    date: date
    kind: Literal["available", "unavailable", "prefer_off"]
    start: time = time(9)
    end: time = time(18)
    note: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def check(self):
        if self.start >= self.end:
            raise ValueError("終了は開始より後にしてください")
        return self


class RequestInput(Editable):
    days: list[RequestDay] = Field(max_length=31)


class WindowInput(Input):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    deadline: date


class ReturnInput(Version):
    reason: str = Field(min_length=1, max_length=300)


class PayInput(Input):
    effective_from: date
    employment: Name
    basis: Literal["unset", "hourly", "monthly"]
    amount: int = Field(ge=0, le=100000000)


class DutyInput(Version):
    date: date
    start: time
    end: time
    off: bool = False
    break_start: time | None = None
    break_end: time | None = None
