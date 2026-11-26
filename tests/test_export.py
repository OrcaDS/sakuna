import csv

import duckdb
import pyarrow.parquet as pq
import pytest

from sakuna import export


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "gold.duckdb"
    con = duckdb.connect(str(path))
    dec = "decimal(38,2)"
    con.execute(
        "create table events (event_id varchar, event_year int, start_date date); "
        "insert into events values ('b', 2018, '2018-09-10'), ('a', 2017, '2017-01-07')"
    )
    con.execute(
        "create table reports (event_id varchar, report_date date, report_no int, sha256 varchar)"
    )
    con.execute(
        "create table event_summary (event_id varchar, event_year int, start_date date, "
        f"affected_families {dec}, cost_total {dec})"
    )
    con.execute(
        "create table impacts (event_id varchar, region_code varchar, province_code varchar, "
        f"psgc_code varchar, dswd_name varchar, affected_persons {dec}, cost_total {dec}, "
        "n_unreadable hugeint); "
        "insert into impacts values ('a', '01', '0128', '0128001000', 'Adams', 1017, 1234.5, 0)"
    )
    con.execute(
        "create table impacts_by_report (event_id varchar, report_date date, report_no int, "
        "sha256 varchar, level varchar, region_code varchar, province_code varchar, "
        "psgc_code varchar, dswd_name varchar)"
    )
    con.execute(
        "create table unmatched_places (region_code varchar, province_code varchar, "
        "dswd_name varchar)"
    )
    con.close()
    return path


def test_export_writes_tables_types_and_checksums(db, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data_dictionary.md").write_text("# dict")
    out = tmp_path / "release"

    counts = export.export(db, out, docs_root=tmp_path)

    assert counts["impacts"] == 1 and counts["events"] == 2
    for table in export.TABLES:
        ext = "csv.gz" if table in export.GZIP_CSV else "csv"
        assert (out / f"{table}.{ext}").exists() and (out / f"{table}.parquet").exists()
    with open(out / "impacts.csv", newline="") as f:
        row = next(csv.DictReader(f))
    assert row["affected_persons"] == "1017"  # count: integer, no ".00"
    assert row["cost_total"] == "1234.50"  # cost keeps two decimals
    schema = pq.read_schema(out / "impacts.parquet")
    assert str(schema.field("affected_persons").type) == "int64"
    assert str(schema.field("n_unreadable").type) == "int64"
    with open(out / "events.csv", newline="") as f:
        assert [r["event_id"] for r in csv.DictReader(f)] == ["a", "b"]  # sorted by year
    assert (out / "data_dictionary.md").exists()
    sums = (out / "SHA256SUMS").read_text().splitlines()
    assert any(line.endswith("  impacts.parquet") for line in sums)
    assert not any("SHA256SUMS" in line for line in sums)


def test_export_without_database_fails(tmp_path):
    with pytest.raises(FileNotFoundError, match="dbt build"):
        export.export(tmp_path / "missing.duckdb", tmp_path / "out")


def test_export_writes_report_files_from_manifest(db, tmp_path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "event_url,file_url,label,report_date,status,sha256,local_path\n"
        "e2,f1,Report 1,2026-01-15,ok,abc,e2/abc.pdf\n"
        "e1,f9,Report 9,,failed,,\n",
        encoding="utf-8",
    )
    counts = export.export(db, tmp_path / "out", docs_root=tmp_path, manifest=manifest)

    assert counts["report_files"] == 2
    with open(tmp_path / "out" / "report_files.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["event_url"] for r in rows] == ["e1", "e2"]  # sorted
    assert list(rows[0]) == export.REPORT_FILE_FIELDS  # no local paths published
