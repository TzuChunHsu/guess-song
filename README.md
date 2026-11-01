# 耳熟能詳 · 猜歌王

聽一小段歌，猜出歌名。收錄 1337 首華語、台語、粵語、西洋、韓語、日語和其他語言的熱門歌曲。

**線上玩：https://tzuchunhsu.github.io/guess-song/**

- 模式：經典十題、生存模式、闖關模式、每日挑戰
- 可調整年代、語言類別、選項數、作答時間和難度
- 音源：Apple iTunes 試聽片段，連不上時自動改用 Deezer

## 檔案

| 路徑 | 內容 |
| --- | --- |
| `index.html` | 遊戲本體（單一檔案，GitHub Pages 直接提供這個檔案） |
| `src/template.html` | 遊戲程式和畫面 |
| `src/bank.txt` | 題庫，一行一首：`歌名(/別名)\|歌手(、合唱)\|年份`，用 `@zh` `@tw` `@yue` `@en` `@kr` `@jp` `@ot` 分類 |
| `src/build.py` | 把題庫、簡繁對照、歌手別名、副歌時間（`src/chorus.js`）放進模板 |
| `tests/` | Playwright 自動測試（模擬 Apple / Deezer 回應，不需要網路） |

## 更新題庫或程式

```bash
cd src
python3 build.py template.html bank.txt ../index.html
```

## 測試

```bash
pip install playwright && playwright install chromium
python3 tests/run_v12.py index.html src/bank.txt   # 完整檢查：按鈕、模式、計分、生存、闖關、每日挑戰
python3 tests/run_rand.py index.html src/bank.txt  # 出題隨機性與歌手分散
python3 tests/run_v6.py index.html src/bank.txt    # Apple / Deezer 連不上時的備援
```
