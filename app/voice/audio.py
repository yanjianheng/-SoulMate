#  1. 等你按一次 Enter，开始录音
#  2. 声卡不断把一小块一小块的音频送进 callback
#  3. 每一块都先存进 audio_chunks 列表
#  4. 你再按一次 Enter，停止录音
#  5. 把所有小块拼成一整段音频并返回

import sounddevice as sd
import numpy as np
import pygame
import time

SAMPLE_RATE = 16000  # Whisper 要求
CHANNELS = 1         # 单声道

def record_audio() -> np.ndarray:
    """按 Enter 开始录音，再按 Enter 停止"""
    print("🎤 按 Enter 开始录音...")
    input()

    # 用 InputStream 持续录音，直到再次按 Enter
    audio_chunks = []

    def callback(indata, frames, time, status):
        """每次声卡采集到一块数据就调这个函数"""
        if status:
            print(f"录音状态: {status}")
        audio_chunks.append(indata.copy())

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype='float32', callback=callback)
    stream.start()
    print("🔴 录音中... 按 Enter 停止")
    input()
    stream.stop()
    stream.close()

    # 把所有块拼成一个完整的 numpy 数组
    audio = np.concatenate(audio_chunks, axis=0)
    audio = audio.flatten()  # 变成一维数组 (N,)
    print(f"✅ 录音完成，时长: {len(audio)/SAMPLE_RATE:.1f}秒")
    return audio

# 定义播放函数，参数 file_path 是待播放音频文件的路径。
def play_audio(file_path: str):
    # 文档字符串说明这个函数负责把已有音频文件播出来。
    """播放音频文件"""
    # 初始化 pygame 的 mixer 模块，否则后面无法真正发声。
    pygame.mixer.init()
    # 记录播放开始时间，后面打印总播放耗时。
    t = time.time()
    # 把目标音频文件加载到 pygame 的音乐播放器里。
    pygame.mixer.music.load(file_path)
    # 开始异步播放已经加载好的音频。
    pygame.mixer.music.play()

    # 只要音频还在播放，这个循环就一直等待。
    while pygame.mixer.music.get_busy():
        # 每 0.1 秒检查一次播放状态，避免 CPU 空转。
        time.sleep(0.1)

    # 打印播放完成和耗时，确认声音已经播完。
    print(f"🔊 播放完成（{time.time() - t:.2f}秒）")
    # 卸载当前音频文件，释放文件占用和 mixer 资源。
    pygame.mixer.music.unload()

if __name__ == "__main__":
    record_audio()