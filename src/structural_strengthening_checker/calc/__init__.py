"""验算模块包：import 本包即完成 4 个模块的注册（副作用 import，勿删）。"""

from __future__ import annotations

from ..core.engine import CALC_REGISTRY  # noqa: F401

from . import cfrp_beam, post_rebar, section_enlarge, steel_plate  # noqa: F401  注册副作用

EXPECTED_MODULES = (
    "cfrp_beam_flexure",
    "steel_plate_flexure",
    "section_enlarge_flexure",
    "post_rebar_anchor",
)
