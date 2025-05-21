# 🧾 CGPT_README – Strat 001 (EUR/GBP Mean-Reversion)

This file tracks **version metadata and formatting procedures** used by ChatGPT to maintain and display strategy performance and settings tables.

## 📄 Files in this folder

- `version_table.json` – structured JSON of all versions with config + results.
- `performance_matrix.md` – full Markdown table (settings + results).
- `summary_block.txt` – monospace, screenshot-style block used for visual reports.

## 🛠️ How version tables are managed

1. **Add new version** to `version_table.json` under the `versions` list.
   - Include `tag`, signal type, `base_z`, `step_z`, drift, cap, etc.
   - Populate the `results` sub-object: `trades`, `win_rate`, `expect_pips`, etc.

2. When a new version is added:
   - Regenerate `performance_matrix.md` using ChatGPT (or helper script)
   - Update `summary_block.txt` if visual format is needed

3. **If a setting or metric is deprecated or added**:
   - Modify all versions for consistency
   - Re-check column spacing in text blocks

## 📋 Formatting conventions

- Visual blocks are aligned using **fixed-width spacing** (4–8 spaces per column)
- Use em-dashes `—` for “not applicable” or missing fields
- Use `same` for unchanged configs across versions
- Round floats to 2 decimal places unless noted
- Use `±Xσ` notation for Z-triggers, and UTF8 symbols (e.g., `%`, `∞`)

## 🧠 Future Enhancements

- Auto-generate from backtest logs
- Version changelog generator
- Promotion trigger (dev → live_sim)

---
Maintained by: ChatGPT + tradeops @ AX-52
