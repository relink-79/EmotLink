import os
import subprocess
import sys
import platform
import json
import socket
import threading
import time

# --- Configuration ---
CAPACITOR_CONFIG_PATH = "capacitor.config.json"
DEFAULT_URL = "http://127.0.0.1:8000"

# --- Helper Functions ---
def print_color(text, color=""):
    """Prints text in a given color."""
    colors = {
        "header": "\033[95m",
        "blue": "\033[94m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "bold": "\033[1m",
        "end": "\033[0m",
    }
    color_code = colors.get(color, "")
    print(f"{color_code}{text}{colors['end']}")

def get_local_ip():
    """Attempts to find the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def update_capacitor_config(url):
    """Updates the server URL in the capacitor config file."""
    try:
        with open(CAPACITOR_CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        config['server']['url'] = url
        
        with open(CAPACITOR_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
            
        print_color(f"✅  Capacitor 설정 업데이트: server.url -> {url}", "green")
        return True
    except Exception as e:
        print_color(f"❌  Capacitor 설정 파일 업데이트 실패: {e}", "red")
        return False

def run_server():
    """Runs the FastAPI server in a separate process."""
    print_color("\n▶️  FastAPI 웹 서버를 시작합니다 (백그라운드)...", "blue")
    # Using 0.0.0.0 to be accessible from the network
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "webserver.main:app", "--host", "0.0.0.0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # Give the server a moment to start
    time.sleep(3)
    print_color("✅  웹 서버 실행 완료!", "green")
    return server_process

def main():
    print_color("==============================================", "header")
    print_color("🚀  EmotLink 모바일 앱 실행 스크립트 🚀", "header")
    print_color("==============================================", "header")

    # 1. Get local IP and set the target URL
    local_ip = get_local_ip()
    target_url = f"http://{local_ip}:8000"
    print_color(f"\n--- 1. IP 주소 감지 ---", "header")
    print_color(f"자동으로 감지된 IP 주소: {local_ip}", "yellow")

    # 2. Update capacitor.config.json temporarily
    print_color(f"\n--- 2. Capacitor 설정 ---", "header")
    if not update_capacitor_config(target_url):
        sys.exit(1)

    server_process = None
    try:
        # 3. Run the FastAPI server in the background
        print_color(f"\n--- 3. 웹 서버 실행 ---", "header")
        server_process = run_server()
        
        # 4. Run the capacitor app
        print_color(f"\n--- 4. Android 앱 빌드 및 실행 ---", "header")
        print_color("Android Studio를 실행합니다. 잠시만 기다려주세요...", "blue")
        
        command_to_run = "npx cap run android"
        if platform.system() != "Windows":
             # For macOS/Linux, it's better to provide args as a list
             command_to_run = ["npx", "cap", "run", "android"]
        
        subprocess.run(command_to_run, shell=True if platform.system() == "Windows" else False, check=True)

    except KeyboardInterrupt:
        print_color("\n\n🛑  실행 중단. 정리 작업을 시작합니다...", "yellow")
    except Exception as e:
        print_color(f"\n\n❌  오류 발생: {e}", "red")
    finally:
        # 5. Clean up
        print_color(f"\n--- 5. 정리 작업 ---", "header")
        if server_process:
            print_color("▶️  백그라운드 웹 서버를 종료합니다...", "blue")
            server_process.terminate()
            print_color("✅  서버 종료 완료.", "green")
        
        print_color("▶️  Capacitor 설정을 원래대로 되돌립니다...", "blue")
        update_capacitor_config(DEFAULT_URL)
        
        print_color("\n✨ 모든 작업이 깨끗하게 정리되었습니다. ✨", "bold")


if __name__ == "__main__":
    main() 