# 参考秒计量账

原有直接校准、采样修订、设备秒计量及旧格式见 `README.md`。原库、旧报告和原测试继续使用。

## 登记校时

`Archive.register_clock(clock_id, batch_revision, device_log, reference_log, rate_range)` 返回下述 JSON 兼容字典。`batch_revision` 使用原 `RevisionRef`。每份日志的记录是 `(整数秒, 非空白标记)`，各自按时刻严格递增。标记允许重复，按字符串原值比较。`rate_range` 是 `(min_rate,max_rate)`，沿用原有理数输入形式，两端为正且下限不大于上限。

设设备时刻为 `t`，参考时刻为 `r`。映射满足 `r=a*t+b`，`a` 在给定闭区间内。仅标记相同且映射时刻精确相等的脉冲计为匹配，每个匹配事件只计一次。不同仿射映射按匹配数比较，唯一最佳且至少匹配两个不同设备时刻才可登记。多个锚点组合得到同一个 `(a,b)` 时仍是同一个映射。允许全量计算。

登记冻结明确批次修订、两份完整日志、速率区间、映射及全部匹配事件。同号且规范化的修订、日志和区间相同则返回原登记，异绑定抛 `ValueError`。非法输入和不能唯一裁决的登记抛 `ValueError`，缺确切修订抛 `KeyError`。失败不占用校时号。

返回字段如下。日志采用 `[时刻, 标记]` 列表，`matches` 采用 `[设备时刻, 参考时刻, 标记]` 列表，按设备时刻升序。速率、偏移和区间端点均用最简 `[分子, 正分母]` 表示。

```json
{
  "clock_id": "fit",
  "batch_id": "morning-tide",
  "revision": 1,
  "device_log": [[1, "left"], [3, "right"]],
  "reference_log": [[2, "left"], [5, "right"]],
  "rate_range": [[1, 1], [2, 1]],
  "rate": [3, 2],
  "offset": [1, 2],
  "matches": [[1, 2, "left"], [3, 5, "right"]]
}
```

## 生成和交付

`Archive.build_clock_report(report_id, clock_id, curve_id, target, window)` 消费已登记的校时及其明确批次修订。`window` 是参考秒整数边界对 `[L,R)`，允许 `L=R`。以参考秒核算覆盖和积分，沿用 V1 的插值、直接校准方向、原段归属和有序分账。每笔保留参考时间边界、未经改写的设备原相邻采样对、方向、原段号和原结点。合法的零宽或无交集窗口交付空账、零覆盖和零积分。

`Archive.read_clock_report(report_id)` 读取已发布成果。上述加工和读取返回 JSON 兼容字典。`Archive.export_clock_report(report_id)` 返回该字典对应的确定性 JSON 字符串。沿用原 JSON 的 `report_id`、`binding`、`coverage`、`total` 和 `contributions` 字段与形状，`format_version` 为 2。`binding.window` 以及账项的 `start_s`、`end_s` 使用参考时间。`samples[].time_s` 始终是设备时刻。新增顶层 `clock`，取登记字典中的 `clock_id`、`rate`、`offset` 和 `matches` 四个字段。这样拿到导出的人可从映射、设备原采样和原校准段重算逐笔值及汇总。

校时报表与旧报表可使用相同字符串报告号，各自通过对应接口读取。校时报表的固定请求绑定是校时号、直接校准号、目标刻度及窗口。同号同绑定返回已存成果，异绑定和非法参数抛 `ValueError`，缺校时、校准或报告抛 `KeyError`。空窗也先验证引用和校准方向。登记和发布失败不留部分新成果，SQLite 写入异常向调用方传播。可复用原事务。提交批次更正、修改传入或返回的容器以及重开后，已发布的绑定和账项保持原样。读取、导出和报告重放使用已发布账项。

## 手算例与运行

- 重复标记样例中，设备侧 `0,1,2` 和参考侧 `10,11,12,20,21,22` 的标记均为 `same`，速率固定为 1。偏移 10 与 20 各有三件匹配，登记拒绝。双方分别加入 `3` 和 `13` 的 `extra` 事件后，同一校时号可登记，偏移 10 唯一胜出，交付四件匹配。
- 按上面的 `fit` 校时使用原示例曲线和采样，参考窗口 `[1,2)` 内分两笔。第一笔 `[1,5/4)` 的原段为 0，积分为 `5/96`。第二笔 `[5/4,2)` 的原段为 1，积分为 `15/32`。两笔的设备采样始终是 `(0,0)`、`(1,1)`，覆盖为 1 参考秒，总量为 `25/48`。窗口 `[2,3)` 无覆盖。

保留 `.pointwise-runtime.json` 的现有命令形式。完成后让其中的核验入口执行全部原回归和新链核验，让演示入口展示校时成果、重开和离库核账。`python3 -B clock_cases.py base` 可检查原归档样例。`python3 -B clock_cases.py verify` 和 `python3 -B clock_cases.py demo` 在新接口完成后调用，前者核验脉冲与分数窗口，后者展示真实交付。写入失败核验可参照 `tests/test_publication.py`，按实现的实际存储布局注入写入异常，检查旧账、缺失的新成果及同号重试。
