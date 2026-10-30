# Konsep Analisa Teknikal & Fundamental Saham Indonesia

Dokumen ini menjelaskan *apa* yang dihitung sistem dan *mengapa*. Semua angka ambang (threshold) bisa diubah di `config/settings.yaml` tanpa menyentuh kode.

> ⚠️ Sistem ini alat bantu riset, bukan rekomendasi beli/jual. Keputusan investasi tetap tanggung jawab pengguna.

---

## 1. Alur besar (pipeline)

```
 ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
 │ 1. Universe  │ → │ 2. Ambil data│ → │ 3. Analisa   │ → │ 4. Skor &    │ → │ 5. Publikasi │
 │ watchlist    │   │ harga + fund.│   │ teknikal &   │   │ klasifikasi  │   │ JSON + web   │
 │ (LQ45 dsb.)  │   │ (yfinance)   │   │ fundamental  │   │ kuadran      │   │ GitHub Pages │
 └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

Dijalankan otomatis tiap hari bursa setelah penutupan (± 17:00 WIB) oleh GitHub Actions.

**Filter likuiditas awal:** saham dengan rata-rata nilai transaksi 20 hari < Rp 5 miliar diberi tanda `illiquid` — sinyal teknikal di saham tidak likuid mudah menipu.

---

## 2. Analisa Teknikal (Skor T, 0–100)

Tujuan: menjawab *"apakah waktunya tepat?"* — tren, momentum, dan konfirmasi volume.

### 2.1 Indikator yang dihitung
| Indikator | Parameter | Fungsi |
|---|---|---|
| SMA | 20, 50, 200 | Arah tren jangka pendek/menengah/panjang |
| EMA | 12, 26 | Basis MACD |
| RSI | 14 | Momentum, jenuh beli/jual |
| MACD | 12/26/9 | Perubahan momentum (histogram) |
| Bollinger Bands | 20, 2σ | Posisi harga relatif volatilitas (%B) |
| ATR | 14 | Volatilitas → stop loss & target |
| ADX, +DI, −DI | 14 | Kekuatan & arah tren |
| Volume ratio | MA5 / MA20 volume | Konfirmasi akumulasi/distribusi |
| 52-week high/low | 250 hari | Posisi harga dalam setahun |
| Support/Resistance | low/high 20 hari + pivot klasik | Area keputusan |

### 2.2 Pembobotan skor
| Komponen | Bobot | Aturan |
|---|---:|---|
| **Tren** | 30 | Close > SMA20 (+5), Close > SMA50 (+10), SMA50 > SMA200 (+10), SMA200 naik dibanding 20 hari lalu (+5) |
| **Momentum** | 25 | RSI 50–70 → 15; 40–50 → 10; 30–40 → 6; < 30 → 8 (potensi pantulan); > 70 → 5 (jenuh beli). MACD histogram > 0 → +10 |
| **Kekuatan tren (ADX)** | 15 | ADX ≥ 25 & +DI > −DI → 15; ADX < 20 (sideways) → 7; ADX ≥ 25 & −DI > +DI → 0; lainnya → 10 |
| **Posisi harga** | 15 | %B 0.2–0.8 → 10; < 0.2 → 7; > 0.8 → 4. Harga ≤ 15% di bawah high 52 minggu → +5 |
| **Volume** | 15 | Rasio volume > 1.2 & harga 5 hari naik → 15; rasio > 1.0 → 10; volume naik tapi harga turun (distribusi) → 0; lainnya → 5 |

### 2.3 Label sinyal
| Skor T | Label |
|---|---|
| ≥ 70 | Bullish kuat |
| 55–69 | Bullish |
| 45–54 | Netral |
| 30–44 | Bearish |
| < 30 | Bearish kuat |

### 2.4 Manajemen risiko (khas BEI)
- **Stop loss** = Close − 2 × ATR14; **Target** = Close + 3 × ATR14 (rasio risk:reward 1 : 1.5).
- Harga dibulatkan ke **fraksi harga BEI**: < Rp200 → Rp1; Rp200–<500 → Rp2; Rp500–<2.000 → Rp5; Rp2.000–<5.000 → Rp10; ≥ Rp5.000 → Rp25.
- Ukuran posisi dihitung dalam **lot (1 lot = 100 lembar)**. Contoh: modal risiko Rp1 juta, jarak SL Rp100 → 10.000 lembar = 100 lot.
- Waspadai batas **ARA/ARB** (auto reject) — saat menyentuh ARA/ARB, sinyal teknikal hari itu kurang bermakna.

---

## 3. Analisa Fundamental (Skor F, 0–100)

Tujuan: menjawab *"apakah perusahaannya bagus dan harganya wajar?"*

### 3.1 Rasio & bobot
| Pilar | Bobot | Metrik (bobot) | Nilai penuh bila | Nol bila |
|---|---:|---|---|---|
| **Valuasi** | 30 | PER (12) | ≤ 10× | ≥ 30× atau negatif |
| | | PBV (10) | ≤ 1× | ≥ 5× |
| | | Dividend yield (8) | ≥ 6% | 0% |
| **Profitabilitas** | 30 | ROE (12) | ≥ 20% | ≤ 0% |
| | | ROA (8) | ≥ 10% (bank: ≥ 2%) | ≤ 0% |
| | | Net profit margin (10) | ≥ 20% | ≤ 0% |
| **Pertumbuhan** | 20 | Pertumbuhan pendapatan YoY (10) | ≥ 15% | ≤ −10% |
| | | Pertumbuhan laba YoY (10) | ≥ 20% | ≤ −20% |
| **Kesehatan keuangan** | 20 | Debt-to-Equity (10) | ≤ 0.5× | ≥ 2× (bank: tidak dihitung) |
| | | Current ratio (5) | ≥ 2× | ≤ 0.8× (bank: tidak dihitung) |
| | | Kualitas laba: arus kas operasi / laba bersih (5) | ≥ 1× | ≤ 0 |

- Nilai di antara batas dihitung **linier**.
- **Penyesuaian sektor bank:** DER & current ratio tidak relevan (dana pihak ketiga = utang), jadi dikeluarkan dan bobot dialihkan proporsional; ROA bank memakai ambang lebih rendah.
- **Data kosong:** metrik yang tidak tersedia dikeluarkan dan bobot dinormalisasi ulang. Kolom `coverage` menunjukkan persen bobot yang benar-benar terisi — skor dengan coverage < 60% sebaiknya diperlakukan hati-hati.

### 3.2 Estimasi nilai wajar
1. **Graham Number** = √(22,5 × EPS × BVPS) — konservatif, cocok untuk emiten berlaba stabil.
2. **PER relatif sektor** = EPS × median PER sektor dalam universe.
3. **Nilai wajar gabungan** = rata-rata yang tersedia; **Margin of Safety** = (Nilai wajar − Harga) / Nilai wajar.

---

## 4. Penggabungan: Skor Akhir & Kuadran

**Skor akhir** = 0,6 × F + 0,4 × T (default investor jangka menengah; trader bisa ubah ke 0,3/0,7).

| | **T ≥ 55** (timing baik) | **T < 55** (timing kurang) |
|---|---|---|
| **F ≥ 60** (bisnis bagus) | 🟢 **Kandidat utama** — fundamental kuat & tren mendukung | 🔵 **Value, tunggu momentum** — masuk watchlist, tunggu konfirmasi teknikal |
| **F < 60** | 🟡 **Momentum spekulatif** — trading jangka pendek, SL ketat | 🔴 **Hindari** |

---

## 5. Batasan & pengembangan lanjut
- Data yfinance tidak resmi → validasi angka fundamental dengan laporan keuangan IDX (XBRL) sebelum keputusan.
- Belum ada backtest; langkah lanjut: uji historis skor T (misalnya *forward return* 20 hari per kuantil skor).
- Pengembangan: data makro (BI-Rate) sebagai filter sektor, notifikasi Telegram, analisa *foreign flow* & *broker summary* (butuh sumber data berbayar).
