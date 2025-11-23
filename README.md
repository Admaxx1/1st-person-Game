# 1st-person-Game

A lightweight Minecraft-inspired first-person demo built with Pygame + OpenGL. Move smoothly across a chunky grid platform, look around with arrow keys, and hop through a grove of blocky trees while fending off slow-moving zombies. **This arena build is Version 1.**

## Features
- WASD walking with tuned smoothing and jump physics (space to jump).
- Pick between arrow-key looking or smooth mouse-look before play begins, both with clamped pitch.
- Much larger tiled platform with alternating grass tones and chunky, unevenly spaced trees you can no longer pass through.
- Solid gray arena walls with the same airy roof; look straight up to see a bold “HUNGER GAMES” banner overhead.
- Red zombies now match player speed and scale up in number and pace the longer you survive (up to 30 at a time) while still glowing lighter red when in punch range.
- A simple survival timer lives at the bottom-left; lasting longer ramps difficulty with quicker spawns and faster walkers.
- A sprint-like boost you can trigger every 30 seconds (top-left cooldown indicator); it triples player speed for 10 seconds while zombies stay slow.
- Grounded enemies, edge clamping so you cannot fall, and a bottom HUD health bar with harsher contact damage plus slower idle regen.
- Death screen that reports how long you lasted, and punching only drops a single zombie per click.
- Baked platform/tree display lists and a 90 FPS tick target to keep motion stable and smooth.

## Requirements
- Python 3.10+
- GPU/driver that supports OpenGL (most desktop setups do).

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

**Controls**
- `W/A/S/D`: move forward/left/back/right
- Arrow keys: look around (Left = turn left, Right = turn right) **or** use mouse-look if selected on the intro screen
- `Space`: jump
- `Mouse left`: punch a single nearby zombie (brighter red when in range)
- `Shift`: trigger a 10-second speed boost (30-second cooldown, timer in the top-left)
- Stand still to slowly regenerate health when out of danger; close contact drains health quickly.
- `Esc`: quit
