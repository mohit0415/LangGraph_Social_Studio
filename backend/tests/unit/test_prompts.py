import pytest

import src.utils.prompts as prompts_module
from src.utils.prompts import (
    CACHE_FLOOR_TOKENS,
    CONSISTENCY_SYSTEM,
    CONSISTENCY_TASK,
    MANAGER_SYSTEM,
    MANAGER_TASK,
    REVISE_TASK,
    ROUTER_SYSTEM,
    ROUTER_TASK,
    RULES,
    SELF_CHECK_REVISION_TASK,
    SELF_CHECK_SYSTEM,
    SELF_CHECK_TASK,
    SHARED_PREFIX,
    SHARED_PREFIX_MIN_CHARS,
    WRITE_TASK,
    WRITER_SYSTEM,
)


def test_shared_prefix_clears_the_cache_floor():
    assert len(SHARED_PREFIX) >= SHARED_PREFIX_MIN_CHARS


def test_the_floor_is_derived_from_the_provider_minimum():
    assert CACHE_FLOOR_TOKENS == 1024
    assert SHARED_PREFIX_MIN_CHARS > CACHE_FLOOR_TOKENS


def test_shared_prefix_is_static():
    assert "{" not in SHARED_PREFIX
    assert "}" not in SHARED_PREFIX
    assert SHARED_PREFIX == SHARED_PREFIX.format()


def test_shared_prefix_covers_every_platform():
    for platform in RULES:
        assert platform.lower() in SHARED_PREFIX.lower()


def test_shared_prefix_states_every_character_limit():
    for rule in RULES.values():
        assert str(rule["max_chars"]) in SHARED_PREFIX


def test_rules_define_exactly_the_three_supported_platforms():
    assert set(RULES) == {"linkedin", "x", "instagram"}


@pytest.mark.parametrize(
    "platform,max_chars",
    [("linkedin", 3000), ("x", 280), ("instagram", 2200)],
)
def test_rules_carry_the_platform_limits(platform, max_chars):
    assert RULES[platform]["max_chars"] == max_chars
    assert RULES[platform]["style"].strip() != ""


def test_manager_task_renders():
    assert "source text" in MANAGER_TASK.format(topic="source text")


@pytest.mark.parametrize("platform", ["linkedin", "x", "instagram"])
def test_writer_system_renders_per_platform(platform):
    rendered = WRITER_SYSTEM.format(
        platform=platform,
        style=RULES[platform]["style"],
        max_chars=RULES[platform]["max_chars"],
    )

    assert platform in rendered
    assert str(RULES[platform]["max_chars"]) in rendered


def test_write_and_revise_tasks_render():
    assert "BRIEF" in WRITE_TASK.format(brief="BRIEF", platform="x")

    revised = REVISE_TASK.format(brief="BRIEF", old_draft="OLD", fix="FIX")
    assert "OLD" in revised
    assert "FIX" in revised


def test_self_check_tasks_render():
    assert "x" in SELF_CHECK_SYSTEM.format(platform="x")
    assert "DRAFT" in SELF_CHECK_TASK.format(brief="B", draft="DRAFT")

    revision = SELF_CHECK_REVISION_TASK.format(
        brief="B",
        draft="DRAFT",
        previous_problem="NOTE",
        attempt=2,
        max_attempts=3,
        final_warning="",
    )
    assert "NOTE" in revision
    assert "attempt 2 of 3" in revision


def test_consistency_and_router_tasks_render():
    assert "POSTS" in CONSISTENCY_TASK.format(brief="B", posts="POSTS")
    assert "MESSAGE" in ROUTER_TASK.format(message="MESSAGE", history="H")


@pytest.mark.parametrize(
    "prompt",
    [MANAGER_SYSTEM, CONSISTENCY_SYSTEM, ROUTER_SYSTEM],
)
def test_static_system_prompts_need_no_arguments(prompt):
    assert prompt.format() == prompt


def test_router_system_names_only_the_supported_platforms():
    assert "linkedin" in ROUTER_SYSTEM
    assert "instagram" in ROUTER_SYSTEM
    assert "Facebook" in ROUTER_SYSTEM


def test_the_guard_rejects_a_prefix_below_the_cache_floor():
    import pathlib

    source = pathlib.Path(prompts_module.__file__).read_text(encoding="utf-8")
    start = source.index('SHARED_PREFIX = """')
    end = source.index('"""', start + len('SHARED_PREFIX = """')) + 3
    shrunk = source[:start] + 'SHARED_PREFIX = "too short"' + source[end:]

    with pytest.raises(ValueError, match="below the"):
        exec(compile(shrunk, prompts_module.__file__, "exec"), {})


def test_the_guard_passes_for_the_real_prefix():
    import pathlib

    source = pathlib.Path(prompts_module.__file__).read_text(encoding="utf-8")

    exec(compile(source, prompts_module.__file__, "exec"), {})
