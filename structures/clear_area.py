from gdpc import Block, Editor
import gdpc.geometry as geo


def killEmAll():
    print("clearing area...")

    editor = Editor(buffering=True)
    editor.bufferLimit = 4096
    buildArea = editor.getBuildArea()


    area = editor.getBuildArea()
    offset = area.offset
    SIZE = 25

    geo.placeCuboid(editor, (offset.x, offset.y, offset.z), (offset.x + SIZE, offset.y + 50, offset.z + SIZE), Block("air"))
    geo.placeCuboid(editor, (offset.x, offset.y, offset.z), (offset.x + SIZE, offset.y, offset.z + SIZE), Block("grass_block"))

    print("area cleared.")

killEmAll()
