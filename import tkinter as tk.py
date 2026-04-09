import tkinter as tk
from tkinter import scrolledtext
import mss
import mss.tools
from PIL import Image
import google.generativeai as genai
import threading
import os
import re
import time
import sys
from dotenv import load_dotenv

# 현재 실행 중인 스크립트의 디렉토리 경로를 찾습니다.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

env_loaded = False
# 여러 가능한 설정 파일 이름을 확인합니다.
for env_file in [".env.txt", "env.txt", ".env"]:
    env_path = os.path.join(CURRENT_DIR, env_file)
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        print(f"ℹ️ 설정 로드 완료: {env_path}")
        env_loaded = True
        break

if not env_loaded:
    print(f"⚠️ 경고: {CURRENT_DIR} 폴더에서 설정 파일(env.txt 등)을 찾을 수 없습니다.")

class TruthCheckerOverlay:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = None
        
        self.root = tk.Tk()
        self.root.title("AI Screen Fact Checker")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95) # 반투명 느낌을 조금 더 강조
        self.root.geometry("420x650+100+100")
        self.root.configure(bg="#F8F9FA")
        
        self.setup_ui()
        self.initialize_gemini()

    def setup_ui(self):
        """UI 요소 초기화 - 부드럽고 둥근 느낌의 디자인 개선"""
        # 타이틀 섹션
        self.label = tk.Label(self.root, text="✨ AI 실시간 팩트체커", 
                              font=("NanumGothic", 18, "bold"), fg="#4CAF50", bg="#F8F9FA") # 더 부드러운 녹색
        self.label.pack(pady=(25, 10))

        # 상태 표시 바
        status_container = tk.Frame(self.root, bg="#FFFFFF", bd=0, highlightthickness=1, highlightbackground="#CED4DA") # 테두리 색상 살짝 진하게
        status_container.pack(fill=tk.X, padx=30, pady=5)
        
        self.status_label = tk.Label(status_container, text="시스템 준비 중...", 
                                     font=("NanumGothic", 9), bg="#FFFFFF", fg="#6C757D")
        self.status_label.pack(pady=6)

        # 신뢰도 표시 섹션
        self.score_label = tk.Label(self.root, text="신뢰도 점수: --%", font=("NanumGothic", 30, "bold"),
                                    fg="#64B5F6", bg="#F8F9FA") # 텍스트 길이에 맞춰 폰트 크기 조정
        self.score_label.pack(pady=15) # 여백 증가

        # 분석 버튼 (Modern Flat Design)
        self.btn_analyze = tk.Button(self.root, text="🔍 현재 화면 분석하기", command=self.start_analysis_thread, 
                                     bg="#198754", fg="white", font=("NanumGothic", 12, "bold"), 
                                     padx=20, pady=12, cursor="hand2", relief=tk.FLAT,
                                     activebackground="#157347", activeforeground="white")
        self.btn_analyze.pack(pady=20, padx=30, fill=tk.X) # 여백 증가
        self.btn_analyze.bind("<Enter>", lambda e: self.btn_analyze.configure(bg="#157347"))
        self.btn_analyze.bind("<Leave>", lambda e: self.btn_analyze.configure(bg="#198754"))

        # 결과 출력 영역
        self.result_area = scrolledtext.ScrolledText(self.root, font=("NanumGothic", 10),
                                                     bg="#FFFFFF", fg="#212529", bd=0,
                                                     highlightthickness=1, highlightbackground="#CED4DA", # 테두리 색상 살짝 진하게
                                                     padx=12, pady=12)
        self.result_area.pack(pady=(5, 10), padx=30, fill=tk.BOTH, expand=True)
        
        self.info_label = tk.Label(self.root, text="💡 팁: 분석할 내용을 화면에 띄우고 버튼을 누르세요.", 
                                   font=("NanumGothic", 9), bg="#F8F9FA", fg="#6C757D", wraplength=350)
        self.info_label.pack(pady=(0, 20))

    def initialize_gemini(self):
        """Gemini API 설정 및 사용 가능한 모델 탐색"""
        if not self.api_key:
            self.update_ui(f"❌ API 키를 찾을 수 없습니다.\n\n확인 경로: {CURRENT_DIR}\n\n위 폴더에 env.txt 파일이 있는지 확인해 주세요.")
            return

        try:
            genai.configure(api_key=self.api_key)
            
            # 실제로 접근 가능한 모델 목록 전체를 가져옵니다.
            models = list(genai.list_models())
            available_names = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
            
            # 디버깅을 위해 콘솔에도 출력합니다.
            print(f"접근 가능한 모델: {available_names}")

            # 우선순위 키워드로 유연하게 매칭 (이름에 키워드가 포함되어 있으면 선택)
            priority_keywords = ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.5-pro', 'gemini-pro-latest', 'gemini-pro-vision', 'gemini-pro']
            selected_model_name = None
            
            for keyword in priority_keywords:
                selected_model_name = next((name for name in available_names if keyword in name), None)
                if selected_model_name:
                    break

            if selected_model_name:
                self.model = genai.GenerativeModel(selected_model_name)
                self.status_label.config(text=f"✅ 연결됨: {selected_model_name.split('/')[-1]}")
            else:
                model_list_str = "\n".join(available_names) if available_names else "없음 (API 키 확인 필요)"
                self.update_ui(f"❌ 사용 가능한 모델을 찾을 수 없습니다.\n\n[확인된 목록]\n{model_list_str}")
        except Exception as e:
            self.update_ui(f"❌ 초기화 오류: {str(e)}")

    def start_analysis_thread(self):
        self.btn_analyze.config(state=tk.DISABLED)
        thread = threading.Thread(target=self.analyze_screen)
        thread.daemon = True
        thread.start()

    def analyze_screen(self):
        if not self.model:
            self.initialize_gemini()
            if not self.model:
                self.root.after(0, lambda: self.btn_analyze.config(state=tk.NORMAL))
                return

        try:
            self.update_ui("📸 화면 캡처 중...")
            self.root.withdraw()
            time.sleep(0.4) 

            with mss.mss() as sct:
                img_data = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", img_data.size, img_data.bgra, "raw", "BGRX")

            self.root.deiconify()
            img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)

            self.update_ui("🧠 AI가 분석 중입니다 (10~15초 소요)...")
            
            prompt = """
            이미지 내 정보를 팩트체크하여 다음 형식으로 응답하세요:
            1. [SCORE] 0에서 100 사이의 숫자로 신뢰도 표기
            2. [REASON] 판단 근거를 불렛 포인트로 설명
            3. [MISINFORMATION_IDENTIFIED] 이미지 내에서 발견된 거짓 정보나 오해의 소지가 있는 부분을 명확히 지적하고, 올바른 사실로 교정해 주세요. 
               특히 어떤 문구/수치가 왜 틀렸는지 근거를 들어 상세히 설명하세요. 거짓 정보가 없다면 '없음'이라고 명시하세요.
            
            모든 응답은 정중한 한국어로 작성하세요.
            """
            
            response = self.model.generate_content([prompt, img])
            
            if response.text:
                self.process_result(response.text)
            else:
                self.update_ui("⚠️ 분석 결과를 생성할 수 없습니다.")

        except Exception as e:
            self.root.deiconify()
            error_msg = str(e)
            if "429" in error_msg:
                self.update_ui("❌ API 사용 한도 초과 (429 Error)\n\n"
                               "원인: 무료 버전의 사용 제한에 도달했습니다.\n"
                               "- 너무 빠르게 버튼을 여러 번 눌렀거나\n"
                               "- 오늘의 전체 할당량을 모두 사용했습니다.\n\n"
                               "해결 방법: 약 1분 뒤에 다시 시도해 보시고, 계속 안 될 경우 내일 다시 사용해 주세요.")
            else:
                self.update_ui(f"❌ 분석 중 오류 발생:\n{error_msg}")
        finally:
            self.root.after(0, lambda: self.btn_analyze.config(state=tk.NORMAL))

    def process_result(self, text):
        """분석 결과 처리 및 UI 업데이트"""
        # AI 응답의 태그를 변환하고 숫자 뒤에 %를 붙여 더 직관적으로 만듭니다.
        display_text = re.sub(r'\[SCORE\]\s*(\d+)', r'📊 신뢰도 점수: \1%', text)
        display_text = display_text.replace("[REASON]", "📝 판단 근거:")
        display_text = display_text.replace("[MISINFORMATION_IDENTIFIED]", "🔍 확인된 허위 정보:")

        self.update_ui(f"--- 팩트체크 분석 상세 결과 ---\n\n{display_text}")
        
        score_match = re.search(r'\[SCORE\]\s*(\d+)', text)
        if score_match:
            score = int(score_match.group(1))
            color = "#DC3545" if score < 50 else "#FD7E14" if score < 80 else "#198754"
            # 상단 점수 라벨과 윈도우 타이틀 업데이트
            self.root.after(0, lambda: self.score_label.config(text=f"신뢰도 점수: {score}%", fg=color))
            self.root.after(0, lambda: self.root.title(f"신뢰도 {score}% - AI Screen Fact Checker"))

    def update_ui(self, message):
        def _write():
            self.result_area.config(state=tk.NORMAL)
            self.result_area.delete(1.0, tk.END)
            self.result_area.insert(tk.INSERT, message)
            self.result_area.config(state=tk.DISABLED)
            self.result_area.see(tk.END)
        self.root.after(0, _write)

if __name__ == "__main__":
    app = TruthCheckerOverlay()
    app.root.mainloop()
