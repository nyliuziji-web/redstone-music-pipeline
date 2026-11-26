package dev.redstone.show;

import com.google.gson.*;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandManager;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandRegistrationCallback;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.particle.Particle;
import net.minecraft.nbt.NbtCompound;
import net.minecraft.particle.DustParticleEffect;
import net.minecraft.text.Text;
import net.minecraft.util.Identifier;
import org.joml.Vector3f;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Reference renderer: deterministic geometry evaluated against the physical machine's music clock.
 * No music is generated or played by this client. Integrated single-player server only.
 */
public final class MusicShowClient implements ClientModInitializer {
    private JsonObject show;
    private final List<Particle> owned = new ArrayList<>();
    private int run = -1, q = -1, emitted = 0, peak = 0;
    private boolean captions = true;
    private Path config;

    @Override public void onInitializeClient() {
        config = MinecraftClient.getInstance().runDirectory.toPath().resolve("config/redstone_music/show_score.json");
        load();
        ClientTickEvents.END_CLIENT_TICK.register(this::tick);
        ClientCommandRegistrationCallback.EVENT.register((dispatcher, access) -> dispatcher.register(
            ClientCommandManager.literal("rmp")
                .then(ClientCommandManager.literal("reload").executes(context -> {
                    clear(); run=-1; load(); context.getSource().sendFeedback(Text.literal("Redstone Music show reloaded")); return 1;
                }))
                .then(ClientCommandManager.literal("status").executes(context -> {
                    String status="{\"loaded\":"+(show!=null)+",\"musicGT\":"+q+",\"run\":"+run+
                        ",\"activeParticles\":"+owned.size()+",\"emitted\":"+emitted+",\"peakParticles\":"+peak+"}";
                    context.getSource().sendFeedback(Text.literal(status));System.out.println("RMP_SHOW_STATUS "+status);return 1;
                }))));
        HudRenderCallback.EVENT.register((draw, tick) -> {
            MinecraftClient mc = MinecraftClient.getInstance();
            if (show == null || q < 0 || !captions || !show.has("captions")) return;
            for (JsonElement item : show.getAsJsonArray("captions")) {
                JsonObject cue=item.getAsJsonObject();
                if (q>=i(cue,"begin",0) && q<i(cue,"end",0)) {
                    String text=cue.get("text").getAsString();
                    int x=(int)(f(cue,"x",.5f)*mc.getWindow().getScaledWidth());
                    int y=(int)(f(cue,"y",.8f)*mc.getWindow().getScaledHeight());
                    draw.drawTextWithShadow(mc.textRenderer,text,x-mc.textRenderer.getWidth(text)/2,y,0xFFF1D2);
                }
            }
        });
    }

    private void load() {
        try {
            String text;
            if (Files.isRegularFile(config)) {
                if(Files.size(config)>16*1024*1024)throw new IllegalArgumentException("Show score exceeds 16MiB");
                text=Files.readString(config);
            }
            else try(var input=getClass().getResourceAsStream("/assets/redstone_music/show_score.json")) {
                if(input==null) throw new IllegalArgumentException("Missing embedded show score");
                text=new String(input.readAllBytes(),StandardCharsets.UTF_8);
            }
            JsonObject candidate=JsonParser.parseString(text).getAsJsonObject();
            if(i(candidate,"schemaVersion",0)!=1 || !candidate.get("clock").getAsString().equals("musicGT"))
                throw new IllegalArgumentException("Unsupported show schema");
            validate(candidate);
            show=candidate;
        } catch(Exception e) { show=null; System.err.println("RMP_SHOW_LOAD_FAILED: "+e); }
    }

    private void clearParticles() {for(Particle p:owned)p.markDead();owned.clear();}
    private void clear() {
        if(q>=0)System.out.println("RMP_SHOW_STOP run="+run+" q="+q+" emitted="+emitted+" peak="+peak);
        clearParticles();q=-1;
    }

    private void tick(MinecraftClient mc) {
        if(show==null || mc.world==null || mc.getServer()==null) {clear(); return;}
        // Read storage on the server thread. Rendering consumes only a detached snapshot.
        var server=mc.getServer();var world=mc.world;JsonObject score=show;
        server.execute(() -> {
            NbtCompound state=server.getDataCommandStorage().get(Identifier.of(score.get("namespace").getAsString(),"fx")).copy();
            mc.execute(() -> {if(mc.world==world && show==score)apply(mc,state);});
        });
    }

    private static void validate(JsonObject score) {
        int length=i(score,"lengthGT",0);
        if(length<1 || length>144000 || !score.get("namespace").getAsString().matches("[a-z0-9_.-]+"))
            throw new IllegalArgumentException("Invalid show duration or namespace");
        JsonArray effects=score.getAsJsonArray("effects");
        if(effects.size()>20000)throw new IllegalArgumentException("Too many effects");
        Set<String> ids=new HashSet<>();
        for(JsonElement item:effects) {
            JsonObject e=item.getAsJsonObject();String kind=e.get("kind").getAsString();
            if(!ids.add(e.get("id").getAsString()) || !Set.of("node","ring","helix","bezier").contains(kind))
                throw new IllegalArgumentException("Duplicate effect id or unsupported geometry");
            int begin=i(e,"beginGT",-1),end=i(e,"endGT",-1),points=i(e,"points",24);
            if(begin<0 || end<=begin || end>length || points<4 || points>96 || !e.get("color").getAsString().matches("[0-9a-fA-F]{6}"))
                throw new IllegalArgumentException("Invalid effect time, point count or color");
            vector(e.getAsJsonArray("position"));
            bounded(e,"radius",1,.01f,32);bounded(e,"height",3,0,64);bounded(e,"size",.65f,.1f,4);
            if(kind.equals("bezier")) {
                JsonArray controls=e.getAsJsonArray("controlPoints");
                if(controls.size()!=4)throw new IllegalArgumentException("Bezier requires four control points");
                for(JsonElement control:controls)vector(control.getAsJsonArray());
            }
        }
        if(score.has("captions")) {
            JsonArray cues=score.getAsJsonArray("captions");
            if(cues.size()>2000)throw new IllegalArgumentException("Too many captions");
            for(JsonElement item:cues) {
                JsonObject cue=item.getAsJsonObject();int begin=i(cue,"begin",-1),end=i(cue,"end",-1);
                if(begin<0 || end<=begin || end>length || cue.get("text").getAsString().length()>2000)
                    throw new IllegalArgumentException("Invalid caption");
                bounded(cue,"x",.5f,0,1);bounded(cue,"y",.8f,0,1);
            }
        }
    }
    private static void vector(JsonArray p) {
        if(p.size()!=3)throw new IllegalArgumentException("Position requires three coordinates");
        for(JsonElement v:p)if(!Double.isFinite(v.getAsDouble()) || Math.abs(v.getAsDouble())>30000000)
            throw new IllegalArgumentException("Invalid coordinate");
    }
    private static void bounded(JsonObject object,String key,float value,float lo,float hi) {
        float n=f(object,key,value);
        if(!Float.isFinite(n) || n<lo || n>hi)throw new IllegalArgumentException("Invalid "+key);
    }

    private void apply(MinecraftClient mc,NbtCompound state) {
        if(mc.world==null || show==null) {clear();return;}
        int nextRun=state.getInt("run");
        if(nextRun!=run) {clear();run=nextRun;emitted=0;peak=0;System.out.println("RMP_SHOW_RUN run="+run);}
        if(state.getInt("playing")!=2 || state.getInt("sample")!=i(show,"sampleKey",5)) {clear();return;}
        int next=state.getInt("q")-1;
        if(next<0 || next>=i(show,"lengthGT",1)) {clear();return;}
        clearParticles();q=next;captions=state.getInt("subtitles")==1;
        if(state.getInt("enabled")!=1)return;
        for(JsonElement item:show.getAsJsonArray("effects")) {
            JsonObject effect=item.getAsJsonObject(); int begin=i(effect,"beginGT",0),end=i(effect,"endGT",0);
            if(q<begin || q>=end)continue;
            float u=(q-begin)/(float)Math.max(1,end-begin);
            int count=Math.max(4,Math.min(96,i(effect,"points",24)));
            int rgb=Integer.parseInt(effect.get("color").getAsString(),16);
            Vector3f color=new Vector3f(((rgb>>16)&255)/255f,((rgb>>8)&255)/255f,(rgb&255)/255f);
            DustParticleEffect type=new DustParticleEffect(color,f(effect,"size",.65f));
            for(int j=0;j<count && owned.size()<1200;j++) {
                double[] p=point(effect,u,j,count);
                Particle particle=mc.particleManager.addParticle(type,p[0],p[1],p[2],0,0,0);
                if(particle!=null) {particle.setMaxAge(2);owned.add(particle);emitted++;}
            }
        }
        peak=Math.max(peak,owned.size());
    }

    private static double[] point(JsonObject e,float u,int j,int n) {
        JsonArray p=e.getAsJsonArray("position");double x=p.get(0).getAsDouble(),y=p.get(1).getAsDouble(),z=p.get(2).getAsDouble();
        double radius=f(e,"radius",1),theta=j*Math.PI*2/n;
        return switch(e.get("kind").getAsString()) {
            case "node" -> {double r=radius*(.4+.6*Math.sin(Math.PI*u));yield new double[]{x+r*Math.cos(theta),y+r*Math.sin(theta),z};}
            case "ring" -> {double r=radius*(.1+u);yield new double[]{x+r*Math.cos(theta),y,z+r*Math.sin(theta)};}
            case "helix" -> {double a=theta*2+u*Math.PI*2;yield new double[]{x+radius*Math.cos(a),y+j*f(e,"height",3)/n,z+radius*Math.sin(a)};}
            case "bezier" -> {
                double t=Math.clamp(u-.3+j*.3/Math.max(1,n-1),0,1),v=1-t;JsonArray c=e.getAsJsonArray("controlPoints");
                double[] r=new double[3];for(int k=0;k<3;k++)r[k]=v*v*v*c.get(0).getAsJsonArray().get(k).getAsDouble()+3*v*v*t*c.get(1).getAsJsonArray().get(k).getAsDouble()+3*v*t*t*c.get(2).getAsJsonArray().get(k).getAsDouble()+t*t*t*c.get(3).getAsJsonArray().get(k).getAsDouble();yield r;
            }
            default -> new double[]{x,y,z};
        };
    }
    private static int i(JsonObject e,String k,int d){return e.has(k)?e.get(k).getAsInt():d;}
    private static float f(JsonObject e,String k,float d){return e.has(k)?e.get(k).getAsFloat():d;}
}
