# Synthetic bank reconciliation data

Reproducible generator of a fictitious bank statement and general ledger, plus a
ground-truth file saying which ledger entries match which bank movements. It is
meant for testing a reconciliation engine.

**All data is synthetic.** Company "Northwind Services S.A.", bank "Banco Andino
Demo" and account `DEMO-0000-1234` are invented. Currency: USD.

## Run

Recommended (uv):

```
uv venv
uv pip install -r requirements.txt
uv run python -m src.synth.generate --seed 42 --months 3 --out data/
uv run python -m pytest
```

Alternative (standard venv):

```
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate      # Linux/macOS
pip install -r requirements.txt
python -m src.synth.generate --seed 42 --months 3 --out data/
python -m pytest
```

Outputs in `data/`: `bank_statement.csv`, `ledger.csv`, `ground_truth.csv`.
The same seed always produces byte-identical files.

## Match cases

`exact`, `date_offset`, `batch_n_to_1`, `split_1_to_n`, `bank_fee_deducted`,
`ambiguous_amount`, `bank_only`, `ledger_only`.
