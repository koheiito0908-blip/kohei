# データスキーマ

`heroes.json` / `pets.json` / `gear.json` はすべて、下記の形のオブジェクトの配列です。
新しいデータを追加するときはこのファイルを見本にしてください。

## heroes.json (英雄)

```json
{
  "id": "kebab-case-の一意なID",
  "name": "英雄名(日本語表記)",
  "rarity": "SSR | SR | R など、ゲーム内表記に合わせる",
  "role": "Tank | DPS | Support | Healer など",
  "element": "属性があれば(無ければ省略可)",
  "tier": "S | A | B | C | D (コミュニティ評価)",
  "synergy_tags": ["burn", "crit", "control" など、他の英雄/ペット/装備との相性タグ],
  "notes": "評価コメント(自由記述)",
  "source": {
    "type": "manual | discord | guide-site",
    "detail": "誰が/どこで言っていたか、URLやユーザー名など分かる範囲で",
    "date": "YYYY-MM-DD (情報の鮮度が分かるように必須)"
  },
  "confidence": "low | medium | high (情報の裏取りができているか)"
}
```

## pets.json (ペット)

`heroes.json` と同じ形に加えて:

- `role` の代わりに `effect_type`(バフ/デバフ/回復 など)を使ってもよい
- `synergy_tags` は「どの英雄・編成と噛み合うか」を書く

## gear.json (装備・カード)

```json
{
  "id": "...",
  "name": "...",
  "slot": "weapon | armor | accessory | card など",
  "rarity": "...",
  "tier": "S | A | B | C | D",
  "recommended_for": ["英雄IDまたはroleを列挙"],
  "effect": "効果の説明",
  "source": { "...": "heroesと同じ形" },
  "confidence": "low | medium | high"
}
```

## 運用ルール

1. **`source` と `date` は必ず埋める。** 出典不明・日付不明のデータは編成シミュレーターの信頼度表示で弱く扱われます。
2. 情報は上書きせず、`notes` に「2026-08版評価」のように追記して古い情報も残す(環境が変わるゲームなので、いつの情報かが重要)。
3. Discordから得た情報は、必ず自分がDiscordクライアント上で目視・コピーした内容のみを転記すること(自動収集はしない)。
