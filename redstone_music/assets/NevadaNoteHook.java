import java.lang.reflect.Method;

/** Bootstrap-visible trace sink, no Minecraft or ASM compile dependency. */
public final class NevadaNoteHook {
    private static Method gameTime, blockState, allEntities, entityX, entityY, entityZ;
    public static synchronized void note(boolean successful, Object level, Object pos) {
        if (!successful) return;
        try {
            if (gameTime == null) gameTime = level.getClass().getMethod("Z");
            if (blockState == null) blockState = level.getClass().getMethod("a_", Class.forName("jd", false, level.getClass().getClassLoader()));
            if (allEntities == null) allEntities = level.getClass().getMethod("A");
            String camera = "";
            for (Object entity : (Iterable<?>) allEntities.invoke(level)) {
                String type = entity.getClass().getName();
                if (!type.equals("bto") && !type.startsWith("bsq$")) continue;
                if (entityX == null) {
                    entityX = entity.getClass().getMethod("dt");
                    entityY = entity.getClass().getMethod("dv");
                    entityZ = entity.getClass().getMethod("dz");
                }
                camera = "|CAM|"+entityX.invoke(entity)+","+entityY.invoke(entity)+","+entityZ.invoke(entity);
                break;
            }
            System.out.println("NEVADA_NOTE|" + gameTime.invoke(level) + "|" + pos + "|" + blockState.invoke(level, pos) + camera);
        } catch (Exception e) { throw new RuntimeException("Unable to record vanilla event", e); }
    }
}
