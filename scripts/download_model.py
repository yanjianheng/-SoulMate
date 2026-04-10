import os
import time

# 【1】配置国内加速站，绕过官方慢网络
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# 忽略烦人的警告
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import warnings
warnings.filterwarnings("ignore", message=".*symlinks.*")

# 【2】指定咱们自己的模型的安全存放路径（避开C盘）
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "whisper")

# 我们只导入专门用来下载的模块，不启动任何模型或麦克风
from huggingface_hub import snapshot_download

repo_id = "Systran/faster-whisper-medium"

print("====================================")
print(f"🤖 开始自动下载/续传大模型：{repo_id}")
print(f"📂 存放目录：{MODEL_DIR}")
print("====================================")
print("💡 提示：国内网络极其容易中断。这个包如果报错断开，会自动原地满血复活（自动重连）！你只需挂机不用管。\n")

success = False
retry_count = 0

# 死磕网络：死循环下载，直到 success
while not success:
    try:
        snapshot_download(
            repo_id=repo_id,
            cache_dir=MODEL_DIR,
            resume_download=True,   # 断点续传
            max_workers=2,          # 调低并发连接数，防止网络因压力过大而断开
        )
        success = True
        print("\n🎉 恭喜！这个难啃的 medium 模型终于被完完整整下载到本地了！")
        print("➡️ 现在你可以放心地回去运行 `python .\\app\\voice\\stt.py` 进行录音测试了。")
    except Exception as e:
        retry_count += 1
        # 把长长的英文报错转成一句话提示，倒数 3 秒重新尝试连接
        print(f"\n⚠️ 遭遇第 {retry_count} 次网络中断（不用担心，它保存了之前的进度）。")
        print("🔄 准备 3 秒后自动断线重连...")
        time.sleep(3)
