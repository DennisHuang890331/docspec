"""`python -m dspx` 入口——當 `docspec` 不在 PATH（agent tool 沙箱/PATH 未更新）時的 portability
後備：在有 dspx 套件可 import 的環境（dev checkout 設 PYTHONPATH=src，或已裝）直接跑 CLI。"""

from dspx.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
