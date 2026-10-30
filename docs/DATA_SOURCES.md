# Sumber Open Data untuk Analisa Saham Indonesia (BEI/IDX)

Disusun Oktober 2026. Status setiap sumber bisa berubah — selalu cek syarat penggunaan (ToS) sebelum dipakai untuk keperluan komersial.

## Ringkasan cepat

| # | Sumber | Jenis data | Teknikal | Fundamental | Akses | Dipakai di repo ini |
|---|--------|-----------|:-:|:-:|------|:-:|
| 1 | **Yahoo Finance via `yfinance`** | OHLCV harian/mingguan, dividen, split, rasio, laporan keuangan ringkas | ✅ | ✅ (ringkas) | Gratis, tanpa key, kode `XXXX.JK` | ✅ utama |
| 2 | **Situs resmi IDX (idx.co.id)** | Ringkasan saham harian, profil emiten, laporan keuangan PDF/XLSX/**XBRL** | ✅ | ✅ (resmi) | Gratis, unduh manual / endpoint tidak resmi | ⚙️ opsional |
| 3 | **Dataset XBRL IDX (Hugging Face `Azzindani/IDX_Financial_Statements`)** | Laporan keuangan & laporan tahunan dalam PDF + XBRL | – | ✅ | Gratis | ⚙️ opsional |
| 4 | **Kaggle "EOD Data Indonesia Stock Exchange"** | CSV/JSON end-of-day, termasuk indeks sektoral | ✅ | – | Gratis (akun Kaggle) | ⚙️ opsional |
| 5 | **Sectors API (api.sectors.app)** | Harga, laporan keuangan terstandar, rasio, dividen, indeks | ✅ | ✅ | API key (ada tier gratis) | ⚙️ opsional |
| 6 | **Bank Indonesia – SEKI** | Suku bunga BI, uang beredar, kurs, kredit perbankan | – | ✅ makro | Gratis (XLS) | ⚙️ konteks makro |
| 7 | **BPS Web API (webapi.bps.go.id)** | PDB, inflasi (IHK), neraca dagang, dll. | – | ✅ makro | Gratis, API key | ⚙️ konteks makro |
| 8 | Proyek open-source komunitas (`idxlens`, `IDX-API`, `idx-bei`, `idx-daily`, `fzn0x/idx`) | Scraper/wrapper data resmi IDX | ✅ | ✅ | Gratis | referensi |

## Detail per sumber

### 1. Yahoo Finance (`yfinance`) — sumber utama
- Saham BEI memakai akhiran `.JK` (contoh `BBCA.JK`, `TLKM.JK`). IHSG = `^JKSE`.
- Yang tersedia: harga OHLCV historis (harian, mingguan, bulanan), dividen & split, `info` (PER, PBV, ROE, DER, market cap, margin, dll.), laporan laba rugi / neraca / arus kas tahunan & kuartalan (biasanya 4 tahun/5 kuartal terakhir).
- Kelebihan: gratis, tanpa key, satu library untuk teknikal dan fundamental.
- Kekurangan: tidak resmi; kadang rate-limit; beberapa saham kecil dan indeks sektoral datanya bolong; data fundamental bisa terlambat atau tidak lengkap untuk emiten Indonesia → **validasi silang dengan laporan resmi IDX untuk keputusan penting.**

### 2. Situs resmi IDX
- Laporan keuangan & tahunan setiap emiten tersedia di menu *Perusahaan Tercatat → Laporan Keuangan dan Tahunan* dalam bentuk PDF, XLSX, dan paket XBRL (ZIP). XBRL adalah format paling presisi untuk diolah mesin.
- Ringkasan perdagangan harian (*Ringkasan Saham*) tersedia per hari.
- Belum ada API publik resmi yang terdokumentasi; endpoint JSON di balik situs dipakai banyak proyek komunitas namun bisa berubah/diblokir. Patuhi ToS IDX dan beri jeda request.

### 3. Dataset XBRL IDX di Hugging Face
- Dataset multimodal berisi laporan PDF asli dan instance XBRL dengan taksonomi IDX. Cocok untuk membangun database fundamental historis jangka panjang.

### 4. Kaggle EOD IDX
- Dataset yang diperbarui harian dalam CSV/JSON, dibuat karena yfinance kurang lengkap untuk indeks sektoral dan saham kurang populer. Bagus untuk backtest.

### 5. Sectors API
- API khusus pasar Indonesia (dan SGX) dengan data keuangan terstandar dan rasio antar-emiten yang bisa dibandingkan. Butuh API key; simpan sebagai GitHub Secret bila dipakai.

### 6–7. Data makro: Bank Indonesia (SEKI) & BPS
- **SEKI** terbit bulanan: sektor moneter, keuangan pemerintah, riil, eksternal. Berguna untuk konteks suku bunga dan likuiditas (penting untuk saham bank & properti).
- **BPS Web API**: PDB, inflasi, neraca perdagangan — butuh API key gratis.

### 8. Proyek komunitas (GitHub)
- `lugassawan/idxlens` (Go): ambil & ekstrak data keuangan dari XBRL > XLSX > PDF IDX.
- `NeaByteLab/IDX-API` (Deno): sinkronisasi data resmi IDX ke SQLite.
- `nichsedge/idx-bei`: scraper IDX.
- `odhyp/idx-daily`: otomatisasi ringkasan saham harian.
- `fzn0x/idx`: CLI/MCP harga, fundamental, screening tanpa API key.

## Rekomendasi arsitektur data
1. **Harga (teknikal):** `yfinance` harian, disimpan sebagai CSV per ticker di repo (`data/prices/`). Fallback: Kaggle EOD.
2. **Fundamental:** `yfinance` untuk screening cepat; untuk analisa mendalam, unduh XBRL resmi IDX (atau Sectors API).
3. **Makro:** BI-Rate & inflasi (manual/bulanan) sebagai filter konteks sektor.
