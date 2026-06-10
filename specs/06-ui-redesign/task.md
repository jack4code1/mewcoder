# UI 界面重构 Tasks

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `src/mewcode/tui/widgets/input_box.py` | 新增 `InputChanged` 消息；监听子 `Input.Changed` 广播是否有内容 |
| 修改 | `src/mewcode/tui/widgets/status_bar.py` | 新增 `is_visible` 反应式属性与 `show()` / `hide()` |
| 修改 | `src/mewcode/tui/app.py` | 调整 `compose` 顺序、CSS、新增 `on_input_changed`、`on_mount` 初始隐藏 |
| 新建 | `tests/test_tui_ui_layout.py` | 布局顺序、显隐切换、输入框至少一行的测试 |
| 修改 | `tests/test_input_box.py` | 扩展：内容变化广播 `InputChanged`、提交后触发空 |
| 修改 | `tests/test_status_bar_metrics.py` | 扩展：隐藏时内容仍更新、再次显示反映最新值 |
| 修改 | `MANUAL.md` / `README.md` | 更新布局说明：状态区移到输入框上方、按输入显隐 |
| 修改 | `CHANGELOG.md` | 记录本次 UI 重构 |

## T1: InputBox 新增 InputChanged 消息类

**文件：** `src/mewcode/tui/widgets/input_box.py`
**依赖：** 无
**步骤：**
1. 在文件底部（与 `InputSubmitted` 等并列）新增 `class InputChanged(Message)`。
2. `__init__(self, has_content: bool)`：调用 `super().__init__()`，保存 `self.has_content = has_content`。

**验证：** `python -c "from mewcode.tui.widgets.input_box import InputChanged; print(InputChanged(True).has_content)"` 输出 `True`（设置好 PYTHONPATH）。

## T2: InputBox 监听 Input.Changed 并广播

**文件：** `src/mewcode/tui/widgets/input_box.py`
**依赖：** T1
**步骤：**
1. 新增方法，使用 `@on(Input.Changed, "#input-field")` 装饰，接收 `Input.Changed` 事件。
2. 在该方法内计算 `has_content = bool(event.value.strip())`。
3. `self.post_message(InputChanged(has_content))`。
4. 确认 `action_submit` 中 `self._set_input_value("")` 会触发 `Input.Changed`（Textual 设置 `Input.value` 会发出 Changed）；若需要保险，可在 `action_submit` 清空后显式 `self.post_message(InputChanged(False))`。

**验证：** 运行 `tests/test_input_box.py` 中新增用例（T9），观察打字发出 `has_content=True`、清空发出 `has_content=False`。

## T3: StatusBar 新增可见性控制

**文件：** `src/mewcode/tui/widgets/status_bar.py`
**依赖：** 无
**步骤：**
1. 新增反应式属性 `is_visible: reactive[bool] = reactive(False)`。
2. 新增 `show(self)`：设 `self.is_visible = True`，移除 `hidden` CSS 类（`self.remove_class("hidden")`）。
3. 新增 `hide(self)`：设 `self.is_visible = False`，添加 `hidden` CSS 类（`self.add_class("hidden")`）。
4. 确认 update 系列方法（`update_token_usage` 等）不因可见性短路，隐藏时仍写入反应式属性并调用 `_update_display()`（其内部 `query_one` 失败已被 try/except 兜住）。

**验证：** `python -c` 实例化检查 `show()/hide()` 切换 `is_visible`；运行 `tests/test_status_bar_metrics.py` 既有用例仍通过。

## T4: app.py 调整 compose 布局顺序

**文件：** `src/mewcode/tui/app.py`
**依赖：** 无
**步骤：**
1. 在 `compose` 的 `Vertical(...)` 中，将子组件顺序改为 `ChatArea` → `StatusBar` → `InputBox`（即 `StatusBar` 移到 `InputBox` 之前）。

**验证：** 启动应用（或布局测试 T8）确认状态区出现在输入框上方。

## T5: app.py 调整 CSS（显隐折叠 + 输入框至少一行）

**文件：** `src/mewcode/tui/app.py`
**依赖：** 无
**步骤：**
1. `#status-bar` 规则：将 `height: 1` 改为可显示时占一行（保留 `height: 1` 或改 `height: auto`），保留 `margin: 0 1`。
2. 新增 `#status-bar.hidden` 规则：`display: none;`（Textual 支持 `display: none` 使其不占布局空间）。
3. `#input-box` 规则：移除 `max-height: 4`，将 `min-height` 设为足以容纳边框（上下各 1）+ 至少一行内容（即 `min-height: 3`），`height` 设为 `auto` 或保留容纳一行的固定值，确保任何高度下至少一行可见且不裁切。

**验证：** 启动应用在小高度终端下确认输入框至少一行完整可见；布局测试 T8 校验。

## T6: app.py 新增 on_input_changed 与初始隐藏

**文件：** `src/mewcode/tui/app.py`
**依赖：** T1, T2, T3, T4
**步骤：**
1. 从 `input_box` 模块导入 `InputChanged`。
2. 新增 `def on_input_changed(self, event: InputChanged) -> None`：`status_bar = self.query_one("#status-bar", StatusBar)`；`status_bar.show() if event.has_content else status_bar.hide()`。
3. 在 `on_mount` 末尾调用 `self.query_one("#status-bar", StatusBar).hide()`，确保启动时输入框为空 → 状态区隐藏。

**验证：** 运行 `tests/test_tui_ui_layout.py`（T8）显隐用例通过。

## T7: 扩展 InputBox 测试

**文件：** `tests/test_input_box.py`
**依赖：** T1, T2
**步骤：**
1. 新增用例：在 `Input` 中设置非空内容，断言收到 `InputChanged` 且 `has_content is True`。
2. 新增用例：清空内容，断言收到 `InputChanged` 且 `has_content is False`。
3. 新增用例：调用提交（已有非空 → submit），断言提交后产生 `has_content=False`（输入框被清空）。
4. 既有 Enter 清空 / 空输入不入历史 / Up-Down 历史用例保持通过。

**验证：** `python -m pytest tests/test_input_box.py -v -p no:cacheprovider` 全通过。

## T8: 新增布局与显隐测试

**文件：** `tests/test_tui_ui_layout.py`
**依赖：** T4, T5, T6
**步骤：**
1. 用 Textual 的 `App.run_test()`（pilot）挂载 `MewCodeApp`。
2. 用例 A：挂载后查询 `main-layout` 子组件顺序，断言 `ChatArea` 在 `StatusBar` 之前、`StatusBar` 在 `InputBox` 之前。
3. 用例 B：启动后断言 `StatusBar` 处于隐藏（`is_visible is False` 或含 `hidden` 类）。
4. 用例 C：向输入框输入非空内容（pilot 模拟按键或直接设 `Input.value`），断言 `StatusBar` 变为可见。
5. 用例 D：清空输入框，断言 `StatusBar` 重新隐藏。
6. 用例 E：提交一条消息后，断言输入框被清空且 `StatusBar` 隐藏。
7. 用例 F：断言 `InputBox` 的 `min-height` styles 满足至少一行（检查 styles 或渲染高度 ≥ 边框+1）。

**验证：** `python -m pytest tests/test_tui_ui_layout.py -v -p no:cacheprovider` 全通过。

## T9: 扩展 StatusBar 隐藏期更新测试

**文件：** `tests/test_status_bar_metrics.py`
**依赖：** T3
**步骤：**
1. 新增用例：实例化/挂载 `StatusBar`，调用 `hide()`，再调用 `update_token_usage`(非零)，断言反应式 `token_usage` 已更新为新值。
2. 调用 `show()`，断言可见且内容为最新值。

**验证：** `python -m pytest tests/test_status_bar_metrics.py -v -p no:cacheprovider` 全通过。

## T10: 更新文档与 CHANGELOG

**文件：** `MANUAL.md`, `README.md`, `CHANGELOG.md`
**依赖：** T1-T9
**步骤：**
1. `MANUAL.md` / `README.md`：更新界面布局描述——状态区位于输入框上方，输入时显示、无输入时隐藏；输入框至少一行。
2. `CHANGELOG.md`：新增本章条目，记录布局顺序调整、状态区条件显隐、输入框高度健壮化、新增测试。

**验证：** `rg "输入框上方|状态区" MANUAL.md README.md` 命中；`CHANGELOG.md` 顶部含新版本条目。

## 执行顺序

```
T1 → T2 ─┐
T3 ──────┤
T4 ──────┼─→ T6 → T8
T5 ──────┘         ↘
T2 → T7            T9 (依赖 T3)
所有实现完成 → T10
```

- T1、T3、T4、T5 相互独立，可并行起步。
- T2 依赖 T1；T6 依赖 T1/T2/T3/T4；T8 依赖 T4/T5/T6。
- T7 依赖 T1/T2；T9 依赖 T3。
- T10 在全部实现与测试通过后进行。
