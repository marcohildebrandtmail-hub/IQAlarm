"""Profile ownership is enforced by real dispatcher bodies, including dry runs."""

import asyncio

from safety_support import local_runtime, models


def test_real_and_dry_profile_plans_never_mix_modes(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.config.stages = models.default_stages()
        runtime.config.secure_stage_id = "1"
        runtime.config.rules = models.default_rules()
        runtime.config.actions = {
            "night": models.Action(
                "night", "3", "notify", "notify.phone", message="Nacht", profile_ids=["armed_night"]
            ),
            "away": models.Action(
                "away",
                "3",
                "notify",
                "notify.phone",
                message="Abwesend",
                profile_ids=["armed_away"],
            ),
        }
        runtime.config.validate()
        plan = await runtime.test_level("3", profile_id="armed_away")
        assert [a["id"] for a in plan] == ["away"]
        assert not runtime.hass.services.calls
        await runtime.test_level("3", dry_run=False, profile_id="armed_night")
        assert [c[2]["message"] for c in runtime.hass.services.calls] == ["Nacht"]

    asyncio.run(scenario())
