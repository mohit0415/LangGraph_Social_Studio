from backend.src.utils.prompts import WRITER_SYSTEM ,REVISE_TASK,WRITE_TASK,RULES

def write_post(platform,brief,fix = "",old_draft=""):
    rules = RULES[platform]
    system =  WRITER_SYSTEM.format(
        platform = platform,
        style = rules['style'],
        old_draft=old_draft,
        fix = fix
    )

    if fix:
        user = REVISE_TASK.format(brief=brief, old_draft=old_draft, fix=fix)
    else:
        user = WRITE_TASK.format(brief=brief)
    return system
