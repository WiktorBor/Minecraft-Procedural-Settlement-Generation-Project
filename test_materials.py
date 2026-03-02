import json
import random
from gdpc import Editor, Block

#load mateirals
with open('materials.json', 'r') as f:
    materials = json.load(f)
#load palettes
with open("palettes.json") as f:
    palettes = json.load(f)

style = random.choice(list(palettes.keys()))
pallette = palettes[style]
print(f"selected style: {style}")

#connect to Minecraft
editor = Editor(buffering=True)
build_area = editor.getBuildArea()
player_x, player_y, player_z = -62, 69, 63
width, depth, height = 7, 7, 10

start_x = player_x - width//2
start_z = player_z + 5
start_y = player_y -1  #start building at player's y level


#build floor
floor_block = Block(random.choice(pallette["floor"]))
for x in range(width):
    for z in range(depth):
        editor.placeBlock((start_x + x, start_y, start_z + z), floor_block)

#build walls
for y in range(1, height):
    for x in range(width):
        for z in range(depth):
            if x in (0, width-1) or z in (0, depth-1):
                wall_block = Block(random.choice(pallette["wall"]))
                editor.placeBlock((start_x + x, start_y + y, start_z + z), wall_block)

#place door at front
door_block = Block(random.choice(pallette["door"]))
editor.placeBlock((start_x + width//2, start_y +1, start_z), door_block)

#place windows
window_block = Block(random.choice(pallette["window"]))
editor.placeBlock((start_x, start_y + 2, start_z + depth//2), window_block)
editor.placeBlock((start_x + width - 1, start_y + 2, start_z + depth//2), window_block)

#build roof
roof_block = Block(random.choice(pallette["roof"]))
for x in range(-1, width+1):
    for z in range(-1, depth+1):
        editor.placeBlock((start_x + x, start_y + height, start_z + z), roof_block)

editor.flushBuffer()
print("house built successfully!")