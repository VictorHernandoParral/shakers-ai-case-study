import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import importlib
import os

def test_oos_threshold_env(monkeypatch):
    # Set envs before import
    monkeypatch.setenv("OOS_SIM_MIN", "0.66")
    monkeypatch.setenv("OOS_MARGIN_MIN", "0.07")
    monkeypatch.setenv("OOS_REQUIRE_TOPK", "3")

    # Import (or reload) the module to pick envs
    import app.utils.oos as oos
    importlib.reload(oos)

    assert abs(oos.SIM_MIN - 0.66) < 1e-9
    assert abs(oos.MARGIN_MIN - 0.07) < 1e-9
    assert oos.REQUIRE_TOPK == 3
