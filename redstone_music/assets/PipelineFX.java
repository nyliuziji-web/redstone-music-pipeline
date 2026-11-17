package dev.redstone.pipeline;

import com.google.gson.*;
import com.mojang.blaze3d.systems.RenderSystem;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.rendering.v1.*;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.*;
import net.minecraft.server.MinecraftServer;
import org.joml.*;
import java.lang.Math;
import java.nio.file.*;
import java.util.*;

/** Deterministic note impacts + continuous ribbons, single-player sample adapter.
 * Geometry is evaluated at render time, not emitted as overlapping full curves each tick.
 */
public final class PipelineFX implements ClientModInitializer {
 record State(int playing,int enabled,int q,int run,int sample,long at){}
 record Note(String id,String parent,String family,int q,int end,int midi,float gain,float x,float y,float z){}
 record Transition(String id,int q,int begin,int end,String kind){}
 record Section(String name,int begin,int end,String focus,float intensity,float width){}
 record Sample(int key,int length,List<Note> notes,List<Transition> transitions,List<Section> sections){}
 static volatile State state=new State(0,0,-70,0,0,System.nanoTime());
 static final Map<Integer,Sample> samples=new HashMap<>();
 static final Set<String> seen=new HashSet<>();
 static final Map<String,Integer> counts=new TreeMap<>();
 static final List<Double> frameTimes=new ArrayList<>();
 static final Set<Integer> screenshots=new HashSet<>();
 static final Map<String,Integer> sectionFrames=new LinkedHashMap<>();
 static final Set<String> macrosSeen=new LinkedHashSet<>();
 static Section section=new Section("INTRO",0,4175,"theme",1,1);
 static final int GOLD=0xffcd74,BLUE=0x41cfff,PURPLE=0xca7dff;
 static class_310 client;static int run=-1,sampleKey=-1,peakImpacts=0,peakQuads=0,quads=0,lastQ=-70,activeEffects=0;
 static boolean failed=false,wasActive=false;static long lastFrame=0;static int renderFrames=0;
 static Path output=Path.of(System.getProperty("nvfx.output","config/redstone_music"));
 static class_287 buffer;static Matrix4f matrix;static Vector3f camera;
 static int autoStage=0,autoRuns=0;static boolean abortSent=false;static long readyAt=0;
 public void onInitializeClient(){
  try(var in=PipelineFX.class.getResourceAsStream("/assets/redstone_music/show_full.json")){
   JsonObject all=JsonParser.parseString(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
   for(var entry:all.entrySet()){
    JsonObject data=entry.getValue().getAsJsonObject();List<Note> notes=new ArrayList<>();List<Transition> ts=new ArrayList<>();
    for(JsonElement element:data.getAsJsonArray("notes")){JsonObject n=element.getAsJsonObject();notes.add(new Note(n.get("id").getAsString(),n.get("parentId").getAsString(),n.get("family").getAsString(),i(n,"q"),i(n,"end"),i(n,"midi"),f(n,"gain"),f(n,"x"),f(n,"y"),f(n,"z")));}
    for(JsonElement element:data.getAsJsonArray("transitions")){JsonObject t=element.getAsJsonObject();ts.add(new Transition(t.get("id").getAsString(),i(t,"q"),i(t,"begin"),i(t,"end"),t.get("kind").getAsString()));}
    List<Section> sections=new ArrayList<>();
    for(JsonElement element:data.getAsJsonArray("sections")){JsonObject z=element.getAsJsonObject();sections.add(new Section(z.get("name").getAsString(),i(z,"begin"),i(z,"end"),z.get("focus").getAsString(),f(z,"intensity"),f(z,"widthScale")));}
    int key=Integer.parseInt(entry.getKey());samples.put(key,new Sample(key,i(data,"length"),notes,ts,sections));
   }
  }catch(Exception e){throw new RuntimeException("Cannot load v02 visual score",e);}
  ServerTickEvents.END_SERVER_TICK.register(server->{
   class_2487 tag=server.method_22827().method_22546(class_2960.method_60655("_NAMESPACE_","fx"));
   state=new State(tag.method_10550("playing"),tag.method_10550("enabled"),tag.method_10550("q"),tag.method_10550("run"),tag.method_10550("sample"),System.nanoTime());
   PipelineCaptions.enabled=tag.method_10550("subtitles")==1;
   if(Boolean.getBoolean("nvfx.autotest"))autoTest(server);
  });
  PipelineCaptions.register();
  ClientTickEvents.END_CLIENT_TICK.register(PipelineFX::tick);
  WorldRenderEvents.LAST.register(PipelineFX::render);
  WorldRenderEvents.END.register(ctx->{recordFrame();if(Boolean.getBoolean("nvfx.autotest"))try{capture();}catch(Exception e){e.printStackTrace();}});
  System.out.println("NVFX_FULL_READY samples="+samples.size());
 }
 static int i(JsonObject o,String k){return o.get(k).getAsInt();}static float f(JsonObject o,String k){return o.get(k).getAsFloat();}
 static float clamp(float t){return Math.max(0,Math.min(1,t));}static float ease(float t){return 1-(float)Math.pow(1-clamp(t),3);}
 static float clock(){State s=state;return s.q-1+clamp((System.nanoTime()-s.at)/50_000_000f);}
 static boolean core(Note n){return n.family.equals("voice")||n.family.equals("theme_attack")||n.family.equals("theme_body")||n.family.equals("piano");}
 static int rgb(Note n){return n.family.equals("voice")?GOLD:n.family.equals("theme_attack")?BLUE:n.family.equals("theme_body")?PURPLE:n.family.equals("piano")?0xc5e6ff:0xb0c8df;}
 static void tick(class_310 mc){
  client=mc;if(Boolean.getBoolean("nvfx.autotest"))mc.field_1690.field_1842=true;
  State s=state;
  if(mc.field_1687==null){if(wasActive){clear();saveReport();wasActive=false;}return;}
  if(mc.field_1724!=null&&s.playing==2){var focus=mc.field_1773.method_19418().method_19331();if(focus!=null&&focus!=mc.field_1724)mc.field_1724.method_5814(focus.method_23317(),focus.method_23318()-1.62,focus.method_23321());}
  if(s.run!=run||s.sample!=sampleKey){clear();seen.clear();counts.clear();screenshots.clear();sectionFrames.clear();macrosSeen.clear();frameTimes.clear();renderFrames=0;peakQuads=0;peakImpacts=0;lastFrame=0;run=s.run;sampleKey=s.sample;}
  boolean active=s.playing==2&&s.enabled==1&&samples.containsKey(s.sample)&&!failed;
  if(s.playing==2)lastQ=s.q;
  if(!active){if(wasActive){clear();saveReport();}wasActive=false;return;}wasActive=true;
  for(Note n:samples.get(s.sample).notes)if(n.q<=s.q-1&&seen.add(n.id)){
   counts.merge(n.family,1,Integer::sum);
   System.out.println("NVFX_FULL_ONSET|"+run+"|"+s.sample+"|"+n.q+"|"+n.family+"|"+n.id);
  }
 }
 static Vector3f v(float x,float y,float z){return new Vector3f(x,y,z);}
 static Vector3f bez(Vector3f a,Vector3f b,Vector3f c,Vector3f d,float u){float t=1-u;return new Vector3f(a).mul(t*t*t).fma(3*t*t*u,b).fma(3*t*u*u,c).fma(u*u*u,d);}
 static void vertex(Vector3f p,int color,float alpha){
  int argb=((int)(255*clamp(alpha))<<24)|(color&0xffffff);
  buffer.method_22918(matrix,p.x-camera.x,p.y-camera.y,p.z-camera.z).method_39415(argb);
 }
 static void quad(Vector3f a,Vector3f b,Vector3f c,Vector3f d,int color,float alpha){alpha*=section.intensity;if(alpha<.008f)return;vertex(a,color,alpha);vertex(b,color,alpha);vertex(c,color,alpha);vertex(d,color,alpha);quads++;}
 static void strip(List<Vector3f> points,float width,int color,float alpha,boolean taper){
  if(points.size()<2||alpha<.008f)return;
  Vector3f prev=null;
  for(int j=1;j<points.size();j++){
   Vector3f a=points.get(j-1),b=points.get(j),tangent=new Vector3f(b).sub(a);if(tangent.lengthSquared()<1e-8)continue;
   Vector3f view=new Vector3f(camera).sub(a),normal=tangent.cross(view,new Vector3f());if(normal.lengthSquared()<1e-8)normal.set(1,0,0);normal.normalize();
   if(prev!=null&&prev.dot(normal)<0)normal.negate();
   Vector3f na=prev==null?normal:prev;
   float wa=width*.5f,wb=wa,fade=1;
   if(taper){wa*=.12f+.88f*(j-1)/(points.size()-1f);wb*=.12f+.88f*j/(points.size()-1f);fade=.15f+.85f*j/(points.size()-1f);}
   quad(new Vector3f(a).fma(wa,na),new Vector3f(a).fma(-wa,na),new Vector3f(b).fma(-wb,normal),new Vector3f(b).fma(wb,normal),color,alpha*fade);
   prev=normal;
  }
 }
 static void stroke(List<Vector3f> p,float width,int color,float alpha){strip(p,width*2.7f,color,alpha*.11f,false);strip(p,width,color,alpha,false);}
 static void ribbon(List<Vector3f> p,int color,float alpha,float width){
  width*=section.width;
  strip(p,width*2.1f,color,alpha*.11f,true);strip(p,width,color,alpha*.68f,true);strip(p,.13f,0xfff5e3,alpha*.9f,true);
  for(int side:new int[]{-1,1}){List<Vector3f> edge=new ArrayList<>();for(int j=0;j<p.size();j++){float u=j/(p.size()-1f);Vector3f pt=new Vector3f(p.get(j));pt.y+=side*width*.40f+side*.045f*(float)Math.sin(u*22+clock()*.10);edge.add(pt);}strip(edge,.055f,color,alpha*.8f,true);}
 }
 static List<Vector3f> path(Vector3f a,Vector3f b,Vector3f c,Vector3f d,float from,float to){
  int n=Math.max(10,(int)((a.distance(b)+b.distance(c)+c.distance(d))*(to-from)/.22f));n=Math.min(n,260);List<Vector3f> p=new ArrayList<>(n+1);
  for(int j=0;j<=n;j++)p.add(bez(a,b,c,d,from+(to-from)*j/n));return p;
 }
 static void diamond(Vector3f center,float length,float width,float angle,int color,float alpha){
  float ca=(float)Math.cos(angle),sa=(float)Math.sin(angle);
  Vector3f a=new Vector3f(center).add(ca*length,sa*length,0),b=new Vector3f(center).add(-sa*width,ca*width,0),c=new Vector3f(center).add(-ca*length,-sa*length,0),d=new Vector3f(center).add(sa*width,-ca*width,0);
  quad(a,b,c,d,color,alpha);
 }
 static void star(Vector3f center,float size,int color,float alpha){diamond(center,size,size*.18f,0,color,alpha);diamond(center,size,size*.18f,(float)Math.PI/2,color,alpha);diamond(center,size*.3f,size*.3f,0,0xfff9ed,alpha);}
 static Vector3f radial(Vector3f center,float radius,float angle,float flatten,float tilt){float x=radius*(float)Math.cos(angle),y=radius*(float)Math.sin(angle)*flatten;return new Vector3f(center).add(x*(float)Math.cos(tilt)-y*(float)Math.sin(tilt),x*(float)Math.sin(tilt)+y*(float)Math.cos(tilt),0);}
 static void arc(Vector3f center,float radius,float a,float b,float flatten,float tilt,int color,float alpha,float width){List<Vector3f> p=new ArrayList<>();for(int j=0;j<=12;j++)p.add(radial(center,radius,a+(b-a)*j/12,flatten,tilt));stroke(p,width,color,alpha);}
 static void impact(Note n,float age){
  int color=rgb(n);boolean melody=core(n);float forward=n.z-camera.z;
  float near=clamp((forward-3)/3);if(age<0||age>.60f)return;
  float seed=(n.parent.hashCode()&1023)/1023f,rot=seed*.45f;
  Vector3f center=v(n.x,n.y,n.z);
  float strength=.85f+.15f*clamp(n.gain*1.3f),radius=(.2f+1.25f*ease((age-.02f)/.16f))*strength;
  float skeleton=(1-clamp((age-.18f)/.14f))*clamp(age/.025f)*near;
  if(!melody){
   if(age>.30f)return;float fade=(1-age/.3f)*near;
   if(n.family.equals("kick")||n.family.equals("snare")||n.family.equals("mid_bass")||n.family.equals("sub_bass")){
    for(int k=0;k<6;k++){float a=(float)(Math.PI*k/5);List<Vector3f> p=List.of(new Vector3f(center),new Vector3f(center).add((float)Math.cos(a)*radius*1.4f,-.45f,(float)Math.sin(a)*radius));stroke(p,.07f,0xe8b872,fade*.6f);}
   }else star(center,.12f+.12f*(1-age/.3f),color,fade*.55f);
   return;
  }
  if(age<.14f)star(center,.18f+.16f*(1-age/.14f),0xfff6e3,near*(1-age/.14f));
  if(n.family.equals("voice")){
   for(int k=0;k<5;k++){
    float a=(float)(k*Math.PI*2/5)+rot;
    for(int side:new int[]{-1,1}){List<Vector3f> p=new ArrayList<>();for(int j=0;j<=20;j++){float u=j/20f,rr=.12f+(radius-.12f)*(float)Math.sin(u*Math.PI*.5),ang=a+side*.30f*(float)Math.sin(Math.PI*u);p.add(radial(center,rr,ang,1,0));}stroke(p,.065f,color,skeleton);}
    star(radial(center,radius,a,1,0),.085f,color,skeleton*.8f);
   }
   for(int k=0;k<10;k++)arc(center,radius*1.18f,(float)(k*Math.PI*2/10)+rot,(float)(k*Math.PI*2/10)+rot+.24f,1,0,color,skeleton*.65f,.035f);
  }else if(n.family.equals("theme_attack")){
   for(int layer=0;layer<2;layer++)for(int k=0;k<4;k++){
    float a=(float)(k*Math.PI/2)+rot+layer*.39f,rr=radius*(layer==0?1:.77f);Vector3f pa=radial(center,rr,a,1,0),pb=radial(center,rr,a+(float)Math.PI/2,1,0);
    for(float[] span:new float[][]{{0,.38f},{.53f,.94f}})stroke(List.of(new Vector3f(pa).lerp(pb,span[0]),new Vector3f(pa).lerp(pb,span[1])),.075f,color,skeleton);
   }
   for(int k=0;k<6;k++){float a=(float)(k*Math.PI/3)+rot+.18f;stroke(List.of(radial(center,radius*.62f,a,1,0),radial(center,radius*1.5f,a,1,0),radial(center,radius,a+.06f,1,0)),.035f,color,skeleton*.85f);}
  }else if(n.family.equals("piano")){
   for(int k=0;k<3;k++){float a=(float)(k*Math.PI*2/3)+rot;arc(center,radius,a,a+1.35f,.8f,k*.3f,color,skeleton,.065f);star(radial(center,radius,a,1,0),.07f,color,skeleton);}
  }else{
   for(int side:new int[]{-1,1})for(int k=0;k<12;k++){float a=(float)(k*Math.PI/6)+rot+age*2*side;arc(center,radius,a,a+.38f,.46f,side*.55f,color,skeleton,.07f);}
   for(int k=0;k<8;k++){float a=(float)(k*Math.PI/4)+rot+age;star(radial(center,radius*1.12f,a,.83f,0),.07f,color,skeleton*.8f);}
  }
  float split=ease((age-.11f)/.29f),life=clamp((age-.11f)/.47f);
  float alpha=clamp((age-.10f)/.07f)*(float)Math.pow(1-life,.8);
  int count=n.family.equals("piano")?6:n.family.equals("theme_attack")?10:12;
  for(int k=0;k<count;k++){
   float a=(float)(k*Math.PI*2/count)+rot+.2f,curl=n.family.equals("voice")?.32f:n.family.equals("theme_attack")?.07f:.78f,sign=k%2==0?-1:1;
   Vector3f detached=new Vector3f(center).add(0,0,Math.max(0,age-.11f)*12);
   float rr=.65f+1.12f*split,angle=a+curl*split*sign;
   Vector3f tip=radial(detached,rr,angle,1,0);if(n.family.equals("voice"))tip.y+=split*.24f;
   float shardFade=alpha*clamp((tip.z-camera.z-3)/3);
   List<Vector3f> tail=new ArrayList<>();for(int j=0;j<8;j++){float u=Math.max(0,split-.20f+j*.20f/7);tail.add(radial(detached,.65f+1.12f*u,a+curl*u*sign,1,0));}
   strip(tail,.025f,color,shardFade*.6f,true);diamond(tip,.12f+(k%3)*.025f,.035f,angle,color,shardFade);star(tip,.045f,0xfff5e3,shardFade*.85f);
   Vector3f tiny=new Vector3f(tip).add(-.14f*(float)Math.cos(angle)+.07f,-.14f*(float)Math.sin(angle)-.07f,-.04f);diamond(tiny,.04f,.02f,angle,color,shardFade*.5f);
  }
 }
 static Vector3f stage(Note n,float q){
  float x=n.family.equals("voice")?37.0f+Math.max(-1.8f,Math.min(1.8f,(n.midi-65)*.22f)):n.family.equals("theme_attack")?27.5f:n.family.equals("piano")?41.5f:47.0f;
  float y=n.family.equals("voice")?114.5f:n.family.equals("piano")?115.2f:119.0f;
  y+=Math.max(-2,Math.min(3,(n.midi-65)*.18f));
  return v(x,y,camera.z+25);
 }
 static void lead(Note n,Note prev,float q){
  int color=rgb(n);float remaining=n.end-q;if(remaining<0||q<n.q)return;
  float alpha=clamp((q-n.q+1)/2)*clamp((remaining+1)/3);
  if(section.focus.equals("piano")&&!n.family.equals("piano"))alpha*=.5f;
  if(!section.focus.equals("piano")&&n.family.equals("piano"))alpha*=.45f;
  Vector3f head=stage(n,q);
  if(prev!=null){float u=ease((q-n.q)/3);Vector3f old=stage(prev,q);head.lerp(old,1-u);}
  List<Vector3f> tail=new ArrayList<>();for(int j=0;j<=110;j++){float u=j/110f;float spread=n.family.equals("voice")?3.2f:.7f;Vector3f p=new Vector3f(head).add((float)Math.sin(u*5+q*.03f)*u*spread,(float)Math.sin(u*6+q*.03f)*u*(n.family.equals("voice")?1.8f:.75f),27*u);tail.add(p);}Collections.reverse(tail);
  ribbon(tail,color,alpha,.94f);star(head,.26f,color,alpha);
  // Actual node to the persistent stage object: localized support line, quickly fades as node passes.
  float age=(q-n.q)/20,near=clamp((n.z-camera.z-3)/4),connect=near*clamp(1-age/.32f);
  if(connect>0){Vector3f source=v(n.x,n.y,n.z);ribbon(path(source,new Vector3f(source).add(0,2,5),new Vector3f(head).add(0,-1,-5),head,0,1),color,connect*.7f,.55f);}
  if(n.end-n.q>8){float angle=q*.08f;for(int side:new int[]{-1,1})arc(head,.40f,angle*side,angle*side+1.7f,.65f,side*.25f,color,alpha*.6f,.04f);}
 }
 static void transition(Transition t,float q,Map<String,Note> leads){
  if(q<t.begin||q>t.end)return;float u=clamp((q-t.begin)/(t.end-t.begin)),env=(float)Math.sin(Math.PI*u);
  Vector3f middle=v(37.5f,115.5f,camera.z+33);
  macrosSeen.add(t.id);
  if(t.kind.startsWith("split_arch")){
   int layers=t.kind.equals("split_arch2")?3:1;
   for(int layer=0;layer<layers;layer++)for(int side:new int[]{-1,1}){
    Vector3f dest=v(37.5f+side*10,116.5f,camera.z+26);
    float growth=ease((q-t.begin-layer*2)/18);ribbon(path(new Vector3f(middle).add(0,layer*.7f,0),v(37.5f+side*2,126+layer*.8f,camera.z+36),v(37.5f+side*(15+layer*2),125-layer,camera.z+32),new Vector3f(dest).add(side*layer,0,layer),Math.max(0,growth-.9f),growth),side<0?BLUE:PURPLE,env*(layer==0?1:.55f),layer==0?.95f:.4f);
   }
  }else if(t.kind.startsWith("braid")){
   for(int side:new int[]{-1,1}){List<Vector3f> p=new ArrayList<>();for(int j=0;j<=130;j++){float a=j/130f,phase=(float)(a*Math.PI*2)+q*.045f+(side<0?0:(float)Math.PI),extra=t.kind.equals("braid2")?.55f*(float)Math.sin(phase*2):0;p.add(v(24.5f+26*a,118+2.3f*(float)Math.sin(phase)+extra,camera.z+34+2*(float)Math.cos(phase)));}ribbon(p,side<0?BLUE:PURPLE,env*.8f,t.kind.equals("braid2")?.88f:.72f);}
  }else if(t.kind.equals("gather")||t.kind.equals("fold")){
   for(int side:new int[]{-1,1}){Vector3f from=v(37.5f+side*15,115.5f,camera.z+27),to=v(37.5f,121.5f,camera.z+38);float growth=ease(u*1.5f);ribbon(path(from,v(37.5f+side*12,119,camera.z+31),v(37.5f+side*4,126,camera.z+36),to,Math.max(0,growth-.8f),growth),t.kind.equals("fold")?GOLD:side<0?BLUE:PURPLE,env*.8f,.85f);}
  }else if(t.kind.equals("voice_crown")){
   Note voice=leads.get("voice");Vector3f root=voice!=null?stage(voice,q):v(37.5f,115,camera.z+25);
   for(int side:new int[]{-1,1}){Vector3f end=new Vector3f(root).add(side*6,2,10);ribbon(path(root,new Vector3f(root).add(side*2,7,3),new Vector3f(root).add(side*8,7,7),end,0,ease(u*2)),GOLD,env*.75f,.66f);}
  }else if(t.kind.equals("piano_arc")){
   for(int k=0;k<3;k++){Vector3f a=v(38+k*2,114,camera.z+27),b=v(43+k*3,118+k,camera.z+35);ribbon(path(a,new Vector3f(a).add(0,4,3),new Vector3f(b).add(0,3,-2),b,0,ease(u*2)),0xc5e6ff,env*(.6f-k*.12f),.56f-k*.1f);}
  }else if(t.kind.equals("wave")){
   for(int side:new int[]{-1,1}){Vector3f a=v(37.5f-side*11,118,camera.z+32),b=v(37.5f+side*11,118,camera.z+32);ribbon(path(a,v(37.5f-side*5,124,camera.z+35),v(37.5f+side*5,112,camera.z+35),b,Math.max(0,u-.65f),Math.min(1,u+.22f)),side<0?BLUE:PURPLE,env,.66f);}
  }else if(t.kind.equals("sweep")){
   int side=(t.q/38)%2==0?1:-1;Vector3f a=v(37.5f+side*11,118,camera.z+27),b=v(37.5f-side*8,121,camera.z+42);ribbon(path(a,new Vector3f(a).add(-side*3,7,5),new Vector3f(b).add(side*5,4,-3),b,Math.max(0,u-.6f),Math.min(1,u+.2f)),side<0?BLUE:PURPLE,env*.75f,.7f);
  }
 }
 static void render(WorldRenderContext context){
  State s=state;if(client==null||failed||s.playing!=2||s.enabled!=1||!samples.containsKey(s.sample))return;
  try{
   Sample sample=samples.get(s.sample);float q=clock();if(q<0||q>sample.length+12)return;
   for(Section x:sample.sections)if(q>=x.begin&&q<x.end){section=x;break;}
   if(q<sample.length)sectionFrames.merge(section.name,1,Integer::sum);
   class_243 cam=context.camera().method_19326();camera=v((float)cam.field_1352,(float)cam.field_1351,(float)cam.field_1350);matrix=context.matrixStack().method_23760().method_23761();
   RenderSystem.enableBlend();RenderSystem.defaultBlendFunc();RenderSystem.disableCull();RenderSystem.enableDepthTest();RenderSystem.depthMask(false);RenderSystem.setShader(class_757::method_34540);RenderSystem.setShaderColor(1,1,1,1);
   buffer=class_289.method_1348().method_60827(class_293.class_5596.field_27382,class_290.field_1576);quads=0;
   Map<String,Note> leads=new HashMap<>(),previous=new HashMap<>();int impacts=0;
   // Camera-relative ribbons first; world-space impact details remain legible on top.
   for(Note n:sample.notes){if(core(n)&&n.q<=q){Note old=leads.get(n.family);if(old==null||old.q<=n.q){if(old!=null)previous.put(n.family,old);leads.put(n.family,n);}}}
   for(Note n:leads.values())lead(n,previous.get(n.family),q);
   for(Transition t:sample.transitions)transition(t,q,leads);
   Set<String> supportGroups=new HashSet<>(),companionGroups=new HashSet<>();
   for(Note n:sample.notes){float age=(q-n.q)/20;if(age>=0&&age<=.6f){if(core(n)){
    impact(n,age);impacts++;
    // A second, explicitly staged ornament makes low/off-axis note tracks readable.
    // Its birth position is stamped in world space, so it never sticks to the lens.
    if(!companionGroups.add(n.family+"/"+n.q))continue;
    Vector3f stage=stage(n,n.q);
    Note companion=new Note(n.id+"/stage",n.parent,n.family,n.q,n.end,n.midi,n.gain,stage.x,stage.y,93.5f+n.q);
    impact(companion,age);impacts++;
   }else if(supportGroups.add(n.family+"/"+n.q))impact(n,age);}}
   activeEffects=impacts+leads.size();peakImpacts=Math.max(peakImpacts,impacts);peakQuads=Math.max(peakQuads,quads);
   // endNullable is required for silent/fully faded frames; end() throws on empty.
   var built=buffer.method_60794();if(built!=null)class_286.method_43433(built);
  }catch(Throwable e){failed=true;e.printStackTrace();clear();saveReport();}
  finally{RenderSystem.depthMask(true);RenderSystem.enableCull();RenderSystem.disableBlend();}
 }
 static void clear(){activeEffects=0;}
 static void recordFrame(){if(client==null||client.field_1687==null||state.playing!=2||state.q<20||!samples.containsKey(state.sample)||state.q>samples.get(state.sample).length)return;long now=System.nanoTime();if(lastFrame!=0)frameTimes.add((now-lastFrame)/1e6);lastFrame=now;renderFrames++;}
 static void capture()throws Exception{
  if(client==null||client.field_1687==null||state.playing!=2)return;
  for(int shot:new int[]{40,500,900,985,1180,1700,2100,2300,2640,2900,3140,3320,3820,4070})if(state.q>=shot&&screenshots.add(shot)){
   Files.createDirectories(output);class_318.method_22690(output.toFile(),"sample_q"+shot+".png",client.method_1522(),t->{});
   JsonObject r=new JsonObject();r.addProperty("q",state.q);r.addProperty("visualQ",clock());r.addProperty("sample",state.sample);r.addProperty("quads",quads);r.addProperty("ownedEffects",activeEffects);r.addProperty("camera",client.field_1773.method_19418().method_19326().toString());r.addProperty("player",client.field_1724.method_19538().toString());r.addProperty("focus",client.field_1773.method_19418().method_19331().getClass().getName());Files.writeString(output.resolve("scene_q"+shot+".json"),r.toString());
  }
 }
 static void saveReport(){try{
  Files.createDirectories(output);JsonObject r=new JsonObject();r.addProperty("run",run);r.addProperty("sample",sampleKey);r.addProperty("enabled",state.enabled);r.addProperty("onsetsDispatched",seen.size());r.add("byFamily",new Gson().toJsonTree(counts));r.addProperty("peakDetailedImpacts",peakImpacts);r.addProperty("peakQuadsPerFrame",peakQuads);r.addProperty("remainingOwnedEffects",activeEffects);r.addProperty("lastMusicGT",lastQ);r.addProperty("failed",failed);r.addProperty("renderFrames",renderFrames);r.addProperty("shaderEnabled",false);r.addProperty("hiddenWindowTest",Boolean.getBoolean("nvfx.autotest"));r.addProperty("renderer","continuous camera-facing strips and deterministic world-space particle geometry");
  if(!frameTimes.isEmpty()){List<Double> sorted=new ArrayList<>(frameTimes);Collections.sort(sorted);r.addProperty("meanFrameMs",frameTimes.stream().mapToDouble(x->x).average().orElse(0));r.addProperty("p95FrameMs",sorted.get((int)((sorted.size()-1)*.95)));}
  r.add("sectionFrames",new Gson().toJsonTree(sectionFrames));r.add("macrosSeen",new Gson().toJsonTree(macrosSeen));
  String json=new GsonBuilder().setPrettyPrinting().create().toJson(r);
  Files.writeString(output.resolve("show_runtime.json"),json);Files.writeString(output.resolve("show_runtime_run"+run+".json"),json);System.out.println("NVFX_FULL_REPORT "+r);
 }catch(Exception e){e.printStackTrace();}}
 static void command(MinecraftServer s,String c){s.method_3734().method_44252(s.method_3739(),c);}
 static void autoTest(MinecraftServer server){
  State s=state;String mode=System.getProperty("nvfx.mode","on");
  if(autoStage==0&&s.playing==0){if(readyAt==0)readyAt=System.nanoTime();if(System.nanoTime()-readyAt<1_000_000_000L)return;command(server,"time set "+(Boolean.getBoolean("nvfx.daylight")?6000:18000));command(server,"scoreboard players set #fx _OBJECTIVE_ "+(mode.equals("off")?0:1));command(server,"execute as @a at @s run function _NAMESPACE_:start");autoStage=1;System.out.println("NVFX_V02_LAUNCH");}
  else if(autoStage==1&&s.playing==2){autoStage=2;}
  else if(autoStage==2){
   int limit=Integer.getInteger("nvfx.maxGT",-1),abortGT=Integer.getInteger("nvfx.abortGT",620);
   if(((mode.equals("abort")||mode.equals("restart")&&autoRuns==0)&&s.q>=abortGT||limit>=0&&s.q>=limit)&&!abortSent){command(server,"function _NAMESPACE_:stop");abortSent=true;}
   if(s.playing==0){if(mode.equals("restart")&&autoRuns==0){autoRuns=1;autoStage=0;readyAt=0;abortSent=false;}else{autoStage=3;client.execute(()->{saveReport();client.method_1592();});}}
  }
 }
}
