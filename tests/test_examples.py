from pathlib import Path
import pytest
import subprocess

example_scripts = (Path(__file__).parent.parent / "examples").glob("*.py")


@pytest.mark.parametrize("script", example_scripts)
def test_example_script(script):
    subprocess.run([script], check=True)
