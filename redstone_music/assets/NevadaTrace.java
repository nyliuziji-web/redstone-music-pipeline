import java.lang.instrument.*;
import java.security.ProtectionDomain;
import java.lang.reflect.Method;
import org.objectweb.asm.*;

/** Test-only observer: logs successful vanilla note-block block events. */
public final class NevadaTrace {
    private static Method gameTime, blockState;
    public static void premain(String args, Instrumentation instrumentation) {
        try { instrumentation.appendToBootstrapClassLoaderSearch(new java.util.jar.JarFile("nevada-hook.jar")); }
        catch (Exception e) { throw new RuntimeException(e); }
        instrumentation.addTransformer(new ClassFileTransformer() {
            @Override public byte[] transform(ClassLoader loader, String name, Class<?> cls,
                    ProtectionDomain domain, byte[] bytes) {
                if (!"dlh".equals(name)) return null; // Mojang official 1.21.1 mapping: NoteBlock
                ClassReader reader = new ClassReader(bytes);
                ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
                reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
                    @Override public MethodVisitor visitMethod(int access, String name, String desc,
                            String signature, String[] exceptions) {
                        MethodVisitor base = super.visitMethod(access, name, desc, signature, exceptions);
                        if (!name.equals("a") || !desc.endsWith("Ldcw;Ljd;II)Z")) return base;
                        System.out.println("NEVADA_TRACE_INSTALLED " + desc);
                        return new MethodVisitor(Opcodes.ASM9, base) {
                            @Override public void visitInsn(int opcode) {
                                if (opcode == Opcodes.IRETURN) {
                                    super.visitInsn(Opcodes.DUP);
                                    super.visitVarInsn(Opcodes.ALOAD, 2);
                                    super.visitVarInsn(Opcodes.ALOAD, 3);
                                    super.visitMethodInsn(Opcodes.INVOKESTATIC, "NevadaNoteHook", "note",
                                        "(ZLjava/lang/Object;Ljava/lang/Object;)V", false);
                                }
                                super.visitInsn(opcode);
                            }
                        };
                    }
                }, 0);
                return writer.toByteArray();
            }
        });
    }
    public static synchronized void note(boolean successful, Object level, Object pos) {
        if (!successful) return;
        try {
            if (gameTime == null) gameTime = level.getClass().getMethod("Z");
            if (blockState == null) blockState = level.getClass().getMethod("a_", Class.forName("jd", false, level.getClass().getClassLoader()));
            System.out.println("NEVADA_NOTE|" + gameTime.invoke(level) + "|" + pos + "|" + blockState.invoke(level, pos));
        } catch (Exception e) {
            throw new RuntimeException("Unable to record vanilla event", e);
        }
    }
}
