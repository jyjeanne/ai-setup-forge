"""Check if uv is installed and install it if missing."""
import subprocess
import sys

def is_uv_installed():
    """Check if uv is available in PATH."""
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False

def install_uv():
    """Install uv using pip."""
    print("Installing uv...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "uv"],
            check=True
        )
        print("uv installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install uv: {e}")
        return False

def main():
    if is_uv_installed():
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True
        )
        print(f"uv is already installed: {result.stdout.strip()}")
    else:
        print("uv is not installed")
        install_uv()

if __name__ == "__main__":
    main()
