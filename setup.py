"""Include host-neutral skills, schemas and examples in installed wheels."""
from pathlib import Path
import shutil
from setuptools import setup
from setuptools.command.build_py import build_py


class KitBuild(build_py):
    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        target = Path(self.build_lib) / 'redstone_music/kit_data'
        target.mkdir(parents=True, exist_ok=True)
        for name in ('skills', 'schemas', 'profiles', 'templates', 'docs', 'examples', 'client', 'integrations', 'agents'):
            if (root/name).is_dir():
                shutil.copytree(root/name, target/name, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.gradle', 'build', '*.pyc', 'node_modules'))
        for name in ('START_HERE.md', 'README.md', 'AGENTS.md', 'PIPELINE.md', 'PIPELINE_VERIFICATION.md', 'THIRD_PARTY.md', 'LICENSE', 'run_pipeline.py', 'pyproject.toml', 'setup.py', 'MANIFEST.in', 'requirements.txt', '.gitignore', '.gitattributes'):
            if (root/name).is_file():
                shutil.copyfile(root/name, target/name)


setup(cmdclass={'build_py': KitBuild})
