# Configurations as code

Each file here is a complete Mouser `config.json` plus a top-level `_about`
block that names the device and explains every mapping. The app ignores
`_about` and preserves it, so a file round-trips through the UI unchanged.

| File | Device | Highlights |
|---|---|---|
| `mx4-ratmode.json` | Logitech MX Master 4 | Sense Panel click = Actions Ring, click then click-and-hold = Wispr Flow push-to-talk (`hold:fn`); Back = Paste, Forward = Copy; thumb wheel = next / previous tab. |

## Double press

Every button that reports press and release (Back, Forward, Middle, Gesture,
Sense Panel, Mode Shift, DPI switch, Thumb) can carry a second action on a
double press. Set it in the profile's mappings under `<button>_double`, for
example `"xbutton2_double": "paste"`. The second press is held like a normal
press, so `"actions_ring_double": "hold:fn"` holds Fn while the second press
is held: click, then click and hold, for push-to-talk. `"none"` turns it off.
In the app, select a button on the Mouse page and pick its action under
Double press; the mode and window are on the Settings page under
Double Press. Export after changing them there.

Two global settings decide how a single press is told apart from a double:

| Setting | Values | Effect |
|---|---|---|
| `double_press_mode` | `"instant"` (default) | The single action fires on the first press with no delay. A second press inside the window cancels it (an open Actions Ring closes) and starts the double action. |
| | `"wait"` | The single action waits until the window passes with no second press, so nothing fires twice, but every single click lands that much later. A first press held past the window commits to the single action at once, so press-and-hold still works. |
| `double_press_window_ms` | 50 to 1000, default 300 | Longest gap between the first release and the second press. In `wait` mode it is also how long a first press may be held before it counts as a long press. |

A button whose own action is `"none"` keeps its native click on a single
press (Back, Forward and Middle replay their OS click). Buttons in Gesture
Swipe mode do not support a double action.

Commands (run from the repo root):

```bash
scripts/config-apply.sh mx4-ratmode    # install it as the live config, restart Mouser
scripts/config-export.sh mx4-ratmode   # pull UI changes back into the file
.venv/bin/python scripts/config_as_code.py check   # validate every file
```

`tests/test_config_as_code.py` validates every file through the app's own
migration pipeline, so a config that the app would rewrite on load fails CI.
After changing settings in the UI, export and commit; the file in git is the
source of truth.
