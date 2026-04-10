# test_mic.py
import sounddevice as sd
import numpy as np

# 列出所有音频设备
print("=== 音频设备列表 ===")
print(sd.query_devices())
print(f"\n默认输入设备: {sd.default.device[0]}")
print(f"默认输出设备: {sd.default.device[1]}")

# 录 3 秒测试
print("\n🎤 开始录音（3秒）...")
duration = 3  # 秒
sample_rate = 16000
audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
               channels=1, dtype='float32')
sd.wait()  # 等录完
print(f"✅ 录音完成，形状: {audio.shape}, 最大振幅: {np.max(np.abs(audio)):.4f}")

# 如果最大振幅 < 0.01，说明麦克风可能没声音
if np.max(np.abs(audio)) < 0.01:
    print("⚠️ 振幅太小，可能麦克风没有输入！检查系统声音设置。")
else:
    print("🎉 麦克风工作正常！")