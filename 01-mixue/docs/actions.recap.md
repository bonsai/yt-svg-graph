# GitHub Actions Recap

更新日: 2026-10-27  
対象: [GitHub Actions](https://github.com/bonsai/yt-svg-graph/actions) / `.github/workflows/build-video.yml`

## 現在の状況

- **最新 Run #17: 成功** — [Run #17](https://github.com/bonsai/yt-svg-graph/actions/runs/40426547890)
- 対象コミット: `ac6d0dce` — `Document local VLM mapping handoff and asset preparation`
- ジョブ `build-mixue` の全ステップが成功。Python セットアップ、依存関係・Chromium の導入、日本語 TTS、PNG素材準備、Artifactアップロードまで完了。
- 直近の Run #15・#16 も成功。Run #13・#14 は失敗しているが、その後の修正コミットで Run #15〜#17 が成功している。
- Run #11・#12 は確認時点で `in_progress` と表示されていた。新しい Run #17 は成功しているため、まず最新結果を基準にする。

## 現在のワークフロー

`.github/workflows/build-video.yml` は `push`（`01-mixue/**` または workflow ファイル変更）と手動実行に対応。

1. Python 3.12、FFmpeg、依存関係、Playwright Chromium を準備
2. `01-mixue/make-tts.py` で日本語TTSを生成
3. PNG経路（`auto` の場合、ストーリーボードPNGがあれば優先）では `build-video.py --source png --prepare-only` を実行
4. PNG経路では動画をレンダリングせず、切り出し素材とマニフェスト等を準備
5. `01-mixue/build/` を `01-mixue-video` Artifact として保存（保持期間14日）

SVG経路を選択した場合は `build-video.py --source svg --fps 1 --duration 120` で動画を生成する設定。

## PNG素材準備の成果物

PNG経路で準備される想定のファイル:

- `build/png-panels/` — 3×3の元画像から切り出した9コマ
- `build/panel-manifest.json` — 元画像・グリッド・座標・サイズ・パネルID等の記録
- `build/panel-map.json` — 現時点ではローカルVLM等が作成する対応表。リポジトリには形式例 `01-mixue/panel-map.example.json` がある
- TTS関連の音声ファイル

## 今回の目的と未実装部分

今回の優先事項は、**ローカルVLMで切り出し素材が正確かどうかを判定すること**。

現状の Actions は素材準備と Artifact 化までで、切り出し精度をVLMで判定するステップはまだ組み込まれていない。したがって、Run #17 の成功は「ワークフローが最後まで完了した」ことを示すものであり、**9コマの切り出し精度や意味的な対応関係が検証済みという意味ではない**。

次に追加する検証の候補:

- [ ] 9コマすべてが出力されたか、画像寸法・座標・ファイル存在を機械的に検証
- [ ] 元画像と切り出し画像をローカルVLMに渡し、境界・欠け・隣接コマの混入を判定
- [ ] 判定結果を `panel-validation.json` に保存（`pass / review / fail`、理由、対象パネル）
- [ ] `fail` があれば動画生成を停止し、検査結果と画像をArtifactで確認可能にする
- [ ] 切り出し精度の検証と、ナレーション場面への意味的な対応付けを別工程にする

## 確認リンク

- [Actions一覧](https://github.com/bonsai/yt-svg-graph/actions)
- [最新成功 Run #17](https://github.com/bonsai/yt-svg-graph/actions/runs/40426547890)
- [Workflow定義](https://github.com/bonsai/yt-svg-graph/blob/main/.github/workflows/build-video.yml)
- [PNG切り出しスクリプト](https://github.com/bonsai/yt-svg-graph/blob/main/01-mixue/png2mov.py)
- [動画ビルドの入口](https://github.com/bonsai/yt-svg-graph/blob/main/01-mixue/build-video.py)
- [VLMマッピング形式例](https://github.com/bonsai/yt-svg-graph/blob/main/01-mixue/panel-map.example.json)

## 注意

このワークフローはビルド成果物を保存するだけで、YouTubeへのアップロードは行わない。Artifactは14日で期限切れになる。
