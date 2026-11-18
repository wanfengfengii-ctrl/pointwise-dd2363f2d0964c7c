# 河口计量归档

河口监测实验室的标定员提供相邻刻度的标定结点，采样员提供同一刻度下的仪器日志。质控员核对请求窗口内真正有观测支撑的累计量，并能查到每笔贡献使用的原始采样对与校准段。研究员可以按固定报告号读取或离库交付，更正现场日志后仍能取得原账。

## 一天的工作

1. 标定员登记 A 到 B 的直接校准，结点为 `(0,0), (1/2,1/4), (1,1)`。
2. 采样员提交 A 刻度的两个读数，0 秒为 0，1 秒为 1。归档发出明确修订号。
3. 质控员选择该修订、直接校准、目标 B 和窗口 `[0,1)`，发布计量账。0 到 1/2 秒积分为 1/16，1/2 到 1 秒积分为 5/16，覆盖 1 秒，总积分 3/8。
4. 质控员以最低覆盖 1 秒和积分闭区间 `[3/8,3/8]` 复核。两项均达标。
5. 研究员导出报告。从每笔的原采样、原校准结点、方向和时间范围，可以离线复算积分。
6. 采样员把后一条读数更正为 0，交回完整批次并取得新修订号。质控员按新修订发布零积分报告。
7. 重开归档后研究员分别取得旧报告的 3/8 和新报告的 0。明确选择旧修订还能重新生成同口径旧账。

## 运行

从项目根目录用 Python 3.11 运行。项目只使用标准库。

```sh
python3 -B verify.py
python3 -B -m unittest discover -s tests
python3 -B demo.py
```

演示使用 `examples/` 的两份 JSON 输入和临时 SQLite 库，输出有核验值的场景记录及新旧报告的真实 JSON。数据库和回归的故障触发器都在测试临时目录中使用。

## Python API

```python
from archive import Archive

with Archive('meter.sqlite') as archive:
    archive.register_curve('probe', 'A', 'B', [(0, 0), ('1/2', '1/4'), (1, 1)])
    revision = archive.put_batch('morning', 'A', [(0, 0), (1, 1)])
    report = archive.build_report('sheet-1', revision, 'probe', 'B', (0, 1))
    assessment = archive.assess_report('sheet-1', 1, '3/8', '3/8')
    output = archive.export_report('sheet-1')
```

- `Archive(path=':memory:')` 打开并初始化归档。`initialize()` 可重复执行，保留用户记录。用 `close()` 或上下文管理器关闭。
- `register_curve(curve_id, source, target, knots)` 和 `get_curve(curve_id)` 返回固定 `DirectCurve`。两轴严格递增，首尾必须分别是 `(0,0)` 与 `(1,1)`，两个刻度必须异名。同校准号和同内容重放返回相等的绑定，内容冲突抛 `ValueError`。
- `put_batch(batch_id, scale, samples)` 返回 `RevisionRef`，由批次号和从 1 开始的修订号组成。每次成功提交一份完整修订。`get_revision(ref)` 读取明确修订，`get_current_revision(batch_id)` 读取当前修订。每份修订固定自身刻度及采样序列。
- `build_report(report_id, batch_revision, curve_id, target, window)` 返回 `ReportSnapshot`。使用 `put_batch` 返回的引用或 `archive.RevisionRef(batch_id, number)`。窗口是整数秒边界对 `[L,R)`，允许 `L=R`。批次与目标必须恰为校准的两端。已占用报告号要求请求绑定完全相同。同绑定重放已存快照。新请求在引用和方向有效后加工，随后原子发布报告与账项。SQLite 写入错误向调用方传播，整份新报告回滚。
- `read_report(report_id)` 取已存快照，`export_report(report_id)` 返回确定性的 JSON 字符串。不存在的校准、批次、明确修订或报告抛 `KeyError`。非法输入、错误方向及固定身份冲突抛 `ValueError`。
- `assess_report(report_id, minimum_coverage, minimum_integral, maximum_integral)` 返回即时 `Assessment`，含阈值、实际值和所有适用的原因。`coverage_insufficient`、`integral_below_minimum` 和 `integral_above_maximum` 可定位到报告中有序的贡献。研究员依据复核结论选择报告。导出接口以固定报告号取成果。

标识与刻度使用非空白字符串。有理值接受 `Fraction`、整数、可由 `Fraction` 精确解析的有理字符串。结点、采样记录和窗口边界用两项元组或列表。结点和采样的外层可用任意逐项迭代的记录序列。采样至少两条，时刻为严格递增的整数秒，读数在 `[0,1]`。读数、时刻及复核阈值遇到浮点数、布尔量或缺值时抛 `ValueError`。

## 计算与交付口径

每对相邻采样点给出线性读数。用原采样对插值，裁到请求与观测时域交集。正向按原横轴切，反向按原纵轴切，两向使用同一套从 0 开始的原段号。切换原像正好位于时间片端点时只保留正长账项。下降仍按时间升序，恒值在内结点归右段，在 1 归末段。每笔由该片的换算端值均值乘秒长得到，覆盖为片长之和。零宽窗口或无交集在输入合法时得到空账和零量。时间原像及所有数值运算均采用 `Fraction`，单位为换算读数乘秒。

快照包含报告号、批次及修订、校准号、源和目标刻度、窗口、覆盖、总量及账项。账项包含正长时间范围、原相邻采样对、方向、原段号、原段两个结点及积分。原结点始终按登记的 A→B 坐标保存。JSON 的 `format_version` 为 1，`coverage`、`total`、账项的 `start_s`、`end_s`、`integral`、读数与结点坐标都用 `[分子, 正分母]`。原采样时刻和请求窗口保留整数秒。离库核账时，先按原采样对在账项两端插值，反向账项交换原结点坐标角色，再按该原段计算两个端值和梯形面积。按时间核对账项覆盖与面积之和。读取和导出直接使用持久化快照。

回归覆盖登记重放及冲突、无效更正、精确正反向切分、跨窗插值、空覆盖、引用与方向错误、写入回滚与同号重试、固定绑定重放、重开与重复初始化，以及独立离库复算。`tests/test_intake.py`、`tests/test_processing.py`、`tests/test_publication.py`、`tests/test_review.py` 随完整发现命令运行。
