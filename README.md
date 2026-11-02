# 耳熟能詳 · 猜歌王

聽一小段歌，猜出歌名。收錄 1369 首華語、台語、粵語、西洋、韓語、日語和其他語言的熱門歌曲，可以一個人玩，也能開房間跟朋友連線對戰。

**線上玩：https://tzuchunhsu.github.io/guess-song/**

## 模式

| 模式 | 玩法 |
| --- | --- |
| 經典十題 | 10 首歌，拚速度、拚連擊 |
| 生存模式 | 3 條命，答錯扣一條；越往後片段越短 |
| 每日挑戰 | 每天所有人同一組 5 首，第一次的成績可以上**今日排行榜** |
| 闖關模式 | 10 關，每關分數達標才能進下一關 |
| 好友對戰 | 開房間，朋友用房號、房間名稱或邀請連結加入，大家同時聽同一首搶答 |

## 好友對戰規則

規則參考 Kahoot 的速度計分和連對加分，以及音樂猜歌遊戲常見的「最快答對」獎勵：

- 房主開房（可以取房間名稱），朋友輸入**暱稱**加上 4 碼房號或房間名稱加入；暱稱重複會自動加編號。
- 房主在房間裡就能調整所有設定，跟單人模式一樣：題目類別、年代範圍、隨機片段或只出副歌、難度、選項數量（4／6／9）、時間限制（10／15／20／30 秒），再加上題數（5／10／15／20 首）；朋友那邊會同步看到設定摘要。
- 倒數 3 秒後，所有人**同時**播同一段，每首只能選一次；選完先不揭曉，等這首結束才一起公布答案和分數（旁邊的人偷看不到）。
- 答對 **500–1000 分**，越快越多；「聽長一點」分數打折（×0.6、×0.35）。
- **連續答對**：第 2 首起每首 +100，最多 +300。
- 每首**最快答對**的人 +200。
- **最後一首分數加倍**。
- 同分時答對首數多的人贏，再同分比答對花的總時間。

| 難度 | 片段 | 干擾選項 | 答錯 |
| --- | --- | --- | --- |
| 輕鬆 | 5 秒 | 沒有同歌手，一半是同性別歌手 | 0 分 |
| 普通 | 3 秒 | 2 首同歌手，其他全是同性別歌手 | 0 分 |
| 地獄 | 1.5 秒 | 一半同歌手，其他是同性別、同年代 | 倒扣 200 |

選項數量和時間限制另外選；單人模式的難度用同一套干擾選項規則。歌手只有一兩首歌時，不夠的部分改用同性別歌手補上。

不同版本也能一起玩：每一題都帶著自己的歌名和歌手，房主和朋友就算開的是不同時間的頁面（手機快取的舊頁面、Netlify 的舊版），題目照樣對得上；只有用很舊的版本開的房間會請房主重新整理。首頁最下面顯示目前的版本時間。

順暢度：房主在大廳等人時就先找好、確認好前三首歌，按開始馬上倒數；遊戲中房主一直保持三首歌寫在前面，朋友的手機也先把這幾首載入。只出副歌時，大家拿到的是房主找到副歌的那一個試聽檔，片段完全相同。

不卡關的做法：
- 房主同時找三首歌（以前一次一首），只出副歌時一首歌最多試兩個試聽檔，找不到副歌就換下一首，不在同一首上耗時間。
- 每首歌在出題前就先確認試聽能播；播不出來的歌會被標記，三天內不再出現。
- 朋友的手機如果載不出某一首（還沒開始播之前），會自動回報，房主馬上換一首給所有人，大家聽到的還是同一首。同一個人最多換三次，之後那一首他就跳過（不扣分），避免網路很差的手機讓整局停住。
- 下一首還沒準備好時，上一首會繼續播著，等新的一首好了才停，不會一片安靜乾等；房主畫面會顯示已略過幾首不能用的歌。

斷線處理：手機睡著或網路中斷會自動重連；重新整理頁面後按「加入」回到房間，分數保留；房主斷線 20 秒，房間裡最早加入的人自動接手；網路擋住即時串流時改成每秒查詢。

## 線上資料庫（Firebase Realtime Database）

對戰和排行榜用免費的 Firebase Realtime Database，網址寫在 `src/battle.js` 的 `FB_DEFAULT`。資料庫的「規則」要設成：

```json
{
  "rules": {
    "rooms": {
      "$code": {
        ".read": "$code.matches(/^[A-Z2-9]{4}$/)",
        ".write": "$code.matches(/^[A-Z2-9]{4}$/)"
      }
    },
    "board": {
      ".read": true,
      "$id": {
        ".write": "!data.exists()",
        ".validate": "newData.hasChildren(['n','s','ts']) && newData.child('n').isString() && newData.child('n').val().length <= 20 && newData.child('s').isNumber()"
      }
    }
  }
}
```

規則沒設好時，遊戲的好友對戰頁面會直接提示。

## 檔案

| 路徑 | 內容 |
| --- | --- |
| `index.html` | 遊戲本體（單一檔案，GitHub Pages 直接提供） |
| `og.png`、`icon-*.png`、`apple-touch-icon.png`、`manifest.webmanifest` | 分享預覽圖、圖示、加到主畫面用 |
| `src/template.html` | 遊戲畫面和單人模式程式 |
| `src/battle.js` | 好友對戰、每日排行榜（Firebase REST API + 即時串流） |
| `src/singers.txt` | 每位歌手的聲音類別（男／女／男團／女團／男女都有），出同性別干擾選項用；新增歌手要補上，否則建置會停下來提醒 |
| `src/bank.txt` | 題庫，一行一首：`歌名(/別名)\|歌手(、合唱)\|年份`，用 `@zh` `@tw` `@yue` `@en` `@kr` `@jp` `@ot` 分類 |
| `src/build.py` | 把題庫、簡繁對照、歌手別名、副歌時間、對戰程式組成 `index.html` |
| `src/make_assets.py` | 產生分享預覽圖和圖示 |
| `tests/` | Playwright 自動測試；`fake_firebase.py` 是模擬 Firebase 的本機伺服器 |

## 更新

```bash
cd src
python3 build.py template.html bank.txt ../index.html
python3 make_assets.py ..        # 只有改圖示或預覽圖時需要
```

## 測試

```bash
pip install playwright && playwright install chromium
python3 tests/run_v12.py index.html src/bank.txt            # 單人模式完整檢查
python3 tests/run_battle.py index.html src/bank.txt         # 三人連線對戰（含斷線、中途加入、房主接手）
python3 tests/run_battle_chorus.py index.html src/bank.txt  # 副歌模式對戰；加 --no-stream 測輪詢備援
python3 tests/run_battle_swap.py index.html src/bank.txt    # 朋友載不出的歌先換掉；下一首晚到時上一首繼續播
python3 tests/run_board.py index.html src/bank.txt          # 每日挑戰排行榜
python3 tests/run_rand.py index.html src/bank.txt           # 出題隨機性與歌手分散
python3 tests/run_options.py index.html src/bank.txt        # 干擾選項：同歌手、同性別、同年代
python3 tests/run_room_names.py index.html src/bank.txt     # 房間名稱（含 test 這種 4 個字母的名字）
python3 tests/run_battle_versions.py index.html src/bank.txt # 房主和朋友的題庫版本不同時照樣能玩
python3 tests/run_reports.py index.html src/bank.txt        # 「不是副歌」回報：當場取消、清單、全部取消
python3 tests/run_v6.py index.html src/bank.txt             # Apple / Deezer 連不上時的備援
```
