import random
from gdpc import Block, Editor
import gdpc.geometry as geo

class TowerBuilder:

    def __init__(self, 
                 editor: Editor, 
                 origin: tuple,    #x,y,z coordinates
                 height: int = 10,
                 width: int = 5
                 ) -> None:
        
        self.editor = editor
        self.origin = origin
        self.height = height + random.randint(-5,5)
        self.width = width + random.choice([0,2])
    
    def _Palletes(self):
        return {
                "wall":["stone_bricks","cobblestone","cracked_stone_bricks"],
                "roof":["spruce_planks"],
                "floor":["spruce_log","spruce_planks"],
                "parapet":["spruce_log"],
                "door":["oak_door","spruce_door"]
                }

    def build(self):
        palletes = self._Palletes()
        wallBlock = random.choice(palletes["wall"])
        floorBlock = random.choice(palletes["floor"])
        roofBlock = random.choice(palletes["roof"])
        parapetBlock = random.choice(palletes["parapet"])
        door = random.choice(palletes["door"])
    
        self.buildWall(wallBlock)
        self.buildFloor(floorBlock)
        self.buildParapet(parapetBlock)
        self.buildRoof(roofBlock)
        self.buildDoor(door)
        self.buildLadder("oak_planks")
        self.editor.placeBlock(self.origin, Block("bamboo_block"))


    def buildWall(self, block):
        x, y, z = self.origin
        geo.placeCuboidHollow(self.editor, (x,y,z), (x+self.width-1, y+self.height-1, z+self.width-1), Block(block))
        
    
    def buildFloor(self, block):
        x, y, z = self.origin
        geo.placeCuboid(self.editor, (x,y,z), (x+self.width-1, y, z+self.width-1), Block(block))


    def buildRoof(self, block):
        x, y, z = self.origin
        geo.placeCuboid(self.editor, (x,y+self.height,z), (x+self.width-1, y+self.height, z+self.width-1), Block(block))

    def buildParapet(self, block):  #has risk of being build outside the build area
        x, y, z = self.origin
        x, y, z = x-1, y+self.height, z - 1 #starting point for the parapet
        geo.placeCuboidHollow(self.editor, (x,y,z), (x+self.width+1, y, z+self.width+1), Block(block))
        for i in range(self.width+2):
            for j in range(self.width+2):
                if (i%2 == 0 and j%2 == 0):
                    if (i == 0 or i == self.width+1 or j == 0 or j == self.width+1):
                        self.editor.placeBlock((x+i, y+1, z+j), Block(block))

    def buildDoor(self, block):
        coords = [((self.origin[0] + self.width//2, self.origin[1]+1, self.origin[2]),{"facing":"south"}),
                  ((self.origin[0], self.origin[1]+1, self.origin[2] + self.width//2),{"facing":"east"}),
                  ((self.origin[0] + self.width - 1, self.origin[1]+1, self.origin[2] + self.width//2),{"facing":"west"}),
                  ((self.origin[0] + self.width//2, self.origin[1]+1, self.origin[2] + self.width - 1),{"facing":"north"})
                  ]
        
        choice = random.choice(coords)
        self.editor.placeBlock(choice[0], Block(block, choice[1]))

    def buildLadder(self, block):
        x, y, z = self.origin
        geo.placeLine(self.editor, (x+self.width//2, y+1, z+self.width//2), (x+self.width//2, y+self.height, z+self.width//2), Block("ladder"))
        geo.placeLine(self.editor, (x+self.width//2, y+1, z+self.width//2+1), (x+self.width//2, y+self.height-1, z+self.width//2+1), Block(block))



        


editor = Editor(buffering=True)
editor.bufferLimit = 4096
buildArea = editor.getBuildArea()

tower = TowerBuilder(editor, (buildArea.offset.x + 5, buildArea.offset.y + 1, buildArea.offset.z + 5))
tower.build()


