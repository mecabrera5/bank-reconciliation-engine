"""Synthetic bank statement / ledger generator with ground truth.

All data is fictitious. Amounts are handled as integer cents internally.
"""
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

COMPANY = "Northwind Services S.A."
BANK = "Banco Andino Demo"
ACCOUNT = "DEMO-0000-1234"
START_DATE = date(2025, 1, 1)
OPENING_BALANCE_CENTS = 5_000_000  # 50,000.00 USD

CASE_TYPES = [
    "exact",
    "date_offset",
    "batch_n_to_1",
    "split_1_to_n",
    "bank_fee_deducted",
    "ambiguous_amount",
    "bank_only",
    "ledger_only",
]

SUPPLIERS = ["Acme Supplies", "Globex Parts", "Initech Goods", "Umbrella Trading",
             "Stark Logistics", "Wayne Materials"]
CUSTOMERS = ["Contoso Ltd", "Fabrikam Inc", "Tailspin Co", "Wingtip Corp", "Adventure Works"]
DEBIT_CATS = ["utilities", "payroll", "rent", "tax", "supplier"]


def fmt(cents):
    sign = "-" if cents < 0 else ""
    c = abs(cents)
    return f"{sign}{c // 100}.{c % 100:02d}"


class Gen:
    def __init__(self, seed, months):
        self.r = random.Random(seed)
        self.span = max(1, months * 30 - 4)
        self.groups = []

    def day(self):
        return START_DATE + timedelta(days=self.r.randrange(self.span))

    def add(self, case, ledger, bank):
        self.groups.append({"case": case, "ledger": ledger, "bank": bank})

    def entry(self):
        """Random (category, reference, signed cents) for a ledger entry."""
        r = self.r
        if r.random() < 0.3:
            return ("customer_payment", f"INV-{r.randrange(1000, 9999)} {r.choice(CUSTOMERS)}",
                    r.randrange(10_000, 400_000))
        cat = r.choice(DEBIT_CATS)
        who = r.choice(SUPPLIERS) if cat == "supplier" else cat.title()
        return (cat, f"{who} {r.randrange(1000, 9999)}", -r.randrange(5_000, 300_000))

    def build(self):
        r = self.r
        for _ in range(120):  # exact
            d = self.day()
            cat, ref, amt = self.entry()
            self.add("exact", [(d, ref, cat, amt)], [(d, ref, amt)])
        for _ in range(60):  # date offset
            d = self.day()
            cat, ref, amt = self.entry()
            self.add("date_offset", [(d, ref, cat, amt)],
                     [(d + timedelta(days=r.randint(1, 3)), ref, amt)])
        for _ in range(15):  # N:1 batch
            d = self.day()
            n = r.randint(2, 6)
            led = []
            for _i in range(n):
                led.append((d - timedelta(days=r.randint(0, 2)),
                            f"Payroll batch item {r.randrange(1000, 9999)}",
                            "payroll", -r.randrange(20_000, 150_000)))
            total = sum(x[3] for x in led)
            self.add("batch_n_to_1", led, [(d, "BATCH PAYMENT", total)])
        for _ in range(12):  # 1:N split
            d = self.day()
            total = -r.randrange(60_000, 600_000)
            parts = r.randint(2, 3)
            cuts = sorted(r.sample(range(1, abs(total)), parts - 1))
            pieces = [b - a for a, b in zip([0] + cuts, cuts + [abs(total)])]
            bank = [(d + timedelta(days=i * r.randint(1, 2)), f"Installment {i + 1}/{parts}", -p)
                    for i, p in enumerate(pieces)]
            self.add("split_1_to_n",
                     [(d, f"Supplier invoice {r.randrange(1000, 9999)}", "supplier", total)], bank)
        for _ in range(25):  # fee deducted from incoming payment
            d = self.day()
            amt = r.randrange(20_000, 500_000)
            fee = max(1, round(amt * 25 / 10_000)) if r.random() < 0.5 else 150
            ref = f"INV-{r.randrange(1000, 9999)} {r.choice(CUSTOMERS)}"
            self.add("bank_fee_deducted", [(d, ref, "customer_payment", amt)], [(d, ref, amt - fee)])
        for _ in range(8):  # ambiguous: same amount, different suppliers
            amt = -r.randrange(10_000, 200_000)
            for s in r.sample(SUPPLIERS, 3):
                d = self.day()
                ref = f"{s} {r.randrange(1000, 9999)}"
                self.add("ambiguous_amount", [(d, ref, "supplier", amt)], [(d, ref, amt)])
        for _ in range(10):  # bank only
            d = self.day()
            self.add("bank_only", [],
                     [(d, "Monthly account fee", -r.choice([450, 500, 1200, 1500]))])
        for _ in range(10):  # ledger only (uncashed cheque)
            d = self.day()
            self.add("ledger_only",
                     [(d, f"Cheque {r.randrange(1000, 9999)} uncashed", "supplier",
                       -r.randrange(10_000, 250_000))], [])
        return self.finish()

    def finish(self):
        led, bank = [], []
        for gi, g in enumerate(self.groups):
            for pi, e in enumerate(g["ledger"]):
                led.append((e[0], e[1], gi, pi, e))
            for pi, e in enumerate(g["bank"]):
                bank.append((e[0], e[1], gi, pi, e))
        led.sort(key=lambda x: x[:4])
        bank.sort(key=lambda x: x[:4])
        lrows, brows = [], []
        lid, bid = {}, {}
        for i, (_, _, gi, pi, e) in enumerate(led, 1):
            lid[(gi, pi)] = f"L{i:04d}"
            lrows.append([lid[(gi, pi)], e[0].isoformat(), e[1], e[2], fmt(e[3])])
        bal = OPENING_BALANCE_CENTS
        for i, (_, _, gi, pi, e) in enumerate(bank, 1):
            bid[(gi, pi)] = f"B{i:04d}"
            bal += e[2]
            brows.append([bid[(gi, pi)], e[0].isoformat(), e[1], fmt(e[2]), fmt(bal)])
        truth = []
        for gi, g in enumerate(self.groups):
            truth.append([
                f"M{gi + 1:04d}",
                "|".join(lid[(gi, p)] for p in range(len(g["ledger"]))),
                "|".join(bid[(gi, p)] for p in range(len(g["bank"]))),
                g["case"],
            ])
        return brows, lrows, truth


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def generate(seed, months, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    bank, ledger, truth = Gen(seed, months).build()
    write_csv(out / "bank_statement.csv", ["bank_id", "date", "description", "amount", "balance"], bank)
    write_csv(out / "ledger.csv", ["ledger_id", "date", "reference", "category", "amount"], ledger)
    write_csv(out / "ground_truth.csv", ["match_id", "ledger_ids", "bank_ids", "case_type"], truth)
    return len(bank), len(ledger), len(truth)


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate synthetic bank/ledger data (all fictitious).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--months", type=int, default=3)
    p.add_argument("--out", default="data/")
    a = p.parse_args(argv)
    nb, nl, nt = generate(a.seed, a.months, a.out)
    print(f"bank={nb} ledger={nl} ground_truth={nt} -> {a.out}")


if __name__ == "__main__":
    main()
