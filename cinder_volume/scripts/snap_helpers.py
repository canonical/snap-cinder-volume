import importlib
import importlib.metadata
import os
import pathlib

from snaphelpers.scripts import snap_helpers as sh

CRAFT_PART_BUILD = os.environ["CRAFT_PART_BUILD"]

original_get_hooks = sh.get_hooks

paths = list(pathlib.Path(CRAFT_PART_BUILD).glob("*.egg-info"))

if len(paths) == 0:
    raise Exception(f"No egg-info found at {CRAFT_PART_BUILD}")

if len(paths) > 1:
    raise Exception(f"Multiple egg-info found at {CRAFT_PART_BUILD}")

dist_info_path = paths[0]

dist_info = importlib.metadata.Distribution.at(dist_info_path)

if dist_info.name is None:
    raise Exception(f"Could not determine project name from {dist_info_path}")


def filtered_hooks(*args, **kwargs):
    """Filtered hooks by build project."""
    hooks = original_get_hooks(*args, **kwargs)
    hooks_ = []
    for hook in hooks:
        if hook.project != dist_info.name:
            print("Filtering out ", hook.name, "from", hook.project)
            continue
        hooks_.append(hook)
    return hooks_


sh.get_hooks = filtered_hooks

script = sh.SnapHelpersScript()
