# voice_main.py（放在 SoulMate 项目根目录，与 project/ 同级）
# 导入 time，用来统计整轮对话和各个阶段的耗时。
import time
# 导入 os，用来判断文件是否存在以及删除临时音频文件。
import os
# 导入 sys，用来修改 Python 模块搜索路径。
import sys
# 从 pathlib 导入 Path，用更稳妥的方式拼接路径。
from pathlib import Path

# 把 project 目录加入 sys.path，这样当前脚本就能导入 app 下的模块。
# 因为你把文件放到了 project/app/voice/ 目录下，所以向上连跳 3 级（.parent）就能回到 project 根目录。
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 从主工程导入 generate_reply，直接复用已有的大模型调用封装。
from app.chat.engine import generate_reply
# 从录音模块导入录音和播放函数。
from app.voice.audio import record_audio, play_audio
# 从 STT 模块导入语音识别函数和模型预加载函数。
from app.voice.stt import speech_to_text, load_stt_model
# 从 TTS 模块导入文字转语音函数。
from app.voice.tts import text_to_speech

# 定义单轮对话函数，输入用户文字，输出模型回答。
def ask_once(text: str) -> str:
    # 文档字符串说明这里是里程碑 1 的单轮问答，不带历史记录。
    """里程碑1：单轮对话（不带历史）"""
    # 构造消息列表，格式和 Chat API 常见的 role/content 结构一致。
    messages = [
        # system 消息用于设定角色和回复风格。
        {
            "role": "system",
            "content": "你是小猪子，回答简洁，控制在2~3句。",
        },
        # user 消息放入这一轮用户刚说的话。
        # 注意：不要修改 role 的名字，大模型 API 严格规定这一栏只能填 "user"、"system" 或 "assistant"。
        {
            "role": "user",
            "content": text,
        },
    ]
    # 调用 generate_reply() 获取回答，并直接返回字符串结果。
    return generate_reply(model="qwen3:8b-q4_K_M", messages=messages)

# 定义主函数，负责把录音、识别、问答、合成、播放串起来。
def main():
    # 打印一条分隔线，让程序启动界面更清楚。
    print("=" * 50)
    # 打印程序标题，告诉用户当前运行的是语音对话版本。
    print("🤖 SoulMate - 里程碑 1：最小语音对话")
    # 再打印一条分隔线，形成完整标题区域。
    print("=" * 50)

    # 先预加载 Whisper 模型，避免第一次识别时用户等待太久。
    load_stt_model()

    # 进入无限循环，直到用户说出退出词才跳出。
    while True:
        # 记录一整轮对话的开始时间。
        total_start = time.time()
        # 创建一个空字典，用来记录每个阶段分别花了多久。
        timings = {}

        # 记录录音开始时间。
        t = time.time()
        # 调用录音函数，让用户按 Enter 开始/结束录音。
        audio = record_audio()
        # 把录音阶段耗时记到 timings 字典里。
        timings["录音"] = time.time() - t

        # 记录语音识别开始时间。
        t = time.time()
        # 把刚录到的音频数组送进 Whisper，拿到识别出的文字。
        text = speech_to_text(audio)
        # 把 STT 阶段耗时记到 timings 字典里。
        timings["STT"] = time.time() - t

        # 如果识别结果为空，说明这轮没有成功识别到内容。
        if not text:
            # 提示用户重试当前这轮。
            print("❌ 未识别到内容，请重试")
            # 直接跳过后面步骤，进入下一轮录音。
            continue
        # 如果识别结果里包含退出词，就准备结束程序。
        if any(w in text for w in ["退出", "再见", "拜拜"]):
            # 向用户打印告别信息。
            print("👋 再见！")
            # 跳出 while 循环，结束整个程序。
            break

        # 记录大模型推理开始时间。
        t = time.time()
        # 调用 ask_once()，把用户文本交给大模型生成回复。
        reply = ask_once(text)
        # 把 LLM 阶段耗时记到 timings 字典里。
        timings["LLM"] = time.time() - t

        # 如果大模型返回空（比如 Ollama 连接失败），跳过后续步骤重新开始录音
        if not reply:
            print("⚠️ 大模型没有返回内容，请检查 Ollama 是否正常运行，继续下一轮...")
            continue

        # 记录语音合成开始时间。
        t = time.time()
        # 把大模型回复转成音频文件，并拿到文件路径。
        audio_file = text_to_speech(reply)
        # 把 TTS 阶段耗时记到 timings 字典里。
        timings["TTS"] = time.time() - t

        # 如果 TTS 合成失败（返回空路径），跳过播放
        if not audio_file:
            print("⚠️ 语音合成失败，跳过播放，继续下一轮...")
            continue

        # 记录播放开始时间。
        t = time.time()
        # 播放刚刚生成的回复音频文件。
        play_audio(audio_file)
        # 把播放阶段耗时记到 timings 字典里。
        timings["播放"] = time.time() - t

        # 暂时保留临时音频文件，方便调试回听。
        # 等调试完毕后，取消下面的注释即可恢复自动清理。
        # if os.path.exists(audio_file):
        #     os.remove(audio_file)

        # 计算整轮总耗时。
        total = time.time() - total_start
        # 打印一条分隔线，准备输出本轮耗时统计。
        print(f"\n{'=' * 40}")
        # 逐项遍历 timings 字典里的阶段名称和耗时。
        for step, elapsed in timings.items():
            # 根据耗时长度生成一个简单的文本条形图。
            bar = "█" * int(elapsed * 5)
            # 打印当前阶段名称、耗时和条形图。
            print(f"  {step:6s}: {elapsed:5.2f}s {bar}")
        # 打印这一整轮对话的总耗时。
        print(f"  {'总计':6s}: {total:5.2f}s")
        # 打印结尾分隔线，并空一行方便下一轮观察。
        print(f"{'=' * 40}\n")

# 只有直接运行这个脚本时，下面的主入口才会执行。
if __name__ == "__main__":
    # 调用主函数，正式启动完整语音对话流程。
    main()