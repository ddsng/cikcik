# 📈 IDX Stock Analyzer

Sistem analisa **teknikal + fundamental** saham Bursa Efek Indonesia (BEI/IDX) yang berjalan otomatis setiap hari bursa di **GitHub Actions** dan mempublikasikan dashboard ke **GitHub Pages** — gratis, tanpa server.

- **Data:** Yahoo Finance via `yfinance` (kode `.JK`) — lihat [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) untuk sumber open data lain (IDX XBRL, Kaggle, Sectors API, BI, BPS).
- **Metodologi:** [docs/KONSEP_ANALISA.md](docs/KONSEP_ANALISA.md) — skor teknikal (tren, momentum, ADX, posisi, volume), skor fundamental (valuasi, profitabilitas, pertumbuhan, kesehatan, dengan penyesuaian sektor bank), nilai wajar (Graham & PER sektor), dan klasifikasi 4 kuadran.
- **Khas BEI:** stop loss/target dibulatkan ke fraksi harga BEI, lot 100 lembar, filter likuiditas nilai transaksi.

```
config/settings.yaml   ← watchlist & semua ambang skor
src/idxanalyzer/
  data.py              ← YahooSource (live) & DemoSource (sintetis/offline)
  technical.py         ← SMA, EMA, RSI, MACD, Bollinger, ATR, ADX + skor T
  fundamental.py       ← skor F + Graham number + nilai wajar relatif
  pipeline.py          ← orkestrasi, skor gabungan, kuadran, output JSON/CSV
  cli.py               ← perintah `run` dan `show`
web/index.html         ← dashboard statis (disalin ke site/ saat run)
.github/workflows/     ← CI (pytest) & analisa harian + deploy Pages
```

## Jalankan lokal

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m idxanalyzer run --demo           # uji cepat dengan data sintetis
python -m idxanalyzer run                  # data live seluruh watchlist
python -m idxanalyzer run -t BBCA,TLKM     # ticker tertentu
python -m idxanalyzer show BBRI            # rincian satu saham di terminal

python -m http.server -d site 8000         # buka http://localhost:8000
pytest -q                                  # jalankan test
```

## Deploy ke GitHub

1. Buat repo baru di GitHub, lalu push folder ini:
   ```bash
   git init && git add . && git commit -m "init: IDX stock analyzer"
   git branch -M main
   git remote add origin https://github.com/<username>/idx-stock-analyzer.git
   git push -u origin main
   ```
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. **Settings → Actions → General → Workflow permissions: Read and write permissions** (agar snapshot histori bisa di-commit).
4. Tab **Actions → Daily analysis & deploy → Run workflow** untuk run pertama (centang *demo* jika ingin uji coba dulu).
5. Dashboard tersedia di `https://<username>.github.io/idx-stock-analyzer/`. Selanjutnya berjalan otomatis Senin–Jumat pukul 17:15 WIB.

## Output

| File | Isi |
|---|---|
| `site/index.html` | Dashboard: ringkasan kuadran, tabel bisa diurutkan/difilter, detail per saham dengan grafik harga + SMA & RSI |
| `site/data/latest.json` | Hasil lengkap semua saham |
| `site/data/summary.csv` | Ringkasan untuk Excel/Google Sheets |
| `site/data/prices/<KODE>.json` | 250 bar terakhir + indikator untuk grafik |
| `site/data/history/<tanggal>.json` | Snapshot harian (di-commit, bisa untuk evaluasi/backtest sinyal) |

## Kustomisasi

- **Watchlist:** edit `watchlist` di `config/settings.yaml` (sesuaikan dengan LQ45/IDX80 terbaru).
- **Gaya investasi:** ubah `weights` (mis. trader `fundamental: 0.3, technical: 0.7`).
- **Ambang fundamental:** setiap metrik punya `full` (skor penuh), `zero` (skor nol), dan `weight`.
- **Sumber data lain:** buat kelas baru dengan method `prices(ticker, period)` dan `fundamentals(ticker)` seperti `YahooSource`, lalu pilih di `cli.py`.

## Catatan penting

- `yfinance` bukan API resmi; kadang rate-limit atau data fundamental emiten Indonesia tidak lengkap (lihat kolom *coverage*). Validasi angka dengan laporan keuangan resmi di idx.co.id sebelum mengambil keputusan.
- Tidak ada jaminan akurasi. **Bukan rekomendasi investasi.**

Lisensi: MIT.
