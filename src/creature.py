
from pandac.PandaModules import Vec3
from direct.actor.Actor import Actor
from pandac.PandaModules import NodePath
from pandac.PandaModules import PandaNode
from direct.showbase.DirectObject import DirectObject
import math

origin = Vec3(0,0,0)

class Creature(NodePath):
    
    def __init__(self, heightFunction, startPosition = Vec3(0,0,0)):
        
        NodePath.__init__(self, "Creature")
        self.reparentTo(render)
        self.startPosition = startPosition
        self.setPos(startPosition)
        #  movement
        self.acceleration = 25
        self.velocity = Vec3(0,0,0)
        self.maxSpeed = 10
        self.speed = 0
        self.maxAngularVelocity = 360
        self.turbo = 1
        
        self.body = Actor("models/ralph",
                   {"run":"models/ralph-run",
                   "walk":"models/ralph-walk"})
        self.body.setScale(0.25)
        self.body.reparentTo(self)
        self.heightFunction = heightFunction
        
        
    def accelerate(self, desiredVelocity, elapsed):
        acceleration = self.acceleration * elapsed
        deltaV = desiredVelocity - self.velocity
        if deltaV.length() > acceleration:
            deltaV.normalize()
            deltaV *= acceleration
        self.velocity += deltaV
        self.speed = self.velocity.length()
        if self.speed > 0:
            self.isMoving = True
        else:
            self.isMoving = False
               
    def turnBody(self, desiredHeading, elapsed):
        """ 
        no angular acceleration... 
        its really not that noticeable outside of ragdolls
        """
        heading = self.body.getH()
        maxAngularVelocity = self.maxAngularVelocity * elapsed
        deltaH = desiredHeading - heading
        
        # Make sure we're taking turning the quick way. If we're turning more
        # than 180.0 we should be turning the other direction.
        if deltaH > 180.0:
            heading+= 360.0
            deltaH = desiredHeading - heading
        elif deltaH < -180.0:
            heading-= 360.0
            deltaH = desiredHeading - heading
        
        #limit turning speed
        if deltaH > maxAngularVelocity:
            deltaH = maxAngularVelocity
        elif deltaH < -maxAngularVelocity:
            deltaH = -maxAngularVelocity
        self.body.setH(heading + deltaH)

    def animate(self):
        # If Ralph is moving, loop the run animation.
        # If he is standing still, stop the animation.
        # reversed walk animation for backward.
        if self.velocity.length > 0:
            if self.isMoving is False:
                self.body.loop("run")
                self.isMoving = True
        else:
            if self.isMoving:
                self.body.stop()
                self.body.pose("walk",9)
                self.isMoving = False 
            
    def move(self, desiredVelocity, desiredHeading, elapsed):
        # save Ralph's initial position so that we can restore it,
        # in case he falls off the map or runs into something.
        # this doesn't work now, with collision detection removed, needs fixing
        startpos = self.getPos()
        
        self.accelerate(desiredVelocity, elapsed)
        self.turnBody(desiredHeading, elapsed)
        self.setPos(startpos + self.velocity * elapsed * self.turbo)
        self.animate()
        self.setZ(self.heightFunction(self.getX(),self.getY()))
                
class Player(Creature):
    def __init__(self, heightFunction,  startPosition = Vec3(0,0,0)):
        Creature.__init__(self,  heightFunction, startPosition)
        #self.desiredHeading = 0.0
        
    def update(self, elapsed):
        heading = -self.getH()
        direction = 0.0
        self.turbo = 1 + 14 * self.controls["turbo"]
        
        if self.controls["forward"] == 1:
            if self.controls["right"] != 0:
                #direction = 45.0
                direction = 0.0
            elif self.controls["left"] != 0:
                #direction = 45.0
                direction = 0.0
            elif self.controls["back"] != 0:
                Creature.move(self, Vec3(0,0,0), 0, elapsed)
                return
        else:
            if self.controls["right"] != 0:
                direction = -90.0
            elif self.controls["left"] != 0:
                direction = 90.0
            elif self.controls["back"] == 0:
                Creature.move(self, Vec3(0,0,0), 0, elapsed)
                return
        
        # the body is parented to the Player
        # heading will direct the velocity of the Player
        # direction will turn the body relative to the Player
        # the heading of the Player is already altered by the camera
        heading += direction
        desiredVelocity = Vec3(math.sin(heading/180.0 * math.pi) , math.cos(heading/180.0 * math.pi), 0) * self.maxSpeed
        if self.controls["forward"] == 1:
            desiredVelocity *= -1
        self.move(desiredVelocity,direction,elapsed)
        
class Ai(Creature):
    def __init__(self, heightFunction, startPosition = Vec3(0,0,0)):
        Creature.__init__(self, heightFunction, startPosition)
        self.seekTarget = None
        self.arrivalRadius = 1
        
    def update(self, elapsed):
        if self.seekTarget:
            self.seekNP(self.seekTarget, elapsed)
            
    def seekVec(self, target, elapsed):
        desiredVelocity = target - self.getPos()
        desiredVelocity.z = 0
        distance = desiredVelocity.length()
        
        if distance > self.maxSpeed:
            desiredVelocity.normalize()
            desiredVelocity *= self.maxSpeed
            
        desiredHeading = math.degrees( math.atan2(desiredVelocity.y, desiredVelocity.x) ) + 90; 
        
        if distance < 1:
            desiredVelocity = Vec3(0,0,0)
        
        self.move(desiredVelocity, desiredHeading, elapsed)
        
    def seekNP(self, target, elapsed):
        self.seekVec(target.getPos(),elapsed)