import random
from gdpc import Block, Editor
import gdpc.geometry as geo

class FarmBuilder:

    def __init__(self, 
                 editor: Editor, 
                 origin: tuple,    #x,y,z coordinates
                 width: int = 5
                 ) -> None:
        
        self.editor = editor
        self.origin = origin
        self.width = width + random.choice([0,2])
    

    def build(self):
        basinBlock = random.choice(["oak_log"])
    
        self.buildBasin(basinBlock)
        self.editor.placeBlock(self.origin, Block("bamboo_block"))


    def buildBasin(self, block):
        x, y, z = self.origin
        geo.placeCuboid(self.editor, (x,y-1,z), (x+self.width-1, y-1, z+self.width-1), Block(block))
        geo.placeCuboidWireframe(self.editor, (x,y,z), (x+self.width-1, y, z+self.width-1), Block(block))
        geo.placeCuboid(self.editor, (x+1,y,z+1), (x+self.width-2, y, z+self.width-2), Block("farmland"))

        geo.placeLine(self.editor, (x+self.width//2, y, z+1), (x+self.width//2, y, z+self.width-2), Block("water"))
        geo.placeCuboid(self.editor, (x+1,y+1,z+1), (x+self.width//2-1, y+1, z+self.width-2), Block("wheat",{"age":7}))
        geo.placeCuboid(self.editor, (x+self.width//2+1,y+1,z+1), (x+self.width-2, y+1, z+self.width-2), Block("carrots",{"age":7}))




        


editor = Editor(buffering=True)
editor.bufferLimit = 4096
buildArea = editor.getBuildArea()

farm = FarmBuilder(editor, (buildArea.offset.x + 5, buildArea.offset.y + 1, buildArea.offset.z + 5))
farm.build()