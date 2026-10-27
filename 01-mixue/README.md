# 01 · MIXUE

約2分の日本語解説動画。ストーリーボードPNGを分割する経路と、HTML/SVGを描画する経路を分離しています。

## 素材と変換経路
- `MIXUE世界展開ストーリーボード展開.png` — PNG入力。既定では4列×2行に分割し、`tts.json` のシーン順・秒数に合わせてMP4化
- `index.html` — 16:9 HTML/SVGアニメーションの描画元
- `png2mov.py` — PNGストーリーボードをパネル画像に分割して動画化
- `svg2mov.py` — HTML/SVGをPlaywrightでフレーム化して動画化
- `build-video.py` — 内部ルーター。autoはストーリーボードPNGがあればPNG経路、なければSVG経路
- `tts.json` / `make-tts.py` — シーンごとの原稿と仮の日本語TTS
- `divide-img.py` / `mux.py` — SVG経路のフレーム分割と動画・音声結合

## Build
GitHub Actions の **Build video assets** を実行します。source は `auto` / `png` / `svg` から選択できます。成果物はArtifactsからダウンロードできます。YouTubeへ自動アップロードはしません。

PNG経路は既定で4列×2行として切り出します。ストーリーボードのコマ配置が異なる場合は `png2mov.py --cols N --rows N` を指定してください。
数値は報道時点や集計方法に差があるため概数として表示し、価格比較は同一商品同士の比較ではないことを画面内に注記します。
