# voice/tts.py
# 导入 time，用来统计语音合成耗时。
import time
import os

# 自动定位当前代码的路径，并由此推算出并建立一个专门存放音频的临时文件夹
TEMP_AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "audio_temp")
# 确保存放音频的目录一定存在，不存在会自动创建 (SoulMate/project/data/audio_temp)
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

# 我们在这里建一个全局变量，把模型塞进去，以后无论喊多少句话，只加载一次！
_melo_model = None

# 定义本地 MeloTTS 方案，默认输出文件名是 output.wav。
def tts_melo(text: str, output_path: str = "output.wav"):
    # 文档字符串说明这个函数走本地 CPU 的 MeloTTS。
    """用 MeloTTS 合成中文语音（CPU 推理，不占 GPU）"""
    global _melo_model
    # 在函数内部导入 MeloTTS，避免没安装时影响整个模块导入。
    from melo.api import TTS as MeloTTS
    # 记录开始时间，后面打印总耗时。
    t = time.time()

    # 只有当模型为空（第一次召唤）时，才去苦哈哈地从硬盘读大模型
    if _melo_model is None:
        print("🔄 正在将 MeloTTS 模型读入内存（仅首次运行需要几秒）...")
        _melo_model = MeloTTS(language="ZH", device="cpu")
        
    # 取出模型里可用说话人的字典。
    speaker_ids = _melo_model.hps.data.spk2id
    # 从可用说话人里取第一个 ID 作为默认音色。
    speaker_id = list(speaker_ids.values())[0]

    # 调用 tts_to_file() 把文字合成为音频文件。
    _melo_model.tts_to_file(text, speaker_id, output_path, speed=1.0)
    # 打印输出文件路径和耗时，方便确认文件是否生成成功。
    print(f"🔊 TTS 合成完成 → {output_path}（{time.time() - t:.2f}秒）")
    # 把生成好的音频文件路径返回给调用方。
    return output_path

# 定义云端 edge-tts 备用方案，默认输出 mp3 文件。
def tts_edge(text: str, output_path: str = "output.mp3"):
    # 文档字符串说明这个函数依赖网络请求。
    """用 edge-tts 合成（需联网）"""
    # 导入 asyncio，用来运行异步 TTS 调用。
    import asyncio
    # 导入 edge_tts，用来访问微软在线 TTS 服务。
    import edge_tts
    # 记录开始时间，后面统计合成耗时。
    t = time.time()

    # 定义一个内部异步函数，真正执行 edge-tts 请求。
    async def _generate():
        # 创建 Communicate 对象，指定待合成文字和使用的音色。
        communicate = edge_tts.Communicate(
            # 把待朗读的文本传给 edge-tts。
            text,
            # 指定中文女声音色 Xiaoxiao。
            voice="zh-CN-XiaoxiaoNeural",
            # 如果想换男声，可以把上面那行改成下面这行。
            # voice="zh-CN-YunxiNeural",
        )
        # 把合成后的音频保存到指定输出文件。
        await communicate.save(output_path)

    # 在同步代码里运行上面的异步函数。
    asyncio.run(_generate())
    # 打印输出路径和总耗时，确认云端 TTS 已完成。
    print(f"🔊 TTS 合成完成 → {output_path}（{time.time() - t:.2f}秒）")
    # 把生成好的音频文件路径返回给调用方。
    return output_path

# 定义统一入口，优先尝试本地 MeloTTS，失败再回退到 edge-tts。
def text_to_speech(text: str, output_path: str = "output.wav") -> str:
    """TTS 统一入口，先试 MeloTTS，失败则用 edge-tts"""
    # 如果传入的文本是空字符串（比如 LLM 调用失败返回空），直接跳过，不生成损坏的音频文件
    if not text or not text.strip():
        print("⚠️ TTS 跳过：收到的文本为空")
        return ""
    # 果传来的是纯文件名(不是写死的绝对路径)，就强制前置咱们的专用临时文件夹路径
    if not os.path.isabs(output_path):
        output_path = os.path.join(TEMP_AUDIO_DIR, output_path)
    
    # 先尝试走本地 MeloTTS 路线。
    try:
        # 如果本地方案成功，直接返回生成文件路径。
        return tts_melo(text, output_path)
    # 如果本地方案报错，就进入异常分支。
    except Exception as e:
        # 打印异常原因，并提示接下来要切换到 edge-tts。
        print(f"⚠️ MeloTTS 失败({e})，切换到 edge-tts")
        # 把输出文件后缀从 .wav 改成 .mp3，再走云端方案。
        return tts_edge(text, output_path.replace(".wav", ".mp3"))

# ================= 以下是测试代码 =================

# 只有直接运行这个 tts.py 文件时，下面的代码才会执行
if __name__ == "__main__":
    print("=== 开始 TTS 模块极速性能测试 ===")
    
    print("\n[第一轮] 准备把大模型搬进内存（包含模型冷启动热身，会用到 5-8 秒）")
    test_text1 = "嘿，你好啊！我是你的大猪。初次见面，请多关照！"
    file1 = text_to_speech(test_text1, output_path="output1.wav")
    
    print("\n[第二轮] 模型已在内存常驻，享受真实聊天环境下的极速体验！")
    test_text2 = "主人，你看！我现在生成语音的速度是不是变得如同闪电一般快了？这下咱们可以无缝沟通啦！"
    file2 = text_to_speech(test_text2, output_path="output2.wav")
    
    print("\n=== 测试宣告结束 ===")
    print("本次完全没有让喇叭发声，仅仅只是快速生成了发音文件。")
    print("请在刚才的目录下找到 output1.wav 和 output2.wav，双击听听效果！")