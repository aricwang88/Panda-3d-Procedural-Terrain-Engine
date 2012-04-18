"""
terrainshadergenerator.py: This file contains a shader generator
specific to the terrain in this engine.
"""
__author__ = "Stephen Lujan"

from config import *
from panda3d.core import Shader
from pandac.PandaModules import PTAFloat
from terraintexturemap import *

###############################################################################
#   TerrainShaderGenerator
###############################################################################

class TerrainShaderGenerator:

    def __init__(self, terrain, textureMapper=None):

        self.terrain = terrain
        if not textureMapper:
            textureMapper = TextureMapper(terrain)
        self.textureMapper = textureMapper
        self.normalMapping = True
        self.detailTexture = True
        self.parallax = False
        self.glare = False
        self.avoidConditionals = 1
        self.fogExponential()
        logging.info("setting basic terrain shader input...")

        self.terrain.setShaderFloatInput("fogDensity", self.fogDensity)
        #self.terrain.setShaderFloatInput("fogDensity", 0)
        self.normalMapStrength = 1.6
        self.terrain.setShaderFloatInput("normalMapStrength", self.normalMapStrength)

        self.detailHugeScale = self.terrain.tileSize / 50 * TERRAIN_HORIZONTAL_STRETCH
        self.detailBigScale = self.terrain.tileSize / 9 * TERRAIN_HORIZONTAL_STRETCH
        self.detailSmallScale = self.terrain.tileSize / 2.2 * TERRAIN_HORIZONTAL_STRETCH
        self.terrain.setShaderFloatInput("detailHugeScale", self.detailHugeScale)
        self.terrain.setShaderFloatInput("detailBigScale", self.detailBigScale)
        self.terrain.setShaderFloatInput("detailSmallScale", self.detailSmallScale)
        self.terrain.setShaderFloatInput("ambientOcclusion", 1.0)
        logging.info("done")

    def addTexture(self, texture):
        self.textureMapper.addTexture(texture)

    def addRegionToTex(self, region, textureNumber=-1):
        self.textureMapper.addRegionToTex(region, textureNumber)

    def fogLinear(self):
        # We need to figure out what fog density we want.
        # Lets find out what density results in 80% fog at max view distance

        self.fogDensity = 0.8 * (self.terrain.maxViewRange)
        self.fogFunction = '''
float FogAmount( float maxDistance, float3 PositionVS )
{
    float z = length( PositionVS ); // viewer position is at origin
    return saturate( 1-(z / maxDistance));
}'''

    def fogExponential(self):
        # We need to figure out what fog density we want.
        # Lets find out what density results in 75% fog at max view distance
        # the basic fog equation...
        # fog = e^ (-density * z)
        # -density * z = ln(fog) / ln(e)
        # -density * z = ln(fog)
        # density = ln(fog) / -z
        # density = ln(0.25) / -maxViewRange
        self.fogDensity = 1.38629436 / (self.terrain.maxViewRange + 30)
        self.fogFunction = '''
float FogAmount( float density, float3 PositionVS )
{
    float z = length( PositionVS ); // viewer position is at origin
    return saturate( pow(2.7182818, -(density * z)));
}'''

    def fogExponential2(self):
        # We need to figure out what fog density we want.
        # Lets find out what density results in 80% fog at max view distance
        # the basic fog equation...
        #
        # fog = e^ (-density * z)*(-density * z)
        # -density^2 * z^2 = ln(fog) / ln(e)
        # -density^2 * z^2 = ln(fog)
        # density = root(ln(fog) / -z^2)
        # density = root(ln(0.2) / -maxViewRange * maxViewRange)

        self.fogDensity = 1.60943791 / (self.terrain.maxViewRange * self.terrain.maxViewRange)
        self.fogFunction = '''
float FogAmount( float density, float3 PositionVS )
{
    float z = length( PositionVS ); // viewer position is at origin
    float exp = density * z;
    return saturate( pow(2.7182818, -(exp * exp)));
}'''

    def getHeader(self):

        header = '''
//Cg
// Should use per-pixel lighting, hdr1, and medium bloom
// input alight0, dlight0

'''
        header += 'const float slopeScale = '
        header += str(self.terrain.maxHeight / self.terrain.horizontalScale) + ';'
        return header



    def getFunctions(self):
        functions = ''
        if self.fogDensity:
            functions += '''
//returns [0,1] fog factor
'''
            functions += self.fogFunction
        functions += '''

float3 absoluteValue(float3 input)
{
    return float3(abs(input.x), abs(input.y), abs(input.z));
}
'''

        if self.avoidConditionals == 0:
            functions += '''
float calculateWeight( float value, float minimum, float maximum )
{
    if (value < minimum)
        return 0.0;
    if (value > maximum)
        return 0.0;

    float weight = min(maximum - value, value - minimum);

    return weight;
}
'''
        else:
            functions += '''
float calculateWeight( float value, float minimum, float maximum )
{
    value = clamp(value, minimum, maximum);
    float weight = min(maximum - value, value - minimum);

    return weight;
}
'''

        functions += '''
float calculateFinalWeight( float height, float slope, float4 limits )
{
    return calculateWeight(height, limits.x, limits.y)
           * calculateWeight(slope, limits.z, limits.a);
}

float3 reflectVector( float3 input, float3 normal)
{
    return ( -2 * dot(input,normal) * normal + input );
}
'''
        return functions


    def getVertexShader(self):
        vShader = '''
void vshader(
        in float2 vtx_texcoord0 : TEXCOORD0,
        in float4 vtx_position : POSITION,
        in float4 vtx_normal : NORMAL,
        in float4 vtx_color : COLOR,

        out vfconn output,
        out float4 l_position : POSITION,

        uniform float fogDensity: FOGDENSITY,
        uniform float3 camPos : CAMPOS,
        uniform float4x4 trans_model_to_world,
        uniform float4x4 mat_modelproj,
        uniform float4x4 trans_model_to_view,
        uniform float4x4 tpose_view_to_model,
        //test
        //uniform float4x4 tpose_model_to_world,
        uniform float4x4 itp_modelview,
        uniform float4x4 itp_projection,
        uniform float4x4 itp_modelproj
) {
        // Transform the current vertex from object space to clip space
        l_position = mul(mat_modelproj, vtx_position);

        //for terrain
        output.l_color = vtx_color;
        output.l_tex_coord = vtx_texcoord0;
        output.l_world_pos = mul(trans_model_to_world, vtx_position);

        //from autoshader - for parallax map
        //output.l_tangent.xyz = mul((float3x3)tpose_view_to_model, vtx_tangent1.xyz);
        //output.l_tangent.w = 0;
        //output.l_binormal.xyz = mul((float3x3)tpose_view_to_model, -vtx_binormal1.xyz);
        //output.l_binormal.w = 0;
'''
        if self.fogDensity:
            vShader += '''
        // there has to be a faster way to get the camera's coordinates in a shader
        float3 cam_to_vertex = output.l_world_pos - camPos;
        output.l_fog = FogAmount(fogDensity.x, cam_to_vertex);

'''

        vShader += '''
        output.l_normal = vtx_normal.xyz;
        output.l_normal.x *= slopeScale;
        output.l_normal.y *= slopeScale;
        output.l_normal = normalize(output.l_normal);
        //vtx_normal.xyz = output.l_normal;

        output.l_eye_position = mul(trans_model_to_view, vtx_position);
        output.l_eye_normal = mul(tpose_view_to_model, vtx_normal);
        //output.l_eye_normal = mul(tpose_view_to_model, vtx_normal);
}
'''
        return vShader


    def getFragmentShaderTop(self):
        fshader = '''
void fshader(
        in vfconn input,
        uniform float4 alight_alight0,
        //uniform float4x4 dlight_dlight0_rel_view,
        uniform float4x4 dlight_dlight0_rel_world,
        out float4 o_color : COLOR0,
        uniform float4 attr_color,
        uniform float4 attr_colorscale,

        //for terrain shader
        in uniform sampler2D normalMap  : NORMALMAP,
        in uniform sampler2D detailTex  : DETAILTEX,
        in uniform float normalMapStrength : NORMALMAPSTRENGTH,
        in uniform float detailSmallScale,
        in uniform float detailBigScale,
        in uniform float detailHugeScale,
        in uniform float ambientOcclusion,
        '''
        if self.fogDensity:
            fshader += '''
        in uniform float4 fogColor : FOGCOLOR,
'''
        return fshader


    def getDetailTextureCode(self):
        fshader = '''

        // get detail coordinates
        float2 detailCoordSmall = input.l_tex_coord * detailSmallScale;
        float2 detailCoordBig = input.l_tex_coord * detailBigScale;
        float2 detailCoordHuge = input.l_tex_coord * detailHugeScale;
        float3 terrainNormal = input.l_normal;
        float4 detailColor = (tex2D(detailTex, detailCoordSmall) * tex2D(detailTex, detailCoordBig) * tex2D(detailTex, detailCoordHuge));
'''
        if self.normalMapping:
            fshader += '''
        // normal mapping
        float3 normalModifier = tex2D(normalMap, detailCoordSmall) + tex2D(normalMap, detailCoordBig) + tex2D(normalMap, detailCoordHuge) - 1.5;
        input.l_normal *= normalModifier.z/normalMapStrength;
        input.l_normal.x += normalModifier.x;
        input.l_normal.y += normalModifier.y;
        input.l_normal = normalize(input.l_normal);
'''
        if self.parallax:
            fshader += '''
        // parallax mapping
        // Given the regular uv coordinates
        float2 uv = input.l_tex_coord;

        // Step 1 - Get depth from the alpha (w) of the relief map
	//float depth = (tex2D(reliefmap,uv).w) * hole_depth;
        float depth = detailColor * 5.0;

	// Step 2 - Create transform matrix to tangent space
	//float3x3 to_tangent_space = float3x3(IN.binormal,IN.tangent,IN.normal);
        float3x3 to_tangent_space = float3x3(input.l_binormal, input.l_tangent, input.l_normal);

	// Steps 2 and 3
        //float2 offset = depth * mul(to_tangent_space,v);
        float2 offset = depth * mul(to_tangent_space,input.l_eye_normal);

        // Step 4, offset u and v by x and y
        input.l_tex_coord += offset;
'''
        return fshader


    def getFragmentShaderEnd(self):

        fshader = ''
        if self.detailTexture:
            fshader += '''
        // Add detail texture
        attr_color *= 1.5 * detailColor;
'''
        fshader += '''
        // Begin view-space light calculations
        float ldist,lattenv,langle;
        float4 lcolor,lspec,lvec,lpoint,latten,ldir,leye,lhalf;
        float4 tot_ambient = float4(0,0,0,0);
        float4 tot_diffuse = float4(0,0,0,0);
        // Ambient Light 0
        lcolor = alight_alight0;
        tot_ambient += lcolor;
        // Directional Light 0
        lcolor = dlight_dlight0_rel_world[0];
        lspec  = dlight_dlight0_rel_world[1];
        lvec   = dlight_dlight0_rel_world[2];
        //lvec.xyz = normalize(lvec.xyz);
        float dlight_angle = saturate(dot(input.l_normal.xyz, lvec.xyz));
        dlight_angle *= sqrt(dlight_angle);
'''
        if self.glare:
            fshader += '''
        //glare direct sun... should glare on reflection over normal instead.
        dlight_angle -= 0.002 * dlight_angle / (dlight_angle-1.005);
'''
        fshader += '''
        lcolor *= dlight_angle;

        tot_diffuse += lcolor;
        // Begin view-space light summation
        float4 result = float4(0,0,0,0.5);
        result += tot_ambient * attr_color;
        result += tot_diffuse * attr_color;
        result *= attr_colorscale;
        if (ambientOcclusion)
            result *= input.l_color * input.l_color * 1.75;
        // End view-space light calculations

        //////////DEBUGGING
        //  Debug view slopes
        //result.rgb = slope * float3(1.0,1.0,1.0) * 2.0;
        //  Debug view surface normals
        //result.rgb = absoluteValue(input.l_normal) * 1.3;
        //  Debug view eye normals
        //result.rgb = input.l_eye_normal.xyz * 2.0;
        //  Debug view Light only
        //result = tot_diffuse + tot_ambient;
        //  Debug view DLight only
        //result = tot_diffuse;
        //  Debug view terrain as solid color before fog
        //result = float4(1.0,0,0,0.5);
        //////////


        //hdr0   brightness drop 1 -> 3/4
        //result.rgb = (result*result*result + result*result + result) / (result*result*result + result*result + result + 1);
        //hdr1   brightness drop 1 -> 2/3
        result.rgb = (result*result + result) / (result*result + result + 1.0);
        //hdr2   brightness drop 1 -> 1/2
        //result.rgb = (result) / (result + 1);
'''
        if self.fogDensity:
            fshader += '''
        result = lerp( fogColor, result, input.l_fog );
'''
        fshader += '''
        o_color = result * 1.000001;
}
'''
        return fshader


    def initializeShaderInput(self):
        return


    def createShader(self):
        logging.info("loading terrain settings into shader input...")
        self.initializeShaderInput()

        logging.info("assembling shader cg code")
        shader = self.getHeader()
        shader += self.getFunctions()
        shader += self.getVertexFragmentConnector()
        shader += self.getVertexShader()
        shader += self.getFragmentShaderTop()
        shader += self.getFShaderTerrainParameters()
        shader += self.getDetailTextureCode()
        shader += self.getTerrainPrepCode()
        shader += self.getTerrainTextureCode()
        shader += self.getFragmentShaderEnd()
        return shader

    def saveShader(self, name='shaders/terrain.sha'):
        string = self.createShader()
        f = open(name, 'w')
        f.write(string)
