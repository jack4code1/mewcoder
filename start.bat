@echo off
set PYTHONPATH=E:\agent_class\project\src
python -c "from mewcode.tui.app import run_app; run_app(model='mimo-v2.5-pro', provider='custom')"
