<p align="center">
  <img src="public/assets/logo.jpg" width="128" alt="Mori Logo">
</p>

# All-in-One Downloader API (yt-dlp + Vercel)

API sederhana yang membungkus [yt-dlp](https://github.com/yt-dlp/yt-dlp) dan mengembalikan
**JSON metadata + direct URL**, bukan file media. Cocok dipakai sebagai backend/endpoint
untuk aplikasi lain (bot, web, mobile app, dsb).

Didukung ribuan situs yang didukung yt-dlp (YouTube, TikTok, Instagram, Twitter/X, Facebook,
SoundCloud, dan banyak lagi) — tinggal ganti parameter `url`.

## Struktur folder

```
ytdlp-api/
├── api/
│   └── download.py     # endpoint utama
├── requirements.txt    # dependency python (yt-dlp)
├── vercel.json          # konfigurasi durasi function
└── README.md
```

## Cara deploy ke Vercel

### 1. Lewat Vercel CLI (paling cepat)

```bash
npm i -g vercel
cd ytdlp-api
vercel login
vercel --prod
```

### 2. Lewat GitHub (rekomendasi untuk maintenance jangka panjang)

1. Push folder ini ke repo GitHub baru.
2. Buka [vercel.com/new](https://vercel.com/new), import repo tersebut.
3. Vercel otomatis mendeteksi `requirements.txt` dan `api/*.py` sebagai Python
   Serverless Function — tidak perlu setting tambahan.
4. Klik Deploy.

## Cara pakai

```
GET https://<domain-project-kamu>.vercel.app/api/download?url=<URL_VIDEO>
```

Contoh:

```
GET /api/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Contoh response (disederhanakan):

```json
{
  "success": true,
  "type": "video",
  "title": "Judul video",
  "thumbnail": "https://...",
  "duration": 213,
  "uploader": "Nama channel",
  "formats": [
    {
      "format_id": "137",
      "ext": "mp4",
      "resolution": "1920x1080",
      "filesize": 45213456,
      "vcodec": "avc1.640028",
      "acodec": "none",
      "url": "https://direct-link-video..."
    }
  ],
  "direct_url": "https://direct-link-terbaik..."
}
```

Kalau `url` yang dikirim adalah playlist, response akan berbentuk:

```json
{
  "success": true,
  "type": "playlist",
  "title": "Nama playlist",
  "total_entries": 12,
  "entries": [ { ...sama seperti object video di atas... } ]
}
```

## Endpoint 2: Proxy/Stream media asli

Karena link di `formats[].url` biasanya dilindungi CDN (butuh header
`Referer`/`User-Agent` yang benar dan tidak bisa dibuka langsung di browser),
gunakan endpoint ini supaya backend yang fetch filenya, bukan browser user:

```
GET /api/download?action=stream&url=<url_dari_formats_atau_direct_url>&filename=video.mp4
```

Response-nya **langsung file media** (bukan JSON) — otomatis kepicu download
di browser karena ada header `Content-Disposition: attachment`.

Parameter opsional:
- `filename` — nama file saat di-download (default: `download.<ext>`)
- `referer` — override Referer manual kalau deteksi otomatis meleset

Alur pemakaian yang benar di frontend:

```js
// 1. Ambil metadata dulu
const res = await fetch(`/api/download?url=${encodeURIComponent(videoUrl)}`);
const data = await res.json();

// 2. Untuk tombol "Download", arahkan ke endpoint stream, BUKAN data.direct_url langsung
const downloadLink = `/api/download?action=stream&url=${encodeURIComponent(data.direct_url)}&filename=${encodeURIComponent(data.title)}.mp4`;
// pasang downloadLink ini di <a href="..."> atau window.location
```

## Testing lokal

```bash
pip install -r requirements.txt
vercel dev
```

Lalu akses `http://localhost:3000/api/download?url=...`

## Kenapa cuma 1 file di folder api/?

Runtime Python terbaru di Vercel hanya mengizinkan **satu entrypoint** per
project (dideklarasikan di `pyproject.toml`). Karena itu, endpoint metadata
dan endpoint stream digabung dalam satu file (`api/download.py`) dan
dibedakan lewat parameter `?action=stream`, bukan lewat file terpisah.

## Catatan penting

- **Bukan proxy download** — API ini hanya mengembalikan link langsung (`url`) dari
  CDN sumber (YouTube/TikTok/dst). Client (browser/app kamu) yang mengunduh langsung
  dari link tersebut. Ini yang membuat API tetap ringan dan cepat.
- **Link di `formats[].url` biasanya punya masa berlaku** (expired setelah beberapa
  jam), jadi jangan disimpan permanen — fetch ulang saat dibutuhkan.
- **Beberapa situs (terutama YouTube) kadang minta cookies/verifikasi bot.** Kalau
  suatu saat muncul error semacam itu, cari opsi `cookiefile` di dokumentasi yt-dlp.
- **Rate limit / diblokir IP Vercel**: karena banyak orang pakai IP Vercel yang sama,
  beberapa situs bisa membatasi. Kalau sering gagal, ini penyebab yang paling umum.
- Update `yt-dlp` secara berkala (situs sering ubah struktur), cukup redeploy ulang
  supaya `requirements.txt` narik versi terbaru.
