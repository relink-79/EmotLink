import os
import subprocess
import sys
import platform

# --- Configuration ---
DEFAULT_ANDROID_STUDIO_PATH = "C:\\Program Files\\Android\\Android Studio"

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
        "underline": "\033[4m",
        "end": "\033[0m",
    }
    color_code = colors.get(color, "")
    print(f"{color_code}{text}{colors['end']}")

def run_command(command, description):
    """Runs a command and prints its description."""
    print_color(f"\n▶️  {description}...", "blue")
    try:
        subprocess.run(command, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print_color("✅  성공!", "green")
        return True
    except subprocess.CalledProcessError as e:
        print_color(f"❌  실패: {e.stderr.decode('utf-8', errors='ignore')}", "red")
        return False

def check_prerequisites():
    """Checks if essential tools like Python and Node.js are installed."""
    print_color("--- 1. 필수 프로그램 설치 확인 ---", "header")
    all_good = True
    if not run_command("python --version", "Python 설치 확인"):
        print_color("Python이 설치되어 있지 않습니다. https://www.python.org/ 에서 설치해주세요.", "yellow")
        all_good = False
    if not run_command("node --version", "Node.js 설치 확인"):
        print_color("Node.js가 설치되어 있지 않습니다. https://nodejs.org/ 에서 설치해주세요.", "yellow")
        all_good = False
    if not run_command("npm --version", "NPM 설치 확인"):
        print_color("NPM이 설치되어 있지 않습니다. Node.js를 설치하면 함께 설치됩니다.", "yellow")
        all_good = False
    
    if not all_good:
        print_color("\n필수 프로그램이 설치되지 않았습니다. 설치 후 다시 실행해주세요.", "red")
        sys.exit(1)
    
    print_color("\n모든 필수 프로그램이 준비되었습니다.", "green")

def setup_java_home_windows():
    """Finds JDK in Android Studio and sets JAVA_HOME on Windows."""
    print_color("\n--- 4. JAVA_HOME 환경 변수 설정 (Windows) ---", "header")
    
    java_home_path = os.environ.get("JAVA_HOME")
    if java_home_path and os.path.exists(java_home_path):
        print_color(f"✅  JAVA_HOME이 이미 설정되어 있습니다: {java_home_path}", "green")
        return

    print_color("JAVA_HOME을 자동으로 설정합니다...", "blue")
    
    jbr_path = os.path.join(DEFAULT_ANDROID_STUDIO_PATH, "jbr")
    if not os.path.exists(jbr_path):
        print_color(f"❌  Android Studio 내장 JDK를 찾을 수 없습니다. ({jbr_path})", "red")
        print_color("안드로이드 스튜디오를 기본 경로에 설치했는지 확인해주세요.", "yellow")
        print_color("만약 다른 경로에 설치했다면, 수동으로 JAVA_HOME을 설정해야 합니다.", "yellow")
        return

    print_color(f"찾은 JDK 경로: {jbr_path}", "green")

    # Set JAVA_HOME
    ps_command_set = f"[System.Environment]::SetEnvironmentVariable('JAVA_HOME', '{jbr_path}', 'User')"
    if run_command(f'powershell -Command "{ps_command_set}"', "JAVA_HOME 설정"):
        
        # Add to Path
        jbr_bin_path = os.path.join(jbr_path, "bin")
        ps_command_path = f"$oldPath = [System.Environment]::GetEnvironmentVariable('Path', 'User'); $newPath = $oldPath + ';{jbr_bin_path}'; [System.Environment]::SetEnvironmentVariable('Path', $newPath, 'User')"
        run_command(f'powershell -Command "{ps_command_path}"', "Path 환경 변수에 JAVA_HOME 추가")
        
        print_color("\n🎉 JAVA_HOME 설정이 완료되었습니다! 🎉", "bold")
        print_color("------------------------------------------------------------------", "yellow")
        print_color("중요: 변경사항을 적용하려면 모든 터미널과 에디터를 완전히 종료한 후,", "yellow")
        print_color("      다시 실행해주세요!", "yellow")
        print_color("------------------------------------------------------------------", "yellow")

def create_local_properties_windows():
    """Creates the local.properties file for Android SDK location."""
    print_color("\n--- 5. Android SDK 위치 설정 (Windows) ---", "header")
    
    android_dir = os.path.join(os.getcwd(), 'android')
    local_properties_path = os.path.join(android_dir, 'local.properties')

    if os.path.exists(local_properties_path):
        with open(local_properties_path, 'r') as f:
            if 'sdk.dir' in f.read():
                print_color("✅  android/local.properties 파일에 SDK 경로가 이미 설정되어 있습니다.", "green")
                return

    # Find SDK path
    sdk_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Android', 'Sdk')

    if not os.path.exists(sdk_path):
        print_color(f"❌  Android SDK를 기본 경로에서 찾을 수 없습니다: {sdk_path}", "red")
        print_color("Android Studio를 열고 SDK Manager에서 SDK를 설치했는지 확인해주세요.", "yellow")
        print_color("만약 다른 경로에 설치했다면, 수동으로 android/local.properties 파일을 만들어주세요.", "yellow")
        print_color("파일 내용: sdk.dir=C:\\\\Users\\\\your_username\\\\AppData\\\\Local\\\\Android\\\\Sdk (경로에 맞게 수정)", "yellow")
        return

    print_color(f"찾은 Android SDK 경로: {sdk_path}", "green")
    
    # Escape backslashes for the properties file
    sdk_path_escaped = sdk_path.replace('\\', '\\\\')
    content = f"\nsdk.dir={sdk_path_escaped}\n"
    
    try:
        if not os.path.exists(android_dir):
            os.makedirs(android_dir)
        with open(local_properties_path, 'a') as f:
            f.write(content)
        print_color("✅  android/local.properties 파일 생성 및 SDK 경로 추가 성공!", "green")
    except Exception as e:
        print_color(f"❌  파일 생성 실패: {e}", "red")


def main():
    """Main setup script execution."""
    print_color("==================================================", "header")
    print_color("🚀  EmotLink 개발 환경 자동 설정 스크립트 🚀", "header")
    print_color("==================================================", "header")

    # 1. Check prerequisites
    check_prerequisites()

    # 2. Install Python dependencies
    if not run_command(f"{sys.executable} -m pip install -r requirements.txt", "Python 라이브러리 설치"):
        sys.exit(1)
        
    # 3. Install Node.js dependencies
    if not run_command("npm install", "Node.js (Capacitor) 라이브러리 설치"):
        sys.exit(1)

    # 4. Set JAVA_HOME (for Windows)
    if platform.system() == "Windows":
        setup_java_home_windows()
        create_local_properties_windows()
    else:
        print_color("\n--- 4. JAVA_HOME 환경 변수 설정 ---", "header")
        print_color("현재 운영체제는 Windows가 아닙니다. JAVA_HOME을 수동으로 설정해주세요.", "yellow")

    print_color("\n\n✨ 모든 설정이 성공적으로 완료되었습니다! ✨", "bold")
    print_color("터미널을 다시 시작한 후, 프로젝트를 실행해주세요.", "green")

if __name__ == "__main__":
    main() 