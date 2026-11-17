package dev.redstone.pipeline;

import com.google.gson.*;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.*;
import java.nio.file.*;
import java.util.*;

/** Fixed screen anchors: time changes opacity/reveals/ornaments, never glyph position. */
public final class PipelineCaptions {
 record Cue(String id,int begin,int end,String text,String translation,float x,float y,String align,String effect,int color){}
 static final List<Cue> cues=new ArrayList<>();
 static volatile boolean enabled=true;
 static final Set<String> seen=new LinkedHashSet<>();
 static final Map<String,List<Float>> anchors=new LinkedHashMap<>();
 static int run=-1,frames=0,peak=0,remaining=0,anchorViolations=0,sampleKey=4;
 static boolean wasActive=false,failed=false;
 static void register(){
  try(var in=PipelineCaptions.class.getResourceAsStream("/assets/redstone_music/captions_scene.json")){
   var data=JsonParser.parseString(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
   if(data.has("sampleKey"))sampleKey=data.get("sampleKey").getAsInt();
   for(var e:data.getAsJsonArray("cues")){
    var o=e.getAsJsonObject();cues.add(new Cue(o.get("id").getAsString(),o.get("begin").getAsInt(),o.get("end").getAsInt(),o.get("text").getAsString(),o.get("translation").getAsString(),o.get("x").getAsFloat(),o.get("y").getAsFloat(),o.get("align").getAsString(),o.get("effect").getAsString(),Integer.parseInt(o.get("color").getAsString(),16)));
   }
  }catch(Exception e){throw new RuntimeException("Cannot load scene captions",e);}
  HudRenderCallback.EVENT.register((ctx,delta)->{
   try{draw(ctx);if(Boolean.getBoolean("nvfx.autotest")){ctx.method_51452();PipelineFX.capture();}}
   catch(Throwable e){if(!failed)e.printStackTrace();failed=true;remaining=0;save();}
  });
 }
 static int argb(float alpha,int color){return ((int)(255*PipelineFX.clamp(alpha))<<24)|(color&0xffffff);}
 static void glyphs(class_332 ctx,String text,int x,int y,float alpha,int color,float age,String effect){
  var font=PipelineFX.client.field_1772;
  if(effect.equals("letter_reveal")||effect.equals("edge_reveal")){
   for(int j=0;j<text.length();j++){
    float t=effect.equals("edge_reveal")?Math.min(j,text.length()-1-j)/(text.length()*.5f):j/(float)text.length();
    float a=alpha*PipelineFX.clamp((age-t*7)/3);
    if(a>.025f)ctx.method_51433(font,text.substring(j,j+1),x,y,argb(a,color),true);
    x+=font.method_1727(text.substring(j,j+1));
   }
  }else if(alpha>.025f)ctx.method_51433(font,text,x,y,argb(alpha,color),true);
 }
 static void draw(class_332 ctx){
  var s=PipelineFX.state;remaining=0;
  if(run!=s.run()){run=s.run();seen.clear();anchors.clear();frames=0;peak=0;anchorViolations=0;wasActive=false;}
  boolean active=PipelineFX.client!=null&&PipelineFX.client.field_1687!=null&&s.playing()==2&&s.sample()==sampleKey&&enabled&&!failed;
  if(!active){if(wasActive){wasActive=false;save();}return;}wasActive=true;
  float q=PipelineFX.clock();
  for(Cue c:cues)if(q>=c.begin&&q<c.end){
   remaining++;frames++;if(seen.add(c.id))System.out.println("NVSCENE_CAPTION|"+run+"|"+c.id+"|"+q+"|"+c.effect);
   float age=q-c.begin,leave=c.end-q,alpha=PipelineFX.clamp(age/5)*PipelineFX.clamp(leave/6);
   float w=ctx.method_51421(),h=ctx.method_51443();var font=PipelineFX.client.field_1772;
   float scale=Math.min(h*.032f/9,(w*(c.align.equals("center")?.53f:.48f))/Math.max(1,font.method_1727(c.text)));
   float left=w*c.x-(c.align.equals("center")?.5f:c.align.equals("right")?1:0)*font.method_1727(c.text)*scale;
   float top=h*c.y;
   String ak=c.id+"@"+(int)w+"x"+(int)h;var point=List.of(left,top,scale);var old=anchors.putIfAbsent(ak,point);if(old!=null&&!old.equals(point))anchorViolations++;
   var m=ctx.method_51448();m.method_22903();
   try{
    m.method_22904(left,top,0);m.method_22905(scale,scale,1);
    int tw=font.method_1727(c.text),cw=font.method_1727(c.translation),max=Math.max(tw,Math.round(cw*.76f));
    int pad=6,bottom=c.translation.isEmpty()?13:25;float growth=PipelineFX.ease(age/9);
    // Small translucent backplate, no animated displacement or text scaling.
    if(alpha>.025f)ctx.method_25294(-pad,-5,max+pad,bottom,argb(alpha*.43f,0x071321));
    int accent=argb(alpha*.9f,c.color);
    if(c.effect.equals("corner_frame")){
     for(int xx:new int[]{-pad,max+pad-9}){ctx.method_25294(xx,-6,xx+9,-5,accent);ctx.method_25294(xx,bottom,xx+9,bottom+1,accent);}
     ctx.method_25294(-pad,-5,-pad+1,2,accent);ctx.method_25294(max+pad-1,bottom-7,max+pad,bottom,accent);
    }else if(c.effect.equals("side_rule")||c.effect.equals("edge_reveal")){
     ctx.method_25294(-pad-3,-5,-pad-1,(int)(-5+(bottom+5)*growth),accent);
    }else{
     int length=(int)(max*growth);
     int lineStart=c.effect.equals("double_rule")?(max-length)/2:0;
     ctx.method_25294(lineStart,bottom-2,lineStart+length,bottom-1,accent);
     if(c.effect.equals("double_rule"))ctx.method_25294(lineStart,-5,lineStart+length,-4,argb(alpha*.5f,c.color));
    }
    int textColor=c.effect.equals("warm_settle")&&age<9?0xffffff:0xfff3df;
    glyphs(ctx,c.text,0,0,alpha,textColor,age,c.effect);
    m.method_22904(0,13,0);m.method_22905(.76f,.76f,1);
    glyphs(ctx,c.translation,0,0,alpha*PipelineFX.clamp((age-2)/5),0xcbdde1,age,"fade");
   }finally{m.method_22909();}
  }
  peak=Math.max(peak,remaining);
 }
 static void save(){try{
  Files.createDirectories(PipelineFX.output);var o=new JsonObject();o.addProperty("run",run);o.addProperty("failed",failed);o.addProperty("captionFrames",frames);o.addProperty("peakConcurrentCues",peak);o.addProperty("remainingCues",remaining);o.addProperty("fixedAnchorViolations",anchorViolations);o.addProperty("hudHidden",PipelineFX.client!=null&&PipelineFX.client.field_1690.field_1842);o.add("seenCues",new Gson().toJsonTree(seen));o.add("anchors",new Gson().toJsonTree(anchors));
  String json=new GsonBuilder().setPrettyPrinting().create().toJson(o);Files.writeString(PipelineFX.output.resolve("captions_runtime.json"),json);Files.writeString(PipelineFX.output.resolve("captions_run"+run+".json"),json);System.out.println("NVSCENE_CAPTIONS_REPORT "+o);
 }catch(Exception e){e.printStackTrace();}}
}
