"""
阿里云 Qwen3-TTS-Flash 语音合成模块

使用 DashScope SDK 进行语音合成，替代原有的 Edge TTS、Azure TTS 等方案。
支持的声音列表：https://help.aliyun.com/zh/model-studio/qwen-tts/
"""

import os
import base64
from typing import Union

import dashscope
from loguru import logger
from moviepy.audio.io.AudioFileClip import AudioFileClip

from app.config import config
from app.utils import utils


# 阿里云 Qwen3-TTS 支持的声音列表
# 格式：(voice_id, display_name, gender, language)
ALIYUN_VOICES = [
    # 中文女声
    ("Cherry", "樱桃-甜美", "Female", "Chinese"),
    ("Serena", "塞琳娜-知性", "Female", "Chinese"),
    ("Ethan", "伊森-成熟", "Male", "Chinese"),
    ("Chelsie", "切尔西-活力", "Female", "Chinese"),
  

    # 英文声音
    ("Cherry", "Cherry-Sweet", "Female", "English"),
    ("Serena", "Serena-Elegant", "Female", "English"),
    ("Ethan", "Ethan-Mature", "Male", "English"),
    ("Chelsie", "Chelsie-Energetic", "Female", "English"),
    ("Ryan", "Ryan-成熟", "Male", "English")
]


def get_aliyun_voices() -> list[str]:
    """
    获取阿里云 Qwen3-TTS 支持的声音列表
    
    Returns:
        声音列表，格式为 ["aliyun:Cherry-樱桃-甜美-Female-Chinese", ...]
    """
    voices = []
    for voice_id, display_name, gender, language in ALIYUN_VOICES:
        # 格式: aliyun:voice_id-display_name-gender-language
        voice_key = f"aliyun:{voice_id}-{display_name}-{gender}-{language}"
        voices.append(voice_key)
    return voices


def parse_aliyun_voice_name(voice_name: str) -> tuple[str, str]:
    """
    解析阿里云语音名称
    
    Args:
        voice_name: 格式为 "aliyun:Cherry-樱桃-甜美-Female-Chinese"
    
    Returns:
        (voice_id, language_type) 元组
    """
    if not voice_name.startswith("aliyun:"):
        return "Cherry", "Chinese"
    
    parts = voice_name.replace("aliyun:", "").split("-")
    voice_id = parts[0] if parts else "Cherry"
    language = parts[-1] if len(parts) > 1 else "Chinese"
    
    return voice_id, language


def is_aliyun_voice(voice_name: str) -> bool:
    """检查是否是阿里云的声音"""
    return voice_name.startswith("aliyun:")


def parse_voice_name(voice_name: str) -> str:
    """
    解析声音名称（保持向后兼容）
    
    对于阿里云声音，直接返回原始名称。
    该函数保留是为了与 task.py 等调用方保持兼容。
    
    Args:
        voice_name: 声音名称
    
    Returns:
        解析后的声音名称
    """
    return voice_name


class SimpleSubMaker:
    """
    简单的字幕生成器，用于存储音频时间戳信息
    
    由于阿里云 TTS 不返回逐字时间戳，我们需要从音频文件中获取时长，
    并根据文本内容估算字幕时间。
    """
    
    def __init__(self):
        self.offset = []  # [(start_time, end_time), ...]
        self.subs = []    # [text, ...]
    
    def create_sub(self, offset: tuple, text: str):
        """添加一段字幕"""
        self.offset.append(offset)
        self.subs.append(text)
    
    def add_from_text_and_duration(self, text: str, duration_ms: float):
        """
        根据文本和总时长创建简单字幕
        
        Args:
            text: 完整文本
            duration_ms: 音频总时长（毫秒）
        """
        # 将文本按标点分割
        lines = utils.split_string_by_punctuations(text)
        if not lines:
            lines = [text]
        
        # 估算每个字的时长
        total_chars = sum(len(line) for line in lines)
        if total_chars == 0:
            return
        
        ms_per_char = duration_ms / total_chars
        current_time = 0.0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            line_duration = len(line) * ms_per_char
            start_time = current_time * 10000  # 转换为 100ns 单位
            end_time = (current_time + line_duration) * 10000
            
            self.offset.append((start_time, end_time))
            self.subs.append(line)
            
            current_time += line_duration


def aliyun_tts(
    text: str,
    voice_name: str,
    voice_rate: float,
    voice_file: str,
    voice_volume: float = 1.0,
) -> Union[SimpleSubMaker, None]:
    """
    使用阿里云 Qwen3-TTS-Flash 进行语音合成
    
    Args:
        text: 待转换文本
        voice_name: 声音名称，格式为 "aliyun:Cherry-樱桃-甜美-Female-Chinese"
        voice_rate: 语速 (0.5-2.0)
        voice_file: 输出音频文件路径
        voice_volume: 音量 (暂不支持)
    
    Returns:
        SimpleSubMaker 对象用于字幕生成，失败返回 None
    """
    # 获取 API Key
    api_key = config.app.get("aliyun_api_key", "")
    if not api_key:
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
    
    if not api_key:
        logger.error("阿里云 API Key 未配置，请在配置文件中设置 aliyun_api_key")
        return None
    
    # 解析声音名称
    voice_id, language_type = parse_aliyun_voice_name(voice_name)
    
    # 设置 DashScope 基础 URL
    dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
    
    text = text.strip()
    if not text:
        logger.error("文本内容为空")
        return None
    
    logger.info(f"开始阿里云 TTS 合成: voice={voice_id}, language={language_type}, rate={voice_rate}")
    
    for retry in range(3):
        try:
            # 调用阿里云 Qwen3-TTS-Flash
            response = dashscope.MultiModalConversation.call(
                model="qwen3-tts-flash",
                api_key=api_key,
                text=text,
                voice=voice_id,
                language_type=language_type,
                stream=False
            )
            
            # 检查响应
            if response is None:
                logger.warning(f"阿里云 TTS 响应为空，重试 {retry + 1}/3")
                continue
            
            # 处理响应
            if hasattr(response, 'status_code') and response.status_code != 200:
                logger.error(f"阿里云 TTS 失败: {response}")
                continue
            
            # 从响应中提取音频数据
            audio_data = None
            audio_url = None
            
            # 尝试从 output.audio 获取（新版 API 返回结构）
            if hasattr(response, 'output') and response.output:
                output = response.output
                # 检查是否有 audio 对象
                if hasattr(output, 'audio') and output.audio:
                    audio_obj = output.audio
                    # 优先使用 data 字段
                    if hasattr(audio_obj, 'data') and audio_obj.data:
                        audio_content = audio_obj.data
                        if isinstance(audio_content, str) and audio_content:
                            audio_data = base64.b64decode(audio_content)
                        elif isinstance(audio_content, bytes):
                            audio_data = audio_content
                    # 如果 data 为空，使用 url 字段
                    if audio_data is None and hasattr(audio_obj, 'url') and audio_obj.url:
                        audio_url = audio_obj.url
                elif isinstance(output, dict):
                    # 字典形式的响应
                    audio_obj = output.get('audio', {})
                    if audio_obj.get('data'):
                        audio_data = base64.b64decode(audio_obj['data'])
                    elif audio_obj.get('url'):
                        audio_url = audio_obj['url']
            
            # 如果有 URL，从 URL 下载音频
            if audio_data is None and audio_url:
                try:
                    import requests
                    logger.info(f"从 URL 下载音频: {audio_url[:80]}...")
                    audio_response = requests.get(audio_url, timeout=(30, 60))
                    if audio_response.status_code == 200:
                        audio_data = audio_response.content
                        logger.info(f"音频下载成功，大小: {len(audio_data)} 字节")
                    else:
                        logger.warning(f"音频下载失败，状态码: {audio_response.status_code}")
                except Exception as e:
                    logger.error(f"下载音频失败: {e}")
            
            if audio_data is None:
                logger.warning(f"无法从响应中提取音频数据，重试 {retry + 1}/3, response: {response}")
                continue
            
            # 保存音频文件
            with open(voice_file, "wb") as f:
                f.write(audio_data)
            
            # 验证文件
            if not os.path.exists(voice_file) or os.path.getsize(voice_file) == 0:
                logger.warning(f"音频文件保存失败，重试 {retry + 1}/3")
                continue
            
            # 获取音频时长并创建字幕 maker
            try:
                with AudioFileClip(voice_file) as audio:
                    duration_ms = audio.duration * 1000  # 转换为毫秒
            except Exception as e:
                logger.warning(f"获取音频时长失败: {e}，使用估算值")
                # 估算：每个字约 200ms
                duration_ms = len(text) * 200
            
            sub_maker = SimpleSubMaker()
            sub_maker.add_from_text_and_duration(text, duration_ms)
            
            logger.info(f"阿里云 TTS 合成完成: {voice_file}, 时长: {duration_ms/1000:.2f}s")
            return sub_maker
            
        except Exception as e:
            logger.error(f"阿里云 TTS 异常: {e}，重试 {retry + 1}/3")
            continue
    
    logger.error(f"阿里云 TTS 合成失败，已重试 3 次")
    return None


def tts(
    text: str,
    voice_name: str,
    voice_rate: float,
    voice_file: str,
    voice_volume: float = 1.0,
) -> Union[SimpleSubMaker, None]:
    """
    统一 TTS 入口函数
    
    使用阿里云 Qwen3-TTS-Flash 进行语音合成。
    
    Args:
        text: 待转换文本
        voice_name: 声音名称
        voice_rate: 语速
        voice_file: 输出音频文件路径
        voice_volume: 音量
    
    Returns:
        SimpleSubMaker 对象用于字幕生成
    """
    return aliyun_tts(text, voice_name, voice_rate, voice_file, voice_volume)


def get_audio_duration(target) -> float:
    """
    获取音频时长
    
    Args:
        target: SimpleSubMaker 对象或 MP3 文件路径
    
    Returns:
        音频时长（秒）
    """
    if isinstance(target, SimpleSubMaker):
        if not target.offset:
            return 0.0
        # offset 的单位是 100ns，需要转换为秒
        return target.offset[-1][1] / 10000000
    elif isinstance(target, str) and os.path.exists(target):
        try:
            with AudioFileClip(target) as audio:
                return audio.duration
        except Exception as e:
            logger.error(f"获取音频时长失败: {e}")
            return 0.0
    else:
        logger.error(f"无效的 target 类型: {type(target)}")
        return 0.0


def create_subtitle(sub_maker: SimpleSubMaker, text: str, subtitle_file: str):
    """
    创建字幕文件
    
    Args:
        sub_maker: SimpleSubMaker 对象
        text: 原始文本
        subtitle_file: 输出字幕文件路径
    """
    if not sub_maker or not sub_maker.subs:
        logger.warning("字幕数据为空，无法生成字幕文件")
        return
    
    def mktimestamp(time_100ns: float) -> str:
        """将 100ns 时间单位转换为 SRT 时间格式"""
        total_seconds = time_100ns / 10000000
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    try:
        sub_items = []
        for idx, ((start_time, end_time), sub_text) in enumerate(zip(sub_maker.offset, sub_maker.subs), 1):
            start_t = mktimestamp(start_time)
            end_t = mktimestamp(end_time)
            sub_items.append(f"{idx}\n{start_t} --> {end_t}\n{sub_text}\n")
        
        with open(subtitle_file, "w", encoding="utf-8") as f:
            f.write("\n".join(sub_items) + "\n")
        
        logger.info(f"字幕文件创建成功: {subtitle_file}")
    except Exception as e:
        logger.error(f"创建字幕文件失败: {e}")


if __name__ == "__main__":
    # 测试代码
    import os
    
    # 设置测试 API Key
    test_api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if test_api_key:
        config.app["aliyun_api_key"] = test_api_key
    
    # 测试语音合成
    test_text = "你好，这是一个测试。阿里云语音合成效果测试。"
    test_file = "test_tts.mp3"
    
    result = tts(
        text=test_text,
        voice_name="aliyun:Cherry-樱桃-甜美-Female-Chinese",
        voice_rate=1.0,
        voice_file=test_file,
    )
    
    if result:
        print(f"TTS 成功，音频文件: {test_file}")
        print(f"时长: {get_audio_duration(result):.2f}s")
    else:
        print("TTS 失败")
