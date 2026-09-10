from src.core.conditions import BuildContext, ConditionEvaluator


def test_build_context_legacy_aliases_map_to_new_fields() -> None:
    ctx = BuildContext()
    ctx.is_port_eu_rom = True
    ctx.is_port_global_rom = False
    ctx.port_rom_version = "14.0.3.0"

    assert ctx.portIsColorOS is True
    assert ctx.portIsColorOSGlobal is False
    assert ctx.portIsOOS is False
    assert ctx.port_oplusrom_version == "14.0.3.0"


def test_composite_condition_rom_type_uses_compat_aliases() -> None:
    evaluator = ConditionEvaluator()
    ctx = BuildContext()
    ctx.is_port_global_rom = True

    assert evaluator.evaluate({"condition": {"rom_type": "ColorOS_Global"}}, ctx) is True
    assert evaluator.evaluate({"condition": {"rom_type": "ColorOS"}}, ctx) is False


def test_composite_condition_rom_version_uses_compat_alias() -> None:
    evaluator = ConditionEvaluator()
    ctx = BuildContext()
    ctx.port_rom_version = "OS2.0.105.0"

    rule = {"condition": {"rom_version": {"contains": "2.0.105"}}}
    assert evaluator.evaluate(rule, ctx) is True
