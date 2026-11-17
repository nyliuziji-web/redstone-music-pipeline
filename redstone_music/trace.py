"""Build the test-only 1.21.1 event recorder from source, using a local ASM JAR."""
import argparse
from pathlib import Path
import shutil
import subprocess


def build(jdk,asm,out):
    jdk=Path(jdk).resolve(strict=True);asm=Path(asm).resolve(strict=True);out=Path(out).resolve()
    if out.exists():raise ValueError('Refuse to overwrite a trace build')
    java_bin=jdk/'bin' if (jdk/'bin').is_dir() else jdk
    suffix='.exe' if (java_bin/'javac.exe').is_file() else ''
    javac=java_bin/('javac'+suffix);jar=java_bin/('jar'+suffix)
    out.mkdir(parents=True);classes=out/'classes';classes.mkdir()
    assets=Path(__file__).parent/'assets'
    subprocess.run([str(javac),'-encoding','UTF-8','-cp',str(asm),'-d',str(classes),str(assets/'NevadaTrace.java'),str(assets/'NevadaNoteHook.java')],check=True,capture_output=True)
    manifest=out/'trace.mf';manifest.write_text('Premain-Class: NevadaTrace\nClass-Path: asm.jar\n\n',encoding='utf-8')
    subprocess.run([str(jar),'cfm',str(out/'nevada-trace.jar'),str(manifest),'-C',str(classes),'.'],check=True,capture_output=True)
    subprocess.run([str(jar),'cf',str(out/'nevada-hook.jar'),'-C',str(classes),'NevadaNoteHook.class'],check=True,capture_output=True)
    shutil.copyfile(asm,out/'asm.jar')
    return {'traceAgent':str(out/'nevada-trace.jar'),'traceHook':str(out/'nevada-hook.jar'),'asmJar':str(out/'asm.jar'),'scope':'test observer for Java 1.21.1; not a musical playback layer'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--jdk',required=True);parser.add_argument('--asm',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args(argv)
    return build(args.jdk,args.asm,args.out)
