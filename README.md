# 東証 業種別騰落ランキング

[Kabutan 東証【業種別】騰落ランキング](https://kabutan.jp/warning/?mode=9_1&market=0&capitalization=-1&stc=zenhiritsu&stm=1&col=zenhiritsu) から、業種名と前日比率を平日15:50に取得して保存する GitHub Pages サイトです。

公開サイト: https://al00000000.github.io/Sector-ranking/

## データ

- `history/` … 比較用の生データ JSON
- `output/` … 日次 CSV (`sector_ranking_YYYY-MM-DD.csv`, UTF-8)
- `docs/data/` … GitHub Pages が読み込む JSON

## 取得

```powershell
py fetch_ranking.py
```

保存列は「順位」「順位変動」「前日順位」「業種名」「前日比率」「前日比率差」です。

## 注意

本サイトのデータの正確性は保証されません。投資判断はご自身の責任で行ってください。
