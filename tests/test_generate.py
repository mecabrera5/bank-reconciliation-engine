import csv
from pathlib import Path

from src.synth import generate as g

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ["cres" + "io", "guaya" + "quil", "od" + "oo", "ie" + "ss", "s" + "ri"]


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cents(s):
    neg = s.startswith("-")
    a, b = s.lstrip("-").split(".")
    v = int(a) * 100 + int(b)
    return -v if neg else v


def make(tmp_path, seed=42, name="o"):
    out = tmp_path / name
    g.generate(seed, 3, out)
    return out


def test_determinism(tmp_path):
    a, b, c = make(tmp_path, 42, "a"), make(tmp_path, 42, "b"), make(tmp_path, 7, "c")
    for f in ["bank_statement.csv", "ledger.csv", "ground_truth.csv"]:
        assert (a / f).read_bytes() == (b / f).read_bytes()
    assert (a / "ledger.csv").read_bytes() != (c / "ledger.csv").read_bytes()


def test_all_case_types_present(tmp_path):
    truth = rows(make(tmp_path) / "ground_truth.csv")
    assert {t["case_type"] for t in truth} == set(g.CASE_TYPES)


def test_volume(tmp_path):
    n = len(rows(make(tmp_path) / "ledger.csv"))
    assert 250 <= n <= 350


def test_batch_sums_exact(tmp_path):
    out = make(tmp_path)
    led = {r["ledger_id"]: cents(r["amount"]) for r in rows(out / "ledger.csv")}
    bank = {r["bank_id"]: cents(r["amount"]) for r in rows(out / "bank_statement.csv")}
    batches = [t for t in rows(out / "ground_truth.csv") if t["case_type"] == "batch_n_to_1"]
    assert batches
    for t in batches:
        ids = t["ledger_ids"].split("|")
        assert 2 <= len(ids) <= 6 and len(t["bank_ids"].split("|")) == 1
        assert sum(led[i] for i in ids) == bank[t["bank_ids"]]


def test_split_sums_exact(tmp_path):
    out = make(tmp_path)
    led = {r["ledger_id"]: cents(r["amount"]) for r in rows(out / "ledger.csv")}
    bank = {r["bank_id"]: cents(r["amount"]) for r in rows(out / "bank_statement.csv")}
    splits = [t for t in rows(out / "ground_truth.csv") if t["case_type"] == "split_1_to_n"]
    assert splits
    for t in splits:
        ids = t["bank_ids"].split("|")
        assert 2 <= len(ids) <= 3
        assert sum(bank[i] for i in ids) == led[t["ledger_ids"]]


def test_balance_consistent(tmp_path):
    bank = rows(make(tmp_path) / "bank_statement.csv")
    bal = g.OPENING_BALANCE_CENTS
    for r in bank:
        bal += cents(r["amount"])
        assert cents(r["balance"]) == bal


def test_every_id_in_ground_truth_once(tmp_path):
    out = make(tmp_path)
    truth = rows(out / "ground_truth.csv")
    lids = [i for t in truth for i in t["ledger_ids"].split("|") if i]
    bids = [i for t in truth for i in t["bank_ids"].split("|") if i]
    assert sorted(lids) == sorted(r["ledger_id"] for r in rows(out / "ledger.csv"))
    assert sorted(bids) == sorted(r["bank_id"] for r in rows(out / "bank_statement.csv"))


def test_no_forbidden_text(tmp_path):
    out = make(tmp_path)
    files = list(out.glob("*.csv")) + list((ROOT / "src").rglob("*.py")) + [ROOT / "README.md"]
    for f in files:
        text = f.read_text(encoding="utf-8").lower()
        for w in FORBIDDEN:
            assert w not in text, f"{w} in {f}"
