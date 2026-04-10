# voice/stt.py
# 从 faster-whisper 导入 WhisperModel 类，用来加载语音识别模型。
from faster_whisper import WhisperModel
# 导入 numpy，只是为了给音频参数写清楚数组类型。
import numpy as np
# 导入 time，用来统计模型加载和识别耗时。
import time
# 导入 os 和 warnings，用来屏蔽无关的 HuggingFace 下载警告。
import os
import warnings

# 【关键网络加速】因为国内访问 Hugging Face 极度缓慢，必须配置国内镜像站加速下载
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 屏蔽 HuggingFace Hub 的 symlink 警告（Windows 无管理员权限下的无害提示）。
warnings.filterwarnings("ignore", message=".*symlinks.*")
# 告诉 HuggingFace Hub 不显示未认证的速率提示（不影响功能）。
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# 自动计算模型存放目录：获取当前文件 (stt.py) 所在目录，向上退三层到达 project 根目录，在里面建个 models/whisper 文件夹存放模型
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "whisper")

# 用全局变量缓存模型实例，避免每识别一次都重新加载一次模型。
_model = None

# 定义加载 STT 模型的函数，默认加载 small 规格。
def load_stt_model(model_size: str = "medium"):
    # 文档字符串说明这个函数负责把 Whisper 模型加载到 GPU。
    """加载 Whisper 模型到 GPU"""
    # 声明这里操作的是全局变量 _model，而不是新建局部变量。
    global _model
    # 只有模型还没加载时，才真正执行加载逻辑。
    if _model is None:
        # 打印提示，让用户知道第一次加载模型会稍微等一下。
        print(f"🔄 加载 Whisper {model_size} 模型...")
        # 记录加载开始时间，后面打印耗时。
        t = time.time()
        # 创建 WhisperModel 实例，并把它放到 GPU 上运行。
        _model = WhisperModel(
            # 使用调用方指定的模型大小，例如 small 或 medium。
            model_size,
            # 临时改为 CPU 运行，绕过缺失 cublas64_12.dll 的问题，确保先跑通闭环！
            # 等测试成功跑通后，我们再去配置那一堆复杂的 CUDA 12 环境。
            device="cpu",
            compute_type="int8",
            # 强制指定模型下载路径，绝不允许它流窜到 C 盘！
            download_root=MODEL_DIR,
        )
        # 打印加载完成和耗时，便于确认模型是否成功初始化。
        print(f"✅ 模型加载完成（{time.time() - t:.1f}秒）")
    # 返回已经加载好的模型对象。
    return _model

# 定义语音转文字函数，输入是 numpy 音频数组，输出是字符串。
def speech_to_text(audio: np.ndarray) -> str:
    # 文档字符串说明这个函数会把音频数组转成文字。
    """将音频 numpy 数组转为文字"""
    # 先拿到已经缓存好的 Whisper 模型，如果没加载过会在这里自动加载。
    model = load_stt_model()
    # 记录识别开始时间，后面统计 STT 耗时。
    t = time.time()

    # 调用 transcribe() 正式执行识别，返回分段生成器和额外信息。
    segments, info = model.transcribe(
        # 把待识别的音频数组传给模型。
        audio,
        # 明确告诉模型这是中文，省掉自动语言检测时间。
        language="zh",
        # 束搜索宽度设为 5，在速度和准确率之间取平衡。
        beam_size=5,
        # 打开 VAD 静音过滤，避免空白段浪费推理时间。
        vad_filter=True,
    )

    # 先准备一个空字符串，后面把每段识别结果拼起来。
    text = ""
    # 逐段遍历识别结果生成器。
    for segment in segments:
        # 把当前分段的文本追加到最终结果中。
        text += segment.text

    # 计算本次识别总耗时。
    elapsed = time.time() - t
    # 打印去掉首尾空白后的识别结果文本。
    print(f"📝 识别结果: {text.strip()}")
    # 打印 STT 耗时，便于后面做性能比较。
    print(f"⏱️ STT 耗时: {elapsed:.2f}秒")
    # 把最终文字结果返回给调用方。
    return text.strip()

# ================= 以下是测试代码 =================

# 只有直接运行这个 stt.py 文件时，下面的代码才会执行
if __name__ == "__main__":
    # 我们需要先导入自己写的录音函数
    # 注意路径：假设你在 project 目录下运行，从 app.voice.audio 中导入
    from audio import record_audio

    print("=== 开始 STT 模块单独测试 ===")
    
    # 第一步：先调用录音函数，录一段音
    print("准备录音...")
    my_audio = record_audio()
    
    # 第二步：把录好的音频数组，传给我们要测试的 speech_to_text 函数
    print("\n准备开始语音识别...")
    result_text = speech_to_text(my_audio)
    
    # 第三步：看看最终返回的结果
    print("\n=== 测试完成 ===")
    print(f"最终拿到的返回值是: {result_text}")
