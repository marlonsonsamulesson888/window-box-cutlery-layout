# 开窗盒餐具排布计算

给开窗彩盒里竖排的餐具算中心距、组宽、窗宽、两侧留纸、每支的上下端和垫高，并按厂内规则逐条检查。只算数，不出图、不出刀模。

入口：[SKILL.md](SKILL.md)。仅需 Python 3.10+ 标准库。

```sh
python scripts/window_layout.py examples/20p_210x270.json --md 排布计算.md
python -m unittest discover -s tests -v
```

规则默认值在 [references/layout-rules.md](references/layout-rules.md)，可在输入 JSON 的 `rules` 里覆盖。示例为匿名化算例。

## 限制
- 按“最宽处”算净距，照片外框、反光和阴影会更宽，出图后要实测复量。
- 窗沿轮廓用折线近似，弧形窗沿只作估算。
- 不考虑叠放、斜放和内托结构强度。

MIT，Copyright (c) 2026 Marlonson Samulesson，见 [LICENSE](LICENSE)。
