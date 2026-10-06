import pytest

import lib.redshift as rs


class FakeDataApi:
    def __init__(self, statuses, pages=None):
        self.statuses = list(statuses)
        self.pages = list(pages or [])
        self.executed = None
        self.cancelled = False

    def execute_statement(self, **kwargs):
        self.executed = kwargs
        return {"Id": "q1"}

    def describe_statement(self, Id):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return {"Status": status, "HasResultSet": True, "Error": "boom"}

    def get_statement_result(self, Id, NextToken=None):
        return self.pages.pop(0)

    def cancel_statement(self, Id):
        self.cancelled = True


COLUMNS = [{"name": "branch_name", "typeName": "varchar"}, {"name": "revenue", "typeName": "numeric"},
           {"name": "order_count", "typeName": "int8"}, {"name": "is_weekend", "typeName": "bool"}]


def test_run_query_pages_and_converts(monkeypatch):
    fake = FakeDataApi(["STARTED", "FINISHED"], pages=[
        {"ColumnMetadata": COLUMNS, "Records": [[{"stringValue": "Branch Central Plaza"}, {"stringValue": "1234.50"},
                                                 {"longValue": 10}, {"booleanValue": True}]], "NextToken": "t"},
        {"ColumnMetadata": COLUMNS, "Records": [[{"stringValue": "Branch Airport"}, {"isNull": True},
                                                 {"longValue": 0}, {"booleanValue": False}]]},
    ])
    monkeypatch.setattr(rs, "_client", fake)
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)

    rows = rs.run_query("SELECT 1 WHERE branch_id = :branch_id", {"branch_id": 12})

    assert fake.executed["Parameters"] == [{"name": "branch_id", "value": "12"}]
    assert fake.executed["WorkgroupName"] == "test"
    assert rows == [
        {"branch_name": "Branch Central Plaza", "revenue": 1234.5, "order_count": 10, "is_weekend": True},
        {"branch_name": "Branch Airport", "revenue": None, "order_count": 0, "is_weekend": False},
    ]


def test_failed_query_hides_details(monkeypatch):
    monkeypatch.setattr(rs, "_client", FakeDataApi(["FAILED"]))
    with pytest.raises(rs.QueryError) as e:
        rs.run_query("SELECT 1")
    assert "boom" not in str(e.value)


def test_slow_query_cancelled(monkeypatch):
    fake = FakeDataApi(["STARTED"])
    monkeypatch.setattr(rs, "_client", fake)
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)
    monkeypatch.setenv("REDSHIFT_MAX_WAIT_SECONDS", "0")
    with pytest.raises(rs.QueryError):
        rs.run_query("SELECT 1")
    assert fake.cancelled


class FlakyDataApi(FakeDataApi):
    """Each execute_statement gets the next outcome: an error message, or None for success."""

    def __init__(self, outcomes):
        super().__init__(["FINISHED"], pages=[{"ColumnMetadata": COLUMNS[:1],
                                                "Records": [[{"stringValue": "Branch Central Plaza"}]]}])
        self.outcomes = list(outcomes)
        self.runs = 0

    def execute_statement(self, **kwargs):
        self.runs += 1
        self.current = self.outcomes.pop(0)
        return {"Id": f"q{self.runs}"}

    def describe_statement(self, Id):
        if self.current is None:
            return {"Status": "FINISHED", "HasResultSet": True}
        return {"Status": "FAILED", "Error": self.current}


INTERNAL = "Internal error encountered when processing query."


@pytest.mark.parametrize("outcomes, runs, ok", [
    ([INTERNAL, None], 2, True),          # idle Serverless hiccup: retried once, then works
    ([INTERNAL, INTERNAL], 2, False),     # still failing: give up after one retry
    (["syntax error at or near x", None], 1, False),  # a real query error is not retried
])
def test_retries_internal_error_once(monkeypatch, outcomes, runs, ok):
    fake = FlakyDataApi(outcomes)
    monkeypatch.setattr(rs, "_client", fake)
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)
    if ok:
        assert rs.run_query("SELECT 1") == [{"branch_name": "Branch Central Plaza"}]
    else:
        with pytest.raises(rs.QueryError, match="query failed"):
            rs.run_query("SELECT 1")
    assert fake.runs == runs
